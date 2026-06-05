# Tổng quan công nghệ & dataset cho hệ thống chấm công khuôn mặt (IDVision)

## 1. Kiến trúc tổng thể
- **Frontend**: React + Vite (đã có trong dự án) – giao diện check‑in, admin dashboard.
- **Backend**: FastAPI (Python) – cung cấp API REST, xử lý ảnh, lưu trữ dữ liệu.
- **Cơ sở dữ liệu**: PostgreSQL (Docker) – lưu thông tin nhân viên, lịch sử chấm công, và **bảng `employee_embeddings`** để lưu vector khuôn mặt (BYTEA).
- **AI Service** (`ai_service`):
  - **InsightFace** – mô hình ArcFace/ResNet‑50 dùng để trích xuất embedding khuôn mặt, hỗ trợ nhận diện khẩu trang.
  - **OpenCV** – phát hiện khuôn mặt (RetinaFace) và tiền xử lý ảnh.
  - **AsyncPG** – kết nối bất đồng bộ tới PostgreSQL để truy vấn/ghi embedding.
  - **Telegram Bot** – thông báo thời gian thực (đã tồn tại trong dự án).

## 2. Công nghệ chính
| Thành phần | Thư viện / công cụ | Phiên bản (tại thời điểm) |
|------------|-------------------|----------------------------|
| **Web framework** | FastAPI | `0.115.6` |
| **Mô hình nhận diện** | InsightFace (ArcFace, ResNet‑50) | `insightface` (latest) |
| **Xử lý ảnh** | OpenCV‑Python‑Headless | `4.10.0.84` |
| **Đồ họa PDF** | ReportLab (được dùng trong `salary_pdf.py`) | `3.6.12` |
| **Telegram Bot** | python‑telegram‑bot | `21.5` |
| **Cơ sở dữ liệu** | PostgreSQL + pgvector (để lưu vector) | PostgreSQL `15`, pgvector `0.4` |
| **Quản lý môi trường** | python‑dotenv | `1.0.1` |
| **Kiểm thử** | pytest, httpx | `7.4.0`, `0.28.1` |

## 3. Dataset được sử dụng
| Dataset | Mô tả | Số ảnh (ước tính) | Đường dẫn trong project |
|--------|------|-------------------|------------------------|
| **LFW (Labeled Faces in the Wild)** | 13 k ảnh, đa góc, không khẩu trang. | ~13 000 | `data/lfw/` (được tải qua `download_datasets.bat`) |
| **MAFA (Masked Face Dataset)** | 30 k ảnh mặt có khẩu trang, chuẩn cho nhận dạng khẩu trang. | ~30 000 | `data/mafa/` (được clone) |
| **Synthetic mask (optional)** | Tạo khẩu trang cho ảnh LFW bằng `MaskTheFace`. | tùy tạo | `data/mask_the_face/` (không bắt buộc) |

## 4. Quy trình dữ liệu (pipeline)
1. **Tải dataset** – chạy `scripts\download_datasets.bat`.
2. **Tạo dataset nhỏ** – script `scripts\create_small_dataset.py` chọn ~5 ảnh/đối tượng từ LFW và MAFA, chia train/val (~200‑300 ảnh).
3. **Huấn luyện** – `scripts\train_face_recognition.py` sử dụng InsightFace Trainer, lưu checkpoint `models/face_arcface_finetuned.pth`.
4. **Tạo embedding cho nhân viên** – `scripts\embed_employee.py` (cung cấp ảnh nhân viên) → lưu vào PostgreSQL table `employee_embeddings`.
5. **API nhận diện** – `ai_service/face_api.py`:
   - Nhận file ảnh POST `/attendance/recognize`.
   - Phát hiện mặt, trích xuất embedding, so sánh cosine với các embedding trong DB.
   - Trả về `employee_id` nếu similarity ≥ `FACE_THRESHOLD` (0.45).
6. **Kiểm thử** – `tests/test_face_api.py` gửi ảnh mẫu và kiểm tra phản hồi JSON.

## 5. Các file quan trọng
- `scripts/download_datasets.bat` – tải LFW & MAFA.
- `scripts/create_small_dataset.py` – tạo tập nhẹ.
- `scripts/train_face_recognition.py` – huấn luyện mô hình.
- `ai_service/db.py` – helper asyncpg cho PostgreSQL.
- `ai_service/face_api.py` – router FastAPI.
- `backend/main.py` – đã include router `face_api`.
- `scripts/init_embeddings_table.sql` – tạo bảng `employee_embeddings`.
- `scripts/embed_employee.py` – tạo embedding cho mỗi nhân viên.
- `tests/test_face_api.py` – kiểm thử endpoint.

## 6. Hướng dẫn nhanh chạy toàn bộ pipeline (một lệnh)
```cmd
cd e:\IDVision
scripts\download_datasets.bat
python scripts\create_small_dataset.py --src-lfw data\lfw --src-mafa data\mafa --dst data\small --max-per-id 5 --val-ratio 0.2
python scripts\train_face_recognition.py --train-dir data\small\train --val-dir data\small\val --output models\face_arcface_finetuned.pth --epochs 10
psql %DATABASE_URL% -f scripts\init_embeddings_table.sql
# Thêm embedding cho một nhân viên (ví dụ)
python scripts\embed_employee.py --emp-id 001 --img path\to\photo.jpg
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 7. Tham khảo & link tải
- **LFW**: https://github.com/AKSHAYUBHAT/TensorFace/raw/master/data/lfw.tgz
- **MAFA**: https://github.com/prajnasb/observations
- **InsightFace**: https://github.com/deepinsight/insightface
- **MaskTheFace** (tùy chọn): https://github.com/kuangliu/MaskTheFace

---
*File này được tạo để bạn có thể trình bày công nghệ và dataset cho các bên liên quan hoặc tư vấn khách hàng.*
