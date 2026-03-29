import asyncio
from dataclasses import dataclass

import httpx

from .config import settings


@dataclass
class Metrics:
    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    errors: int = 0
    offload_events: int = 0
    queue_depth: int = 0


class LoadShiftController:
    def __init__(self) -> None:
        self.metrics = Metrics()
        self.local_semaphore = asyncio.Semaphore(settings.max_local_concurrency)
        self.queue_limit = settings.max_local_queue
        self._queue_depth = 0
        self._lock = asyncio.Lock()

    async def enqueue(self) -> bool:
        async with self._lock:
            if self._queue_depth >= self.queue_limit:
                return False
            self._queue_depth += 1
            self.metrics.queue_depth = self._queue_depth
            return True

    async def dequeue(self) -> None:
        async with self._lock:
            self._queue_depth = max(0, self._queue_depth - 1)
            self.metrics.queue_depth = self._queue_depth

    async def should_offload(self) -> bool:
        async with self._lock:
            return (
                bool(settings.cloud_backend_url)
                and self._queue_depth >= settings.offload_queue_threshold
            )

    async def classify_via_cloud(self, text: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            target = f"{settings.cloud_backend_url}/api/classify"
            response = await client.post(target, json={"text": text})
            response.raise_for_status()
            data = response.json()
        self.metrics.cloud_requests += 1
        self.metrics.offload_events += 1
        data["source"] = "cloud"
        return data


controller = LoadShiftController()
