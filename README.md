# Autoscale Lifecycle Demo

A FastAPI web app that demonstrates autoscale lifecycle behavior: local CPU stress triggers remote VM scale-up, and sustained low CPU triggers VM scale-down (delete).

## What this project demonstrates

1. CPU stress generation from local app
2. CPU threshold-based remote VM deployment (scale-up)
3. Arm-and-delete flow for scale-down when CPU stays low
4. Real-time timeline of scaling events with timestamps

## Tech stack

1. Backend: FastAPI, Python
2. Frontend: HTML, CSS, Vanilla JavaScript

## Video Demo : https://youtu.be/m3_O4pQWdaQ?si=OVDARjL-9nDXKBif

## Project structure

```text
VCC/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── constants/
│       │   └── app_constants.py
│       ├── models.py
│       ├── cpu_stress.py
│       └── __init__.py
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   └── src/
├── scripts/
│   └── deploy_gcp.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Prerequisites

### Local

1. Python 3.8+
2. pip

## Run locally

### Setup

1. Clone the repository
2. Go into the project folder:

   ```bash
   cd VCC
   ```

3. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the server:

   ```bash
   uvicorn backend.app.main:app --reload
   ```

6. Open the app:
   - App: http://127.0.0.1:8000
   - Health: http://127.0.0.1:8000/api/health
   - Scale Metrics: http://127.0.0.1:8000/api/scale/metrics

### Notes for local machine

1. App settings are in `backend/app/constants/app_constants.py`.
2. If you change constants, restart the server.

## Demo workflow

1. Click **Start Stress** to raise local CPU usage.
2. When CPU stays above threshold for configured seconds, the app triggers VM deployment.
3. Watch status transitions and timestamped events in the UI.
4. Click **Stop Stress** to arm scale-down.
5. If CPU remains below threshold for 10 seconds, the remote VM is deleted.

## Optional features

- View real-time CPU and scale state in the dashboard
- Watch live service events (with timestamps) in the UI
- View deploy script log tail directly in the UI
- Keep terminal logs visible while server is running

## API endpoints

1. `GET /api/health` - Health check
2. `GET /api/scale/metrics` - CPU, stress, scale state, UI event log, deploy log tail
3. `GET /api/scale/stress/status` - CPU stress worker status
4. `POST /api/scale/stress/start` - Start CPU stress workers
5. `POST /api/scale/stress/stop` - Stop CPU stress workers (arms scale-down if VM is active)

## Configuration

Project and scaling settings are centralized in:

- `backend/app/constants/app_constants.py`

Main values:

1. `GCP_PROJECT_ID`
2. `GCP_VM_NAME`
3. `GCP_ZONE`
4. `GCP_MACHINE_TYPE`
5. `REPO_URL`
6. `SCALE_UP_CPU_THRESHOLD`
7. `SCALE_UP_SECONDS`
8. `SCALE_POLL_SECONDS`

## See scale lifecycle live

1. Make sure Google Cloud CLI is installed and authenticated:

   ```bash
   gcloud auth login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

2. Confirm values in `backend/app/constants/app_constants.py`.

3. Start the app:

   ```bash
   uvicorn backend.app.main:app --reload
   ```

4. Open the app at `http://127.0.0.1:8000`.

5. Click **Start Stress** to push CPU usage high.

6. Watch the dashboard:
   - `Scale status` moves from `watching` to `deploying` to `scaled_up`
   - High CPU timer counts sustained above-threshold duration
   - Event timeline shows timestamped lifecycle logs
   - Deploy log tail shows recent lines from local deploy log

7. Click **Stop Stress** to arm scale-down.

8. Keep CPU below threshold for 10 seconds to trigger VM deletion.

9. Watch status move to `deleting`, then back to `watching` after delete.

10. You can also deploy manually anytime:

```bash
python3 scripts/deploy_gcp.py
```

Optional overrides:

```bash
python3 scripts/deploy_gcp.py <project_id> <vm_name> <zone> <machine_type> <repo_url>
```

## Troubleshooting

If UI buttons appear unresponsive, fully restart `uvicorn` and hard refresh the browser.

If remote VM launch fails, check local deployment logs:

```bash
tail -n 120 scripts/deploy_gcp.log
```

You can also watch logs live:

```bash
tail -f scripts/deploy_gcp.log
```
