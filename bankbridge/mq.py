"""Development-only MQ REST producer. JMS worker uses transactional consumption."""
import logging
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from .settings import Settings


class MQPublishError(RuntimeError):
    pass


def publish_message(payload: str, settings: Settings) -> None:
    """Persistent put; duplicate sends are possible after ambiguous HTTP/network failures.

    MQ REST is intentionally used for publication only. We do NOT destructively GET over
    REST as that cannot atomically acknowledge after committing the database transaction.
    """
    url = (settings.mq_url.rstrip("/") + "/ibmmq/rest/v3/messaging/qmgr/"
           + quote(settings.mq_qmgr, safe="") + "/queue/" + quote(settings.mq_queue, safe="") + "/message")
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "ibm-mq-rest-csrf-token": "bankbridge",
        "ibm-mq-md-persistence": "persistent",
    }
    try:
        resp = requests.post(url, data=payload.encode("utf-8"), headers=headers,
                             auth=HTTPBasicAuth(settings.mq_user, settings.mq_password),
                             timeout=(5, 15), verify=settings.mq_tls_verify)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise MQPublishError(f"IBM MQ publication failed: {type(exc).__name__}") from exc
