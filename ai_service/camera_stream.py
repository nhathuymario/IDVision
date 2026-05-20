"""
IDVision — Camera Stream Processor
Captures frames from camera/RTSP, detects faces, and sends to Backend API.

This is the main loop of the AI service:
1. Capture frame from camera
2. Detect motion (optional optimization)
3. Detect faces using InsightFace
4. Check liveness (anti-spoofing)
5. Send embedding to Backend API for recognition
"""

import asyncio
import base64
import logging
import os
import signal
import sys
import time
from typing import Optional

import cv2
import httpx
import numpy as np
from dotenv import load_dotenv

from face_detector import FaceDetector
from liveness import LivenessDetector

# Load environment variables
load_dotenv()

# ── Configuration ───────────────────────────────────────────
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
ANTI_SPOOFING_ENABLED = os.getenv("ANTI_SPOOFING_ENABLED", "true").lower() == "true"
LIVENESS_THRESHOLD = float(os.getenv("LIVENESS_THRESHOLD", "0.5"))

# Processing settings
PROCESS_EVERY_N_FRAMES = 3          # Process every Nth frame (skip for speed)
MIN_DETECTION_INTERVAL = 3.0        # Min seconds between recognition requests per face
MOTION_THRESHOLD = 25               # Pixel change threshold for motion detection
MIN_FACE_SIZE = 60                  # Minimum face size in pixels to process
RECONNECT_DELAY = 5                 # Seconds to wait before reconnecting camera

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_service")


class CameraStreamProcessor:
    """
    Main camera processing loop.
    
    Captures frames, detects faces, checks liveness,
    and sends embeddings to Backend for recognition.
    """

    def __init__(self):
        self._face_detector = FaceDetector(ctx_id=-1)  # CPU mode by default
        self._liveness_detector = LivenessDetector(threshold=LIVENESS_THRESHOLD)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._running = False
        self._prev_frame_gray: Optional[np.ndarray] = None
        self._last_recognition_time: dict[str, float] = {}  # Track per-face cooldown

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info("🚀 IDVision AI Service — Initializing...")
        logger.info("=" * 60)

        # Initialize face detector
        self._face_detector.initialize()
        logger.info("✅ Face detector ready (InsightFace buffalo_l)")

        # Initialize liveness detector
        if ANTI_SPOOFING_ENABLED:
            if self._liveness_detector.initialize():
                logger.info("✅ Liveness detector ready (MiniFASNet)")
            else:
                logger.warning("⚠️ Liveness detector using heuristic fallback")
        else:
            logger.info("ℹ️ Anti-spoofing is disabled")

        # HTTP client for Backend API calls
        self._http_client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=10.0,
        )

        # Verify backend connection
        await self._wait_for_backend()

        logger.info(f"📷 Camera source: {CAMERA_SOURCE}")
        logger.info(f"🌐 Backend URL: {BACKEND_URL}")
        logger.info("=" * 60)

    async def _wait_for_backend(self, max_retries: int = 30) -> None:
        """Wait for backend to be ready before starting camera loop."""
        for attempt in range(max_retries):
            try:
                resp = await self._http_client.get("/health")
                if resp.status_code == 200:
                    logger.info("✅ Backend API is reachable")
                    return
            except Exception:
                pass
            logger.info(f"Waiting for backend... (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(2)

        logger.error("❌ Backend not reachable. Starting anyway...")

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        """Open camera/RTSP stream with error handling."""
        # Try to parse as integer (webcam index)
        try:
            source = int(CAMERA_SOURCE)
        except ValueError:
            source = CAMERA_SOURCE  # RTSP URL

        logger.info(f"Opening camera: {source}")
        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            logger.error(f"Failed to open camera: {source}")
            return None

        # Set camera properties for better quality
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Camera opened: {actual_w}x{actual_h}")

        return cap

    def _detect_motion(self, frame: np.ndarray) -> bool:
        """
        Simple motion detection using frame differencing.
        Reduces unnecessary face detection on static scenes.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_frame_gray is None:
            self._prev_frame_gray = gray
            return True  # Process first frame

        # Frame difference
        delta = cv2.absdiff(self._prev_frame_gray, gray)
        thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
        motion_pixels = np.sum(thresh > 0)
        total_pixels = thresh.size
        motion_ratio = motion_pixels / total_pixels

        self._prev_frame_gray = gray

        # Consider motion if > 1% of pixels changed
        return motion_ratio > 0.01

    def _get_face_key(self, bbox: list[int]) -> str:
        """Generate a rough position key for face cooldown tracking."""
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        # Quantize to 100px grid to group same-person detections
        return f"{cx // 100}_{cy // 100}"

    def _check_cooldown(self, face_key: str) -> bool:
        """Check if enough time has passed since last recognition for this face position."""
        now = time.time()
        last_time = self._last_recognition_time.get(face_key, 0)
        if now - last_time < MIN_DETECTION_INTERVAL:
            return False  # Still in cooldown
        self._last_recognition_time[face_key] = now
        return True

    async def _send_recognition_request(
        self,
        embedding: np.ndarray,
        is_live: bool,
        liveness_score: float,
        face_image: Optional[np.ndarray] = None,
    ) -> Optional[dict]:
        """Send face embedding to Backend API for recognition."""
        try:
            # Encode snapshot as base64
            snapshot_b64 = None
            if face_image is not None:
                _, buffer = cv2.imencode(".jpg", face_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                snapshot_b64 = base64.b64encode(buffer).decode("utf-8")

            payload = {
                "embedding": embedding.tolist(),
                "is_live": is_live,
                "liveness_score": liveness_score,
                "snapshot_base64": snapshot_b64,
            }

            response = await self._http_client.post(
                "/api/attendance/recognize",
                json=payload,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("recognized"):
                    logger.info(
                        f"✅ Recognized: {result['employee_name']} | "
                        f"Status: {result.get('status')} | "
                        f"Similarity: {result.get('similarity', 0):.4f}"
                    )
                else:
                    logger.debug(f"Not recognized: {result.get('message')}")
                return result
            else:
                logger.warning(f"Backend returned {response.status_code}: {response.text}")
                return None

        except httpx.TimeoutException:
            logger.warning("Backend request timeout")
            return None
        except Exception as e:
            logger.error(f"Recognition request failed: {e}")
            return None

    async def run(self) -> None:
        """Main camera processing loop."""
        self._running = True
        frame_count = 0

        while self._running:
            cap = self._open_camera()
            if cap is None:
                logger.error(f"Retrying camera in {RECONNECT_DELAY}s...")
                await asyncio.sleep(RECONNECT_DELAY)
                continue

            logger.info("📷 Camera stream started. Processing...")

            try:
                while self._running:
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning("Failed to read frame. Reconnecting...")
                        break

                    frame_count += 1

                    # Skip frames for performance
                    if frame_count % PROCESS_EVERY_N_FRAMES != 0:
                        continue

                    # Motion detection (skip static scenes)
                    if not self._detect_motion(frame):
                        continue

                    # Preprocess frame
                    processed_frame = FaceDetector.preprocess_frame(frame)

                    # Detect faces
                    faces = self._face_detector.detect_faces(processed_frame)
                    if not faces:
                        continue

                    # Process each detected face
                    for face in faces:
                        # Skip small faces (too far from camera)
                        bbox_w = face.bbox[2] - face.bbox[0]
                        bbox_h = face.bbox[3] - face.bbox[1]
                        if bbox_w < MIN_FACE_SIZE or bbox_h < MIN_FACE_SIZE:
                            continue

                        # Check cooldown (rate limiting per face position)
                        face_key = self._get_face_key(face.bbox)
                        if not self._check_cooldown(face_key):
                            continue

                        # Liveness check
                        is_live = True
                        liveness_score = 1.0
                        if ANTI_SPOOFING_ENABLED and face.face_image is not None:
                            is_live, liveness_score = self._liveness_detector.check(
                                face.face_image
                            )
                            if not is_live:
                                logger.warning(
                                    f"⛔ Spoofing detected! Score: {liveness_score:.3f}"
                                )
                                continue

                        # Send to backend for recognition
                        await self._send_recognition_request(
                            embedding=face.embedding,
                            is_live=is_live,
                            liveness_score=liveness_score,
                            face_image=face.face_image,
                        )

                    # Small delay to prevent CPU overload
                    await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Camera loop error: {e}", exc_info=True)
            finally:
                cap.release()
                logger.info("Camera released.")

            if self._running:
                logger.info(f"Reconnecting camera in {RECONNECT_DELAY}s...")
                await asyncio.sleep(RECONNECT_DELAY)

    def stop(self) -> None:
        """Signal the processing loop to stop."""
        logger.info("Stop signal received.")
        self._running = False

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()


async def main():
    """Entry point for the AI service."""
    processor = CameraStreamProcessor()

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        processor.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler())

    try:
        await processor.initialize()
        await processor.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        await processor.cleanup()
        logger.info("AI Service shut down.")


if __name__ == "__main__":
    asyncio.run(main())
