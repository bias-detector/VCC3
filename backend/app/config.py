import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "VCC-3 Service")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))
    max_local_concurrency: int = int(os.getenv("MAX_LOCAL_CONCURRENCY", "4"))
    max_local_queue: int = int(os.getenv("MAX_LOCAL_QUEUE", "20"))
    offload_queue_threshold: int = int(os.getenv("OFFLOAD_QUEUE_THRESHOLD", "8"))
    local_wait_timeout_seconds: int = int(os.getenv("LOCAL_WAIT_TIMEOUT_SECONDS", "8"))
    cloud_backend_url: str = os.getenv("CLOUD_BACKEND_URL", "").strip().rstrip("/")
    public_base_url: str = (
        os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
    )


settings = Settings()
