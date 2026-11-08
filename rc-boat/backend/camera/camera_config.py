"""
Camera and streaming configuration.
All values are overridable via environment variables.
"""
from dataclasses import dataclass
import os


@dataclass
class CameraConfig:
    """Configuration for the Raspberry Pi camera and MJPEG streaming.

    Attributes:
        enabled: Whether camera streaming is active.
        width: Frame width in pixels.
        height: Frame height in pixels.
        framerate: Target frames per second.
        jpeg_quality: JPEG compression quality (1-95, higher = better quality, larger size).
        rotation: Camera rotation in degrees (0, 90, 180, 270).
        simulation_mode: If True, generate synthetic test frames instead of using real camera.
        stream_path: HTTP path for the MJPEG stream endpoint.
        restart_delay_s: Seconds to wait before restarting camera after failure.
        max_restart_attempts: Maximum number of restart attempts before giving up.
    """
    enabled: bool = os.getenv("CAMERA_ENABLED", "true").lower() == "true"
    width: int = int(os.getenv("CAMERA_WIDTH", "640"))
    height: int = int(os.getenv("CAMERA_HEIGHT", "480"))
    framerate: int = int(os.getenv("CAMERA_FPS", "25"))
    jpeg_quality: int = int(os.getenv("CAMERA_JPEG_QUALITY", "70"))
    rotation: int = int(os.getenv("CAMERA_ROTATION", "0"))
    simulation_mode: bool = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    stream_path: str = os.getenv("CAMERA_STREAM_PATH", "/video")
    restart_delay_s: float = float(os.getenv("CAMERA_RESTART_DELAY", "2.0"))
    max_restart_attempts: int = int(os.getenv("CAMERA_MAX_RESTARTS", "5"))


# Global camera config instance
camera_config = CameraConfig()
