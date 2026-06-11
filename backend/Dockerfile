# ================================================
# IDVision Backend — Dockerfile
# FastAPI + SQLAlchemy + pgvector
# ================================================
FROM python:3.11-slim

# System dependencies for psycopg2, OpenCV, and InsightFace build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download InsightFace models (buffalo_l ~300MB)
RUN python -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l'); app.prepare(ctx_id=-1, det_size=(640,640)); print('Models downloaded successfully')" || \
    echo "Model pre-download skipped (will download on first run)"

# Copy application code
COPY . .

# Create snapshots directory
RUN mkdir -p /app/snapshots

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
