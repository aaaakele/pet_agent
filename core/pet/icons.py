"""Pet icon / avatar manager — PNG and GIF support."""

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QMovie
from PySide6.QtWidgets import QLabel

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


class PetIconManager:
    """Load and apply pet avatar images (static or animated) to QLabel widgets."""

    @staticmethod
    def is_gif(path: str) -> bool:
        return Path(path).suffix.lower() == ".gif"

    @staticmethod
    def is_valid_image(path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_FORMATS

    @staticmethod
    def apply_to_label(label: QLabel, path: str, size: int = 150):
        """Set a QLabel to display a static image or animated GIF.
        Returns the QMovie reference (must be kept alive by caller for GIFs).
        """
        if PetIconManager.is_gif(path):
            movie = QMovie(path)
            movie.setScaledSize(QSize(size, size))
            label.setMovie(movie)
            movie.start()
            return movie
        else:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                # Fallback: solid color placeholder
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.gray)
            label.setPixmap(
                pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            return None
