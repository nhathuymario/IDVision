# ================================================
# IDVision AI Service — Dockerfile
# InsightFace + OpenCV + ONNX Runtime
# ================================================
FROM python:3.11-slim

# System dependencies for OpenCV and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create model directory
RUN mkdir -p /app/models/anti_spoofing

# Pre-download InsightFace models (buffalo_l ~300MB)
# This avoids downloading on first run in production
RUN python -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l'); app.prepare(ctx_id=-1, det_size=(640,640)); print('Models downloaded successfully')" || \
    echo "Model pre-download skipped (will download on first run)"

CMD ["python", "camera_stream.py"]
