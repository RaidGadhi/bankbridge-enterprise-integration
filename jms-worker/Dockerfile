FROM maven:3.9.9-eclipse-temurin-17 AS builder
WORKDIR /work
COPY pom.xml .
COPY src ./src
RUN mvn -q -B -DskipTests package
FROM eclipse-temurin:17-jre
RUN useradd -u 10001 -m bb
WORKDIR /app
COPY --from=builder /work/target/mq-jms-worker-1.0.0.jar /app/worker.jar
USER bb
ENTRYPOINT ["java", "-jar", "/app/worker.jar"]
