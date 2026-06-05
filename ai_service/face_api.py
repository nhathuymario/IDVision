import os
import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException
from dotenv import load_dotenv
from ai_service.db import fetch_all_embeddings
import insightface

load_dotenv()

router = APIRouter()

# Load model once (lazy)
_face_app = None

def get_face_app():
    global _face_app
    if _face_app is None:
        _face_app = insightface.app.FaceAnalysis(name='antelope')
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app

@router.post("/attendance/recognize")
async def recognize(file: UploadFile = File(...)):
    content = await file.read()
    img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")
    app = get_face_app()
    faces = app.detectors[0].detect(img)
    if faces.shape[0] == 0:
        raise HTTPException(status_code=404, detail="No face detected")
    # Use first face
    emb = app.models[0].get_feat(img, faces[0][:4])
    emb = emb / np.linalg.norm(emb)
    # Compare with DB embeddings
    best_id = None
    best_sim = -1.0
    for emp_id, stored_blob in await fetch_all_embeddings():
        stored = np.frombuffer(stored_blob, dtype=np.float32)
        sim = float(np.dot(emb, stored))
        if sim > best_sim:
            best_sim = sim
            best_id = emp_id
    threshold = float(os.getenv("FACE_THRESHOLD", "0.45"))
    if best_sim >= threshold:
        return {"employee_id": best_id, "similarity": best_sim}
    return {"msg": "Similarity below threshold", "similarity": best_sim}
