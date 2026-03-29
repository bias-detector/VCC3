FROM python:3.13-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend ./backend

# Copy frontend static files
COPY frontend ./frontend

# Expose FastAPI port
EXPOSE 8000

# Copy .env if present, otherwise use defaults
COPY .env .env 2>/dev/null || true

# Run the app
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
