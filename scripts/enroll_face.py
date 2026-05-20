"""
IDVision — Face Enrollment Script
CLI tool to register an employee's face from webcam or image files.

Usage:
    # From webcam (captures 5 photos with countdown):
    python enroll_face.py --employee-id 1 --source webcam

    # From image files:
    python enroll_face.py --employee-id 1 --source files --images photo1.jpg photo2.jpg

    # With custom backend URL:
    python enroll_face.py --employee-id 1 --source webcam --backend-url http://localhost:8000
"""

import argparse
import asyncio
import base64
import sys
import time

import cv2
import httpx
import numpy as np


async def enroll_from_webcam(
    employee_id: int,
    backend_url: str,
    num_captures: int = 5,
    camera_index: int = 0,
) -> None:
    """Capture face photos from webcam and enroll via API."""
    print(f"\n{'='*60}")
    print(f"  IDVision — Face Enrollment (Webcam)")
    print(f"  Employee ID: {employee_id}")
    print(f"  Capturing {num_captures} photos")
    print(f"{'='*60}\n")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("❌ Failed to open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("📷 Webcam opened. Position your face in front of the camera.")
    print("   Press 'q' to quit at any time.\n")

    captured_images = []

    for i in range(num_captures):
        instruction = ""
        if i == 0:
            instruction = "Look straight ahead (no mask)"
        elif i == 1:
            instruction = "Look slightly left"
        elif i == 2:
            instruction = "Look slightly right"
        elif i == 3:
            instruction = "With mask — look straight"
        elif i == 4:
            instruction = "With mask — slight angle"

        print(f"\n📸 Photo {i+1}/{num_captures}: {instruction}")

        # Countdown
        for countdown in range(3, 0, -1):
            print(f"   Capturing in {countdown}...", end="\r")

            # Show live preview during countdown
            for _ in range(10):  # ~1 second of preview frames
                ret, frame = cap.read()
                if ret:
                    # Draw countdown on frame
                    display = frame.copy()
                    cv2.putText(
                        display,
                        f"Photo {i+1}/{num_captures}: {instruction}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
                    )
                    cv2.putText(
                        display,
                        str(countdown),
                        (frame.shape[1]//2 - 30, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5,
                    )
                    cv2.imshow("IDVision Enrollment", display)

                key = cv2.waitKey(100)
                if key == ord('q'):
                    print("\n\n⏹️ Enrollment cancelled.")
                    cap.release()
                    cv2.destroyAllWindows()
                    return

        # Capture the actual photo
        ret, frame = cap.read()
        if ret:
            captured_images.append(frame)
            # Flash effect
            white = np.ones_like(frame) * 255
            cv2.imshow("IDVision Enrollment", white.astype(np.uint8))
            cv2.waitKey(100)
            cv2.imshow("IDVision Enrollment", frame)
            cv2.waitKey(500)
            print(f"   ✅ Photo {i+1} captured!")
        else:
            print(f"   ❌ Failed to capture photo {i+1}")

    cap.release()
    cv2.destroyAllWindows()

    if not captured_images:
        print("\n❌ No photos captured.")
        return

    # Send to backend
    await _upload_images(employee_id, backend_url, captured_images)


async def enroll_from_files(
    employee_id: int,
    backend_url: str,
    image_paths: list[str],
) -> None:
    """Enroll from image files via API."""
    print(f"\n{'='*60}")
    print(f"  IDVision — Face Enrollment (Files)")
    print(f"  Employee ID: {employee_id}")
    print(f"  Images: {len(image_paths)}")
    print(f"{'='*60}\n")

    images = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is None:
            print(f"⚠️ Cannot read: {path}")
            continue
        images.append(img)
        print(f"  ✅ Loaded: {path}")

    if not images:
        print("\n❌ No valid images found.")
        return

    await _upload_images(employee_id, backend_url, images)


async def _upload_images(
    employee_id: int,
    backend_url: str,
    images: list[np.ndarray],
) -> None:
    """Upload captured images to the enrollment API."""
    print(f"\n📤 Uploading {len(images)} images to {backend_url}...")

    async with httpx.AsyncClient(base_url=backend_url, timeout=60.0) as client:
        # Prepare multipart files
        files = []
        for i, img in enumerate(images):
            _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            files.append(
                ("images", (f"face_{i+1}.jpg", buffer.tobytes(), "image/jpeg"))
            )

        try:
            response = await client.post(
                f"/api/enrollment/{employee_id}",
                files=files,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"\n{'='*60}")
                print(f"  ✅ ENROLLMENT SUCCESSFUL")
                print(f"  Employee: {result['employee_name']}")
                print(f"  Faces processed: {result['num_faces_processed']}/{len(images)}")
                print(f"  Enrolled at: {result['enrolled_at']}")
                print(f"  Message: {result['message']}")
                print(f"{'='*60}")
            else:
                error = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                print(f"\n❌ Enrollment failed (HTTP {response.status_code}):")
                print(f"   {error}")

        except httpx.ConnectError:
            print(f"\n❌ Cannot connect to backend at {backend_url}")
            print("   Make sure the backend server is running.")
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="IDVision — Face Enrollment Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enroll_face.py --employee-id 1 --source webcam
  python enroll_face.py --employee-id 1 --source webcam --num-captures 3
  python enroll_face.py --employee-id 1 --source files --images photo1.jpg photo2.jpg photo3.jpg
  python enroll_face.py --employee-id 1 --source webcam --backend-url http://localhost:8000
        """
    )

    parser.add_argument(
        "--employee-id", type=int, required=True,
        help="Employee ID to enroll face for."
    )
    parser.add_argument(
        "--source", choices=["webcam", "files"], default="webcam",
        help="Image source: webcam capture or file upload."
    )
    parser.add_argument(
        "--images", nargs="+",
        help="Image file paths (required when --source=files)."
    )
    parser.add_argument(
        "--num-captures", type=int, default=5,
        help="Number of photos to capture from webcam (default: 5)."
    )
    parser.add_argument(
        "--camera-index", type=int, default=0,
        help="Webcam index (default: 0)."
    )
    parser.add_argument(
        "--backend-url", default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)."
    )

    args = parser.parse_args()

    if args.source == "files" and not args.images:
        parser.error("--images is required when --source=files")

    if args.source == "webcam":
        asyncio.run(enroll_from_webcam(
            employee_id=args.employee_id,
            backend_url=args.backend_url,
            num_captures=args.num_captures,
            camera_index=args.camera_index,
        ))
    else:
        asyncio.run(enroll_from_files(
            employee_id=args.employee_id,
            backend_url=args.backend_url,
            image_paths=args.images,
        ))


if __name__ == "__main__":
    main()
