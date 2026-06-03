"""
IDVision — Domain Exceptions
Provides specific exceptions for clean error handling across services and routers.
"""

class FaceRecognitionError(Exception):
    """Base exception for all face recognition and attendance errors."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NoFaceDetectedError(FaceRecognitionError):
    """Raised when no face is detected in the input image."""
    def __init__(self, message: str = "Không tìm thấy khuôn mặt trong ảnh."):
        super().__init__(message)


class MultipleFacesError(FaceRecognitionError):
    """Raised when multiple faces are detected in an image where only one is expected."""
    def __init__(self, message: str = "Phát hiện nhiều khuôn mặt trong ảnh. Chỉ được phép có một mặt."):
        super().__init__(message)


class FaceTooSmallError(FaceRecognitionError):
    """Raised when the detected face is too small to ensure reliable recognition."""
    def __init__(self, message: str = "Khuôn mặt quá nhỏ hoặc ở quá xa camera."):
        super().__init__(message)


class FaceQualityError(FaceRecognitionError):
    """Raised when face image quality check fails (too blurry, too dark, etc.)."""
    def __init__(self, message: str = "Chất lượng ảnh không đạt yêu cầu (mờ hoặc quá tối)."):
        super().__init__(message)


class ModelNotLoadedError(FaceRecognitionError):
    """Raised when the AI model is not initialized or failed to load."""
    def __init__(self, message: str = "Mô hình nhận diện khuôn mặt chưa được tải."):
        super().__init__(message)


class NoFaceEnrolledError(FaceRecognitionError):
    """Raised when trying to identify against an employee who has no face enrolled."""
    def __init__(self, message: str = "Nhân viên chưa được đăng ký khuôn mặt."):
        super().__init__(message)


class NoMatchFoundError(FaceRecognitionError):
    """Raised when a face is detected but does not match any enrolled employee."""
    def __init__(self, message: str = "Không nhận diện được khuôn mặt. Vui lòng thử lại."):
        super().__init__(message)


class DuplicateCheckinError(FaceRecognitionError):
    """Raised when employee attempts to check in again within the duplicate check window."""
    def __init__(self, employee_id: int, employee_name: str, minutes: int, message: str = ""):
        self.employee_id = employee_id
        self.employee_name = employee_name
        self.minutes = minutes
        msg = message or f"{employee_name} đã chấm công trong {minutes} phút gần đây."
        super().__init__(msg)


class EmbeddingFormatError(FaceRecognitionError):
    """Raised when the pre-computed embedding vector size or format is invalid."""
    def __init__(self, message: str = "Định dạng vector embedding không hợp lệ. Phải là 512 chiều."):
        super().__init__(message)
