class JobError(Exception):
    code = "PROCESSING_FAILED"
    public_message = "Gambar tidak dapat diproses. Silakan coba lagi."
    status_code = 400


class InvalidImageError(JobError):
    code = "IMAGE_CORRUPTED"
    public_message = "Gambar tidak valid. Gunakan file JPG, PNG, atau WebP yang utuh."
    status_code = 422

    def __init__(self, reason: str = "corrupt"):
        mapping = {
            "empty": ("IMAGE_CORRUPTED", "File gambar kosong atau tidak dapat dibaca."),
            "extension": ("INVALID_FILE_TYPE", "Gunakan file JPG, PNG, atau WebP."),
            "mismatch": ("INVALID_FILE_TYPE", "Ekstensi file tidak sesuai dengan isi gambar."),
            "animated": ("ANIMATED_IMAGE_NOT_SUPPORTED", "Gambar animasi belum didukung."),
            "too-small": ("IMAGE_TOO_SMALL", "Dimensi gambar terlalu kecil."),
            "too-large": ("IMAGE_TOO_LARGE", "Dimensi atau jumlah piksel gambar terlalu besar."),
            "corrupt": ("IMAGE_CORRUPTED", self.public_message),
        }
        self.code, self.public_message = mapping.get(reason, mapping["corrupt"])
        super().__init__(reason)


class FileTooLargeError(JobError):
    code = "FILE_TOO_LARGE"
    public_message = "Ukuran gambar melebihi batas yang diizinkan."
    status_code = 413


class QueueFullError(JobError):
    code = "QUEUE_FULL"
    public_message = "Antrean sedang penuh. Silakan coba beberapa saat lagi."
    status_code = 429


class RateLimitedError(JobError):
    code = "RATE_LIMITED"
    public_message = "Batas unggahan tercapai. Silakan coba lagi nanti."
    status_code = 429


class WorkerUnavailableError(JobError):
    code = "WORKER_UNAVAILABLE"
    public_message = "Pemroses gambar sedang tidak tersedia. Silakan coba lagi sebentar."
    status_code = 503


class InvalidTransitionError(JobError):
    code = "INVALID_TRANSITION"
    public_message = "Status pekerjaan tidak memungkinkan tindakan ini."
    status_code = 409
