# Production-like image of the whole app (Flask backend serving the frontend).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt gunicorn==23.0.0

COPY backend backend
COPY frontend frontend

EXPOSE 8000
# One worker: data is still kept in memory, so every request must reach the same process.
# Set AGROUP_SECRET_KEY when starting the container so login sessions survive restarts.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "backend.server:create_app()"]
