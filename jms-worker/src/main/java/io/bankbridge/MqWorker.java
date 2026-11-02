package io.bankbridge;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ibm.mq.jms.MQConnectionFactory;
import com.ibm.msg.client.wmq.WMQConstants;
import javax.jms.Connection;
import javax.jms.Destination;
import javax.jms.Message;
import javax.jms.MessageConsumer;
import javax.jms.MessageProducer;
import javax.jms.Session;
import javax.jms.TextMessage;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.logging.Level;
import java.util.logging.Logger;

/** IBM MQ JMS transactional consumer. Commit MQ only AFTER DB API succeeds.
 *
 * Network errors after DB commit can cause message redelivery. The database
 * guarantees idempotent ledger effects for each transfer_id.
 */
public class MqWorker {
    private static final Logger LOG = Logger.getLogger(MqWorker.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5)).build();

    private static String env(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing required env: " + name);
        return value;
    }

    private static boolean process(String raw) throws Exception {
        JsonNode event = MAPPER.readTree(raw);
        if (!event.hasNonNull("event_type") || !event.hasNonNull("transfer_id")) {
            throw new IllegalArgumentException("Message is missing event_type or transfer_id");
        }
        if (!"payment.requested".equals(event.get("event_type").asText())) {
            throw new IllegalArgumentException("Unexpected event type");
        }
        String id = event.get("transfer_id").asText();
        if (!id.matches("[0-9a-fA-F-]{36}")) {
            throw new IllegalArgumentException("Invalid transfer ID format");
        }
        HttpRequest req = HttpRequest.newBuilder()
            .uri(URI.create(env("CORE_API", "http://api:8000") + "/internal/process/" + id))
            .header("X-Internal-Token", required("BANKBRIDGE_INTERNAL_TOKEN"))
            .timeout(Duration.ofSeconds(20))
            .POST(HttpRequest.BodyPublishers.noBody()).build();
        HttpResponse<String> response = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() >= 200 && response.statusCode() < 300) {
            LOG.info("Processed transfer=" + id + " status=" + response.statusCode());
            return true;
        }
        if (response.statusCode() == 400 || response.statusCode() == 404) {
            throw new IllegalArgumentException("Permanent API validation failure HTTP=" + response.statusCode());
        }
        throw new IllegalStateException("Retryable processing error HTTP=" + response.statusCode());
    }

    public static void main(String[] args) throws Exception {
        // Restrict to isolated developer network. Production requires mTLS / MQ TLS.
        MQConnectionFactory cf = new MQConnectionFactory();
        cf.setHostName(env("MQ_HOST", "mq"));
        cf.setPort(Integer.parseInt(env("MQ_PORT", "1414")));
        cf.setQueueManager(env("MQ_QMGR", "QM1"));
        cf.setChannel(env("MQ_CHANNEL", "DEV.APP.SVRCONN"));
        cf.setTransportType(WMQConstants.WMQ_CM_CLIENT);
        cf.setBooleanProperty(WMQConstants.USER_AUTHENTICATION_MQCSP, true);
        String queue = env("MQ_QUEUE", "DEV.QUEUE.1");
        String poisonQueue = env("MQ_POISON_QUEUE", "DEV.QUEUE.2");
        int maxPoisonAttempts = Integer.parseInt(env("MAX_POISON_ATTEMPTS", "5"));
        LOG.info("Starting JMS worker; queue=" + queue + ", dead-letter=" + poisonQueue);
        while (true) {
            try (Connection conn = cf.createConnection(required("MQ_USER"), required("MQ_PASSWORD"))) {
                Session session = conn.createSession(true, Session.SESSION_TRANSACTED);
                Destination input = session.createQueue("queue:///" + queue);
                Destination dead = session.createQueue("queue:///" + poisonQueue);
                MessageConsumer consumer = session.createConsumer(input);
                MessageProducer poisonProducer = session.createProducer(dead);
                conn.start();
                while (true) {
                    Message msg = consumer.receive(10000);
                    if (msg == null) continue;
                    try {
                        if (!(msg instanceof TextMessage)) throw new IllegalArgumentException("Expected TextMessage");
                        process(((TextMessage) msg).getText());
                        session.commit();
                    } catch (Exception e) {
                        boolean permanent = e instanceof IllegalArgumentException;
                        int deliveries = 1;
                        try { deliveries = msg.getIntProperty("JMSXDeliveryCount"); }
                        catch (Exception ignored) { /* JMS property optional */ }
                        if (permanent && deliveries >= maxPoisonAttempts) {
                            try {
                                TextMessage poison = session.createTextMessage(
                                    "quarantined: " + ((msg instanceof TextMessage) ? ((TextMessage) msg).getText() : "<non-text>")
                                );
                                poisonProducer.send(poison);
                                session.commit(); // Move poison and ACK original in same MQ transaction
                                LOG.warning("Message quarantined after " + deliveries + " attempts");
                            } catch (Exception poisonFailure) {
                                session.rollback();
                                LOG.log(Level.SEVERE, "Could not quarantine; original message remains", poisonFailure);
                            }
                        } else {
                            session.rollback();
                            LOG.log(Level.WARNING, "Message rolled back: permanent=" + permanent + " attempts=" + deliveries, e);
                            Thread.sleep(2000);
                        }
                    }
                }
            } catch (Exception connectionFailure) {
                LOG.log(Level.SEVERE, "MQ connection lost, reconnecting in 5s", connectionFailure);
                Thread.sleep(5000);
            }
        }
    }
}
