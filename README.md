# VCC 3 - Auto Scaling Toxicity Classifier Demo

This project is a Python microservice with frontend and backend for your VCC assignment.

- Page title: VCC 3
- Intro text: Auto scaling Demo project
- Main feature: toxicity classification using self-hosted local LLM
- Stress demo: red button to generate load and trigger local VM to Google Cloud VM load shift

## Architecture

1. Frontend UI is served by FastAPI
2. /api/classify first tries local processing
3. If queue pressure is high, request is offloaded to cloud VM
4. If local processing times out, fallback to cloud VM when configured
5. /api/generate-load creates burst traffic and returns local/cloud split

## Quick Start (Local VM with Docker)

Docker handles all dependencies automatically - no manual Ollama setup needed.

### Option A: One-Command Docker Deploy (Recommended)

Install Docker Desktop first.

```bash
cd /Users/adil.shamim/Desktop/VCC
chmod +x scripts/local-deploy.sh
./scripts/local-deploy.sh
```

This will:

- Start Ollama container and pull llama3.2:1b
- Launch FastAPI backend
- Expose everything on http://127.0.0.1:8000

First run takes 2-5 minutes for LLM model download (2GB)

### Option B: Manual Docker Compose

```bash
cd /Users/adil.shamim/Desktop/VCC
open -a Docker
docker info
docker compose up -d
docker exec vcc-ollama ollama pull llama3.2:1b
curl http://127.0.0.1:8000/api/health
```

Notes:

- `ollama pull` is one-time. Model files persist in the `ollama_data` Docker volume.
- If Docker is already running, `open -a Docker` is harmless.

Monitor progress:

```bash
docker compose logs -f ollama
docker compose logs -f vcc-backend
```

Stop:

```bash
docker compose down
```

### Option C: Manual Python Virtual Environment

If you prefer no Docker:

```bash
cd /Users/adil.shamim/Desktop/VCC
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

ollama pull llama3.2:1b

cd backend
set -a; source ../.env; set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://127.0.0.1:8000

## GCP Deployment (Cloud VM)

Automatically create a Google Cloud VM and deploy backend with one command.

### Prerequisites

1. Google Cloud SDK installed
2. Active GCP project with billing enabled
3. Authentication: gcloud auth login

### Deploy to GCP

```bash
chmod +x scripts/deploy-gcp-vm.sh
./scripts/deploy-gcp-vm.sh my-gcp-project vcc-3-backend us-central1-a e2-medium
```

Parameters:

- my-gcp-project: Your GCP project ID
- vcc-3-backend: VM name (optional)
- us-central1-a: Zone (optional)
- e2-medium: Machine type (optional)

The script will:

1. Create a Debian 12 VM
2. Install Docker
3. Clone this repo
4. Build and run backend container
5. Set up firewall rules for port 8000
6. Output the cloud VM IP

Example output:

```
Frontend: http://34.123.45.67:8000
API: http://34.123.45.67:8000/api
```

### Connect Local VM to Cloud Backend

Once cloud VM is running:

1. On local machine, edit .env:

```bash
SERVICE_NAME=VCC-3 Local VM
OLLAMA_URL=http://127.0.0.1:11434
CLOUD_BACKEND_URL=http://34.123.45.67:8000
MAX_LOCAL_CONCURRENCY=4
MAX_LOCAL_QUEUE=20
OFFLOAD_QUEUE_THRESHOLD=8
```

2. Restart local service:

```bash
docker compose restart vcc-backend
```

3. Open local frontend: http://127.0.0.1:8000

4. Click Generate Load and Trigger Upscaling button

5. Watch metrics show cloud_routed count increasing

### SSH into Cloud VM

```bash
gcloud compute ssh vcc-3-backend --zone us-central1-a
```

View logs:

```bash
docker logs vcc-3-backend -f
```

### Cleanup (Delete Cloud VM)

```bash
chmod +x scripts/cleanup-gcp-vm.sh
./scripts/cleanup-gcp-vm.sh my-gcp-project vcc-3-backend us-central1-a
```

Deploy the same code to cloud VM and run with:

- `SERVICE_NAME=VCC-3 Cloud VM`
- `CLOUD_BACKEND_URL=` (empty, since it IS the cloud backend)

On cloud VM (via SSH or deployment script):

```bash
# Via docker-compose
docker compose up -d

# Or directly:
docker run -d \
  --name vcc-3-backend \
  -p 8000:8000 \
  -e SERVICE_NAME="VCC-3 Cloud VM" \
  -e OLLAMA_MODEL="llama3.2:1b" \
  vcc-3-backend
```

Ensure cloud firewall allows port `8000`.

## Local -> Cloud Load Shift Demo (Assignment Presentation)

**Scenario:** Show how local VM auto-scales by offloading to cloud.

### Setupto Cloud Load Shift Demo (Assignment Presentation)

Scenario: Show how local VM auto-scales by offloading to cloud

### Setup

1. Local VM (Mac/Linux laptop):

```bash
./scripts/local-deploy.sh
```

2. Cloud VM (GCP):

```bash
./scripts/deploy-gcp-vm.sh my-project vcc-3-backend
```

3. Connect local to cloud (update .env):

```bash
CLOUD_BACKEND_URL=http://34.123.45.67:8000
docker compose restart vcc-backend
```

### Demo Flow

1. Open two browser tabs:
   - Local: http://127.0.0.1:8000/api/metrics
   - Cloud: http://34.123.45.67:8000/api/metrics

2. On local UI, click Generate Load and Trigger Upscaling with concurrency 40

3. Watch in real-time:
   - Local metrics: queue_depth spikes, then requests offload
   - Cloud metrics: total_requests and local_requests increase
   - Local metrics: cloud_routed count increases

4. Proof: Both metrics dashboards show the split trafficPOST /api/classify`

- `POST /api/generate-load`

---

## Project Structure (Industry Standard)

```
VCC/
├── frontend/                  ← UI code (separate from backend)
│   ├── public/               ← Static assets
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   └── src/                  ← Future React/TypeScript code
├── backend/                  ← API & LLM logic (pure Python)
│   └── app/
│       ├── main.py          ← FastAPI endpoints
│       ├── config.py        ← Settings (env vars)
│       ├── models.py        ← Request/response schemas
│       ├── llm_client.py    ← Ollama integration
│       └── scaler.py        ← Load balancer & queue logic
├── scripts/                  ← Deployment automation
│   ├── local-deploy.sh      ← One-command local setup
│   ├── deploy-gcp-vm.sh     ← One-command cloud deploy
│   └── cleanup-gcp-vm.sh    ← Tear down cloud resources
├── Dockerfile               ← Backend container (copies frontend too)
├── docker-compose.yml       ← Local dev orchestration
├── requirements.txt         ← Python dependencies
└── .env.example             ← Configuration template
```

**Why separate frontend/backend?**

- **Industry standard:** Clean separation of concerns
- **Scalable:** Frontend can later be served from CDN
- **Team-friendly:** Frontend dev doesn't need Python knowledge
- **Future-proof:** Easy to migrate to React/Vue when needed

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed explanation.

## Why Docker?

| Aspect | Docker | Manual Setup |
| ------ | ------ | ------------ |

| Dependencie

| Aspect                | Docker          | Manual Setup          |
| --------------------- | --------------- | --------------------- |
| Dependencies          | All built in    | Manual Ollama install |
| Reproducibility       | Same everywhere | Varies by machine     |
| Speed                 | One command     | 5+ commands           |
| Cloud Deployment      | 1 script        | Manual SSH setup      |
| Environment Variables | In compose      | Manual .env edits     |

Use ./scripts/local-deploy.sh on laptop, ./scripts/deploy-gcp-vm.sh for cloud.

## Troubleshooting

Port 8000 in use:

```bash
docker-compose down
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

Ollama model not downloading:

```bash
docker logs vcc-ollama -f
```

Wait 2-5 min, check disk space (2GB needed)

Cloud VM frontend loads but Classify button hangs:

- Check network firewall allows traffic
- SSH in: gcloud compute ssh vcc-3-backend --zone ZONE
- Check container: docker logs vcc-3-backend

Local offload not working:

- Verify CLOUD_BACKEND_URL in .env is correct (no trailing slash)
- Check connectivity: curl http://<CLOUD_IP>:8000/api/health
