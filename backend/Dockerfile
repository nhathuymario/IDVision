# ================================================
# IDVision Backend — Dockerfile
# FastAPI + SQLAlchemy + pgvector
# ================================================
FROM python:3.11-slim

# System dependencies for psycopg2 and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create snapshots directory
RUN mkdir -p /app/snapshots

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
