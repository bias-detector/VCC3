# Guess the Number - Simple Game

A minimal FastAPI web application featuring a number guessing game with CPU stress testing capabilities.

## What this project demonstrates

1. Simple game logic with server-side state
2. Clean frontend-backend separation
3. CPU stress testing tools
4. Real-time metrics display

## Tech stack

1. Backend: FastAPI, Python
2. Frontend: HTML, CSS, Vanilla JavaScript

## Project structure

```text
VCC/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       ├── cpu_stress.py
│       └── __init__.py
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   └── src/
├── .env
├── .env.example
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
2. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the server:

   ```bash
   uvicorn backend.app.main:app --reload
   ```

5. Open the app:
   - App: http://127.0.0.1:8000
   - Health: http://127.0.0.1:8000/api/health
   - Metrics: http://127.0.0.1:8000/api/metrics

## How to play

1. Click **Start New Game** to begin
2. Enter a number between 1 and 100
3. The game will tell you if your guess is too high, too low, or correct
4. Try to guess the number in as few attempts as possible!

## Optional features

- Use **Start CPU Stress** to test system performance
- View real-time CPU usage in the Metrics section
- Enable simple CPU-based auto scale-up monitor (runs deploy script automatically)

## API endpoints

1. `GET /api/health` - Health check
2. `GET /api/metrics` - CPU usage and stress status
3. `POST /api/game/start` - Start a new game
4. `POST /api/game/guess` - Submit a guess
5. `POST /api/stress/start` - Start CPU stress
6. `POST /api/stress/stop` - Stop CPU stress

## Environment variables

See `.env.example` for configuration:

```bash
SERVICE_NAME=Number Guess Game
GCP_PROJECT_ID=
GCP_VM_NAME=guess-game-vm
GCP_ZONE=us-central1-a
GCP_MACHINE_TYPE=e2-medium
REPO_URL=
SCALE_UP_CPU_THRESHOLD=75
SCALE_UP_SECONDS=20
SCALE_POLL_SECONDS=1
```

## See scale-up live

1. Make sure Google Cloud CLI is installed and authenticated:

   ```bash
   gcloud auth login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

2. Set `GCP_PROJECT_ID` in `.env`:

   ```bash
   GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
   ```

3. (Optional) Set your repository URL if needed by the VM startup script:

   ```bash
   REPO_URL=https://github.com/YOUR_USER/VCC.git
   ```

4. Start the app:

   ```bash
   uvicorn backend.app.main:app --reload
   ```

5. Open the app at `http://127.0.0.1:8000`.

6. Click **Start** in Stress Test to push CPU usage high.

7. Watch the top-right metrics card:
   - `Scale monitor` should be `ON`
   - `Scale status` moves from `watching` to `deploying` to `scaled_up`
   - `Timer` counts sustained high CPU duration
   - `Scale message` shows progress and remote URL when available

8. You can also deploy manually anytime:

   ```bash
   python3 scripts/deploy_gcp.py YOUR_GCP_PROJECT_ID
   ```
