"""Runtime settings, never hardcode deploy-time credentials into source."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./bankbridge.db")
    api_key: str = os.getenv("BANKBRIDGE_API_KEY", "local-demo-key-change-me")
    internal_token: str = os.getenv("BANKBRIDGE_INTERNAL_TOKEN", "local-internal-token-change-me")
    mq_url: str = os.getenv("MQ_REST_URL", "https://localhost:9443")
    mq_qmgr: str = os.getenv("MQ_QMGR", "QM1")
    mq_queue: str = os.getenv("MQ_QUEUE", "DEV.QUEUE.1")
    mq_user: str = os.getenv("MQ_REST_USER", "admin")
    mq_password: str = os.getenv("MQ_REST_PASSWORD", "")
    mq_tls_verify: bool = os.getenv("MQ_TLS_VERIFY", "true").lower() == "true"
    poll_interval: float = float(os.getenv("WORKER_POLL_SECONDS", "1"))
    mode: str = os.getenv("BANKBRIDGE_MODE", "local")
    allow_demo_seed: bool = os.getenv("ALLOW_DEMO_SEED", "false").lower() == "true"
