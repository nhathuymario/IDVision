# 🎯 IDVision — Hệ Thống Chấm Công Bằng Nhận Diện Khuôn Mặt AI

Hệ thống chấm công thời gian thực sử dụng nhận diện khuôn mặt AI, hỗ trợ nhận diện khuôn mặt đeo khẩu trang, chống giả mạo (anti-spoofing), và thông báo real-time qua Telegram.

## 🏗️ Kiến Trúc

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   📷 Camera     │────▶│   AI Service     │────▶│   FastAPI Backend   │
│   (Webcam/RTSP) │     │  • InsightFace   │     │  • Face Matching    │
│                 │     │  • Anti-Spoofing  │     │  • Attendance Log   │
│                 │     │  • Motion Detect  │     │  • Telegram Bot     │
└─────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                            │
                                                 ┌──────────┴──────────┐
                                                 │                     │
                                          ┌──────▼──────┐    ┌────────▼────────┐
                                          │ PostgreSQL  │    │  🤖 Telegram    │
                                          │ + pgvector  │    │  Notification   │
                                          └─────────────┘    └─────────────────┘
```

## 🛠️ Công Nghệ

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Face Detection** | InsightFace (SCRFD) | Phát hiện khuôn mặt, kể cả đeo khẩu trang |
| **Face Recognition** | ArcFace (512-dim) | Trích xuất đặc trưng khuôn mặt thành vector |
| **Anti-Spoofing** | MiniFASNet (ONNX) | Chống giả mạo bằng ảnh/video |
| **Backend API** | FastAPI (async) | Xử lý logic, REST API |
| **Database** | PostgreSQL + pgvector | Lưu trữ vector khuôn mặt, attendance logs |
| **Notification** | Telegram Bot API | Thông báo real-time |
| **Deployment** | Docker Compose | Đóng gói và triển khai |

## 🚀 Hướng Dẫn Cài Đặt

### Yêu Cầu
- Docker & Docker Compose
- Webcam hoặc camera IP (RTSP)
- Telegram Bot Token (tạo qua [@BotFather](https://t.me/BotFather))

### 1. Clone & Cấu Hình

```bash
cd IDVision

# Copy và chỉnh sửa file cấu hình
cp .env.example .env
# Sửa .env: điền TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PASSWORD
```

### 2. Khởi Chạy

```bash
# Build và start tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f

# Kiểm tra status
docker-compose ps
```

### 3. Đăng Ký Nhân Viên

```bash
# Tạo nhân viên qua API
curl -X POST http://localhost:8000/api/employees \
  -H "Content-Type: application/json" \
  -d '{"name": "Nguyễn Nhất Huy", "employee_code": "NV001", "telegram_chat_id": "123456789"}'

# Đăng ký khuôn mặt bằng script (từ webcam)
python scripts/enroll_face.py --employee-id 1 --source webcam

# Hoặc từ file ảnh
python scripts/enroll_face.py --employee-id 1 --source files --images photo1.jpg photo2.jpg photo3.jpg
```

### 4. Kiểm Tra

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Attendance hôm nay**: http://localhost:8000/api/attendance/today

## 📁 Cấu Trúc Dự Án

```
IDVision/
├── docker-compose.yml          # Docker orchestration
├── .env.example                # Environment template
├── README.md
│
├── backend/                    # FastAPI Backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # App entry point + lifespan
│   ├── config.py               # Pydantic settings
│   ├── database.py             # SQLAlchemy async + pgvector
│   ├── models.py               # ORM models
│   ├── schemas.py              # Pydantic request/response
│   ├── routers/
│   │   ├── employees.py        # CRUD nhân viên
│   │   ├── enrollment.py       # Đăng ký khuôn mặt
│   │   └── attendance.py       # Chấm công + báo cáo
│   └── services/
│       ├── face_cache.py       # In-memory face cache (numpy)
│       ├── matcher.py          # Vector matching logic
│       └── telegram_bot.py     # Telegram notification
│
├── ai_service/                 # AI/Vision Module
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── face_detector.py        # InsightFace wrapper
│   ├── liveness.py             # Anti-spoofing
│   ├── camera_stream.py        # Camera capture + processing
│   └── models/                 # AI model files (auto-download)
│
├── db/
│   └── init.sql                # PostgreSQL schema + pgvector
│
├── scripts/
│   └── enroll_face.py          # Face enrollment CLI
│
└── snapshots/                  # Check-in face snapshots
```

## 🔧 Cấu Hình

| Biến Môi Trường | Mặc Định | Mô Tả |
|---|---|---|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `TELEGRAM_BOT_TOKEN` | - | Token từ BotFather |
| `TELEGRAM_CHAT_ID` | - | Group chat ID nhận thông báo |
| `SIMILARITY_THRESHOLD` | `0.55` | Ngưỡng cosine similarity (0.0-1.0) |
| `LATE_THRESHOLD_HOUR` | `8` | Giờ vào ca |
| `DUPLICATE_CHECK_MINUTES` | `30` | Chống chấm công trùng (phút) |
| `ANTI_SPOOFING_ENABLED` | `true` | Bật/tắt anti-spoofing |
| `CAMERA_SOURCE` | `0` | Webcam index hoặc RTSP URL |

## 📡 API Endpoints

### Employees
| Method | Endpoint | Mô Tả |
|--------|----------|--------|
| `POST` | `/api/employees` | Tạo nhân viên |
| `GET` | `/api/employees` | Danh sách (có phân trang) |
| `GET` | `/api/employees/{id}` | Chi tiết nhân viên |
| `PUT` | `/api/employees/{id}` | Cập nhật |
| `DELETE` | `/api/employees/{id}` | Vô hiệu hóa (soft delete) |

### Enrollment
| Method | Endpoint | Mô Tả |
|--------|----------|--------|
| `POST` | `/api/enrollment/{id}` | Upload ảnh đăng ký khuôn mặt |
| `POST` | `/api/enrollment/{id}/embedding` | Đăng ký bằng embedding vector |
| `DELETE` | `/api/enrollment/{id}` | Xóa đăng ký |

### Attendance
| Method | Endpoint | Mô Tả |
|--------|----------|--------|
| `POST` | `/api/attendance/recognize` | **Core** — Nhận diện và chấm công |
| `GET` | `/api/attendance/today` | Danh sách chấm công hôm nay |
| `GET` | `/api/attendance/report` | Báo cáo theo khoảng thời gian |
| `GET` | `/api/attendance/stats/today` | Thống kê hôm nay |

### Admin
| Method | Endpoint | Mô Tả |
|--------|----------|--------|
| `POST` | `/api/cache/refresh` | Refresh face cache từ DB |
| `GET` | `/health` | Health check |

## 🔔 Telegram Notification

Khi nhân viên chấm công, bot sẽ gửi thông báo:

```
✅ [IDVision] Nhân viên Nguyễn Nhất Huy đã chấm công thành công.
🕐 Giờ vào ca: 08:15:00 ngày 20/05/2026
📊 Độ chính xác: 92.3%
```

Nếu đến trễ:
```
⚠️ [IDVision] Nhân viên Nguyễn Nhất Huy đến trễ.
🕐 Giờ vào: 08:45:00 ngày 20/05/2026
⏰ Trễ: 45 phút
📊 Độ chính xác: 89.1%
```

## ⚙️ Tối Ưu Performance

- **Face Cache**: Toàn bộ face encodings được cache trên RAM (~2MB cho 1000 NV). Matching bằng numpy vectorized cosine similarity < 1ms
- **Motion Detection**: Chỉ xử lý khi phát hiện chuyển động, giảm tải CPU
- **Frame Skipping**: Xử lý mỗi frame thứ 3, rate limit 3s/người
- **HNSW Index**: pgvector approximate nearest neighbor cho fallback queries

## 🧯 Troubleshooting nhanh

- **Loi `password authentication failed for user "idvision"`**
  - Thuong do da doi `DB_PASSWORD` trong `.env` sau khi volume Postgres da duoc tao truoc do.
  - **Giu du lieu cu**: doi mat khau user `idvision` trong PostgreSQL cho khop voi `.env`.
    - Neu dung Docker Compose:

```bash
docker compose exec -u postgres db psql -d postgres -c "ALTER USER idvision WITH PASSWORD '123456';"
```

    - Neu Postgres dang chay local tren Windows:

```sql
ALTER USER idvision WITH PASSWORD '123456';
```

  - Sau do restart backend.
  - Cach reset sach DB (mat du lieu cu):

```bash
docker compose down -v
docker compose up -d
```

- **Canh bao NumPy tren Windows (MINGW-W64 experimental)**
  - Day la warning, khong phai loi ket noi DB.
  - Moi truong production nen uu tien chay bang Docker de tranh sai khac binary tren Windows.

## 📝 License

Internal use only — IDVision Attendance System
