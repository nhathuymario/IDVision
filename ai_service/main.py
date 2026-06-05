import asyncio
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from contextlib import asynccontextmanager

from face_detector import FaceDetector
from camera_stream import CameraStreamProcessor

# Create global instances
face_detector = FaceDetector(ctx_id=-1)
camera_processor = CameraStreamProcessor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize detector for FastAPI endpoints
    face_detector.initialize()
    
    # 2. Start camera processor in the background
    async def run_camera():
        try:
            await camera_processor.initialize()
            await camera_processor.run()
        except Exception as e:
            import logging
            logging.getLogger("ai_service").error(f"Background camera processor error: {e}")
            
    camera_task = asyncio.create_task(run_camera())
    
    yield
    
    # Shutdown camera processor
    camera_processor.stop()
    try:
        await camera_processor.cleanup()
    except Exception:
        pass
    camera_task.cancel()

app = FastAPI(title="IDVision AI API", version="1.0.0", lifespan=lifespan)

@app.post("/extract-embedding")
async def extract_embedding(file: UploadFile = File(...)):
    """Extract face embedding from uploaded image."""
    try:
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file.")
        
        # Preprocess frame
        img = FaceDetector.preprocess_frame(img)
        
        # Extract embedding
        result = face_detector.extract_single(img)
        if result is None:
            raise HTTPException(status_code=404, detail="No face detected in the image.")
            
        return {
            "embedding": result.embedding.tolist(),
            "det_score": result.det_score,
            "bbox": result.bbox
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "healthy"}
