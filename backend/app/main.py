import asyncio
import random
from pathlib import Path

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .llm_client import LocalLLMClassifier
from .models import ClassifyRequest, ClassifyResponse, LoadRequest, LoadResponse
from .scaler import controller

app = FastAPI(title="VCC 3", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = LocalLLMClassifier()

# Serve static files from frontend/public
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "public"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
        "cloud_fallback_enabled": bool(settings.cloud_backend_url),
    }


@app.get("/api/metrics")
async def metrics() -> dict:
    m = controller.metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    return {
        "service": settings.service_name,
        "total_requests": m.total_requests,
        "local_requests": m.local_requests,
        "cloud_requests": m.cloud_requests,
        "offload_events": m.offload_events,
        "queue_depth": m.queue_depth,
        "errors": m.errors,
        "cpu_percent": cpu_percent,
    }


@app.post("/api/classify", response_model=ClassifyResponse)
async def classify(payload: ClassifyRequest) -> ClassifyResponse:
    controller.metrics.total_requests += 1

    accepted = await controller.enqueue()
    if not accepted:
        controller.metrics.errors += 1
        raise HTTPException(status_code=503, detail="Queue full. Try again.")

    try:
        if await controller.should_offload():
            try:
                cloud_result = await controller.classify_via_cloud(payload.text)
                return ClassifyResponse(**cloud_result)
            except Exception:
                controller.metrics.errors += 1

        try:
            async with asyncio.timeout(settings.local_wait_timeout_seconds):
                async with controller.local_semaphore:
                    toxic, confidence, reason = await asyncio.to_thread(
                        classifier.classify, payload.text
                    )
        except TimeoutError:
            controller.metrics.errors += 1
            if settings.cloud_backend_url:
                cloud_result = await controller.classify_via_cloud(payload.text)
                return ClassifyResponse(**cloud_result)
            raise HTTPException(status_code=504, detail="Local model timeout")

        controller.metrics.local_requests += 1
        return ClassifyResponse(
            text=payload.text,
            toxic=toxic,
            confidence=confidence,
            reason=reason,
            source="local",
        )
    finally:
        await controller.dequeue()


@app.post("/api/generate-load", response_model=LoadResponse)
async def generate_load(payload: LoadRequest, request: Request) -> LoadResponse:
    base = str(request.base_url).rstrip("/")
    samples_toxic = [
        "You are stupid and useless",
        "I hate this and everyone involved",
        "Shut up, this is trash",
    ]
    samples_clean = [
        "Thank you for the help",
        "Can we improve this together?",
        "Great work on the assignment",
    ]

    semaphore = asyncio.Semaphore(payload.concurrency)
    local_routed = 0
    cloud_routed = 0
    failures = 0

    async def fire_one(i: int) -> None:
        nonlocal local_routed, cloud_routed, failures
        toxic_pick = random.random() <= payload.toxic_ratio
        text = random.choice(samples_toxic if toxic_pick else samples_clean) + f" [{i}]"

        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{base}/api/classify",
                        json={"text": text},
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("source") == "cloud":
                        cloud_routed += 1
                    else:
                        local_routed += 1
            except Exception:
                failures += 1

    await asyncio.gather(*(fire_one(i) for i in range(payload.total_requests)))
    completed = payload.total_requests - failures

    return LoadResponse(
        total_requests=payload.total_requests,
        completed=completed,
        failures=failures,
        local_routed=local_routed,
        cloud_routed=cloud_routed,
    )
