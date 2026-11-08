"""
Camera Controller — Picamera2 + simulation fallback.

Captures JPEG frames continuously into an asyncio.Queue.
The streaming service reads from this queue and pushes frames
to HTTP clients without blocking the motor-control event loop.

Frame capture runs in a separate thread (ThreadPoolExecutor) to
avoid blocking asyncio. The queue is bounded (maxsize=2) to drop
stale frames immediately — this minimises latency.
"""

import asyncio
import io
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from camera.camera_config import CameraConfig

logger = logging.getLogger(__name__)

# One shared executor for all camera I/O
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="camera")


class CameraController:
    """Manages camera capture and exposes frames via an asyncio queue.

    On real hardware (Linux, picamera2 installed):
        Uses Picamera2 to capture JPEG frames at the configured resolution
        and frame rate. Frames are encoded to JPEG in the capture thread.

    In simulation mode:
        Generates synthetic frames (coloured gradient + timestamp text)
        using Pillow. No GPIO or camera hardware is used.

    Usage::

        cam = CameraController(config)
        await cam.initialize_camera()
        frame_bytes = await cam.capture_frame()   # wait for next JPEG
        await cam.stop_camera()
    """

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._running = False
        self._initialized = False
        self._frame_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._capture_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._restart_attempts = 0
        self._picam2 = None  # Picamera2 instance (hardware only)
        self._sim_frame_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initialize_camera(self) -> None:
        """Initialize the camera and start frame capture.

        In simulation mode this starts the synthetic frame generator.
        On real hardware this opens Picamera2, configures the sensor,
        and starts the capture pipeline.

        Raises:
            RuntimeError: If initialization fails and simulation fallback
                          is also unavailable.
        """
        if self._initialized:
            logger.warning("Camera already initialized")
            return

        self._loop = asyncio.get_running_loop()
        self._running = True

        if self._config.simulation_mode:
            logger.info(
                "[CAM-SIM] Starting synthetic camera %dx%d @ %d fps",
                self._config.width,
                self._config.height,
                self._config.framerate,
            )
            self._start_capture_thread(self._sim_capture_loop)
        else:
            logger.info(
                "[CAM-HW] Initializing Picamera2 %dx%d @ %d fps",
                self._config.width,
                self._config.height,
                self._config.framerate,
            )
            try:
                await asyncio.get_running_loop().run_in_executor(
                    _executor, self._init_picamera2
                )
                self._start_capture_thread(self._hw_capture_loop)
            except Exception as exc:
                logger.error("Picamera2 initialization failed: %s", exc)
                logger.warning("Falling back to simulation mode")
                self._config = CameraConfig(
                    **{**self._config.__dict__, "simulation_mode": True}
                )
                self._start_capture_thread(self._sim_capture_loop)

        self._initialized = True
        logger.info("Camera initialized successfully")

    async def capture_frame(self) -> bytes:
        """Wait for and return the next JPEG frame.

        This coroutine blocks until a frame is available. In normal
        operation frames arrive at approximately the configured FPS.

        Returns:
            Raw JPEG bytes ready to send as an HTTP MJPEG chunk.
        """
        return await self._frame_queue.get()

    async def stop_camera(self) -> None:
        """Stop frame capture and release camera resources."""
        if not self._running:
            return

        logger.info("Stopping camera …")
        self._running = False

        # Wake up any blocked capture_frame() calls
        try:
            self._frame_queue.put_nowait(b"")
        except asyncio.QueueFull:
            pass

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=5.0)
            self._capture_thread = None

        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception as exc:
                logger.warning("Error closing Picamera2: %s", exc)
            finally:
                self._picam2 = None

        self._initialized = False
        logger.info("Camera stopped")

    async def restart_camera(self) -> bool:
        """Restart the camera after a failure.

        Returns:
            True if restart succeeded, False if max attempts exceeded.
        """
        if self._restart_attempts >= self._config.max_restart_attempts:
            logger.error(
                "Camera restart limit (%d) reached — giving up",
                self._config.max_restart_attempts,
            )
            return False

        self._restart_attempts += 1
        logger.info(
            "Restarting camera (attempt %d/%d) …",
            self._restart_attempts,
            self._config.max_restart_attempts,
        )

        await self.stop_camera()
        await asyncio.sleep(self._config.restart_delay_s)
        await self.initialize_camera()
        return True

    @property
    def is_running(self) -> bool:
        """Whether the camera capture loop is active."""
        return self._running and self._initialized

    @property
    def resolution(self) -> tuple[int, int]:
        """Current capture resolution as (width, height)."""
        return (self._config.width, self._config.height)

    @property
    def framerate(self) -> int:
        """Configured target frame rate."""
        return self._config.framerate

    # ------------------------------------------------------------------
    # Internal — thread management
    # ------------------------------------------------------------------

    def _start_capture_thread(self, target) -> None:
        self._capture_thread = threading.Thread(
            target=target, name="camera-capture", daemon=True
        )
        self._capture_thread.start()

    # ------------------------------------------------------------------
    # Internal — hardware capture (Picamera2)
    # ------------------------------------------------------------------

    def _init_picamera2(self) -> None:
        """Open Picamera2 and configure it. Runs in executor thread."""
        from picamera2 import Picamera2  # type: ignore[import-untyped]

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": (self._config.width, self._config.height), "format": "RGB888"},
            controls={"FrameRate": float(self._config.framerate)},
        )
        self._picam2.configure(config)
        if self._config.rotation:
            self._picam2.set_controls({"ScalerCrop": None})
        self._picam2.start()
        # Allow sensor to stabilise
        time.sleep(0.5)

    def _hw_capture_loop(self) -> None:
        """Continuous capture loop for real Picamera2 hardware."""
        import io as _io

        interval = 1.0 / self._config.framerate
        logger.info("[CAM-HW] Capture loop started")

        while self._running:
            start = time.monotonic()
            try:
                # Capture a JPEG directly from the sensor
                buf = _io.BytesIO()
                self._picam2.capture_file(
                    buf,
                    format="jpeg",
                )
                frame = buf.getvalue()
                self._enqueue_frame(frame)
            except Exception as exc:
                logger.error("[CAM-HW] Capture error: %s", exc)
                if self._running:
                    asyncio.run_coroutine_threadsafe(
                        self.restart_camera(), self._loop
                    )
                break

            elapsed = time.monotonic() - start
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)

        logger.info("[CAM-HW] Capture loop exited")

    # ------------------------------------------------------------------
    # Internal — simulation frame generator
    # ------------------------------------------------------------------

    def _sim_capture_loop(self) -> None:
        """Generate synthetic JPEG frames at the configured FPS."""
        interval = 1.0 / self._config.framerate
        logger.info("[CAM-SIM] Synthetic capture loop started")

        while self._running:
            start = time.monotonic()
            try:
                frame = self._generate_sim_frame()
                self._enqueue_frame(frame)
            except Exception as exc:
                logger.error("[CAM-SIM] Frame generation error: %s", exc)

            elapsed = time.monotonic() - start
            time.sleep(max(0.0, interval - elapsed))

        logger.info("[CAM-SIM] Capture loop exited")

    def _generate_sim_frame(self) -> bytes:
        """Create a synthetic JPEG frame using Pillow.

        The frame shows an animated gradient background with a timestamp,
        frame counter, and resolution text — enough to verify the stream
        is live and updating.
        """
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

        self._sim_frame_count += 1
        t = time.monotonic()
        w, h = self._config.width, self._config.height

        # Animated HSV → RGB background
        hue_deg = (t * 30) % 360  # rotates through hues over ~12 s
        hue = hue_deg / 360.0
        r, g, b = _hsv_to_rgb(hue, 0.6, 0.25)

        img = Image.new("RGB", (w, h), color=(r, g, b))
        draw = ImageDraw.Draw(img)

        # Scanline gradient overlay
        for y in range(h):
            alpha = y / h
            row_r = int(r + (0 - r) * alpha)
            row_g = int(g + (0 - g) * alpha)
            row_b = int(b + (80 - b) * alpha)
            draw.line([(0, y), (w, y)], fill=(row_r, row_g, row_b))

        # Crosshair reticle
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=(0, 255, 0), width=2)
        draw.line([(cx - 50, cy), (cx - 35, cy)], fill=(0, 255, 0), width=2)
        draw.line([(cx + 35, cy), (cx + 50, cy)], fill=(0, 255, 0), width=2)
        draw.line([(cx, cy - 50), (cx, cy - 35)], fill=(0, 255, 0), width=2)
        draw.line([(cx, cy + 35), (cx, cy + 50)], fill=(0, 255, 0), width=2)

        # Corner brackets (FPV style)
        bracket = 20
        for bx, by in [(10, 10), (w - 30, 10), (10, h - 30), (w - 30, h - 30)]:
            draw.line([(bx, by), (bx + bracket, by)], fill=(0, 255, 0), width=2)
            draw.line([(bx, by), (bx, by + bracket)], fill=(0, 255, 0), width=2)

        # Text overlays
        try:
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14
            )
            font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 20
            )
        except (OSError, IOError):
            font_small = ImageFont.load_default()
            font_large = font_small

        # Top-left: timestamp
        ts = time.strftime("%H:%M:%S")
        draw.text((12, 12), f"\u23f1 {ts}", fill=(0, 255, 0), font=font_small)

        # Top-right: resolution + FPS
        res_text = f"{w}x{h} {self._config.framerate}fps"
        draw.text((w - 140, 12), res_text, fill=(0, 255, 0), font=font_small)

        # Centre: SIM label
        sim_text = "SIMULATION MODE"
        bbox = draw.textbbox((0, 0), sim_text, font=font_large)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, cy + 45), sim_text, fill=(255, 180, 0), font=font_large)

        # Bottom-left: frame counter
        draw.text(
            (12, h - 28),
            f"FRAME {self._sim_frame_count:06d}",
            fill=(0, 200, 255),
            font=font_small,
        )

        # Pulsing dot (liveness indicator)
        pulse = abs(math.sin(t * 3))
        dot_r = int(4 + pulse * 6)
        dot_color = (int(255 * pulse), 255, 0)
        draw.ellipse(
            [w - 24, h - 24, w - 24 + dot_r * 2, h - 24 + dot_r * 2],
            fill=dot_color,
        )

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self._config.jpeg_quality, optimize=False)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Internal — thread-safe frame enqueue
    # ------------------------------------------------------------------

    def _enqueue_frame(self, frame: bytes) -> None:
        """Push a frame into the asyncio queue from a background thread.

        Schedules ``_put_frame`` on the event loop so all queue operations
        happen on the asyncio thread — fully thread-safe.
        """
        if self._loop is None or not self._running:
            return
        asyncio.run_coroutine_threadsafe(self._put_frame(frame), self._loop)

    async def _put_frame(self, frame: bytes) -> None:
        """Drop the oldest frame if the queue is full, then enqueue the new one.

        Runs on the asyncio event loop, so ``get_nowait`` / ``put_nowait``
        are safe here.
        """
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._frame_queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV (0-1 each) to RGB (0-255 each)."""
    if s == 0:
        rv = int(v * 255)
        return rv, rv, rv
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i = i % 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)
