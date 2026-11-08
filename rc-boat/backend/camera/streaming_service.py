"""
MJPEG Streaming Service

Delivers a multipart/x-mixed-replace MJPEG stream from the CameraController
to HTTP clients. Each connected client gets an independent generator that
reads frames from the camera queue.

The MJPEG format is universally supported by browsers via a plain <img> tag
pointed at the stream URL — no JavaScript, no codec negotiation, no plugins.

IMPORTANT: This module is completely independent of the motor-control
WebSocket. Camera failures cannot affect ESC or servo operation.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator

from fastapi import Request
from fastapi.responses import StreamingResponse

from camera.camera_controller import CameraController

logger = logging.getLogger(__name__)

MJPEG_BOUNDARY = b"--frame"
MJPEG_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame"


class StreamingService:
    """Wraps a CameraController and exposes an MJPEG HTTP endpoint.

    Multiple clients can connect simultaneously; each gets an independent
    async generator reading from the shared CameraController queue.
    """

    def __init__(self, camera: CameraController) -> None:
        self._camera = camera
        self._active_clients = 0

    @property
    def active_clients(self) -> int:
        """Number of currently streaming HTTP clients."""
        return self._active_clients

    async def stream_response(self, request: Request) -> StreamingResponse:
        """Return a StreamingResponse containing the MJPEG stream.

        Args:
            request: The incoming FastAPI request (used for disconnect detection).

        Returns:
            A StreamingResponse with Content-Type multipart/x-mixed-replace.
        """
        return StreamingResponse(
            self._mjpeg_generator(request),
            media_type=MJPEG_CONTENT_TYPE,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Accel-Buffering": "no",  # disable nginx buffering
            },
        )

    async def get_camera_status(self) -> dict:
        """Return a dict describing current camera status."""
        return {
            "running": self._camera.is_running,
            "resolution": {
                "width": self._camera.resolution[0],
                "height": self._camera.resolution[1],
            },
            "framerate": self._camera.framerate,
            "active_clients": self._active_clients,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _mjpeg_generator(self, request: Request) -> AsyncGenerator[bytes, None]:
        """Async generator that yields MJPEG multipart chunks."""
        self._active_clients += 1
        client = getattr(request.client, "host", "unknown")
        logger.info(
            "MJPEG client connected: %s  (total: %d)", client, self._active_clients
        )

        frame_count = 0
        last_log = time.monotonic()

        try:
            while True:
                # Check if the HTTP client disconnected
                if await request.is_disconnected():
                    logger.info("MJPEG client disconnected: %s", client)
                    break

                if not self._camera.is_running:
                    # Camera stopped — send a small delay before retrying
                    await asyncio.sleep(0.5)
                    continue

                try:
                    frame = await asyncio.wait_for(
                        self._camera.capture_frame(), timeout=2.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Frame timeout for client %s", client)
                    continue

                if not frame:
                    continue

                # Yield MJPEG chunk
                chunk = (
                    MJPEG_BOUNDARY + b"\r\n"
                    + b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n".encode()
                    + b"\r\n"
                    + frame
                    + b"\r\n"
                )
                yield chunk

                frame_count += 1
                now = time.monotonic()
                if now - last_log >= 10.0:
                    fps = frame_count / (now - last_log + 1e-9)
                    logger.debug(
                        "MJPEG stream: client=%s  frames=%d  fps=%.1f",
                        client,
                        frame_count,
                        fps,
                    )
                    frame_count = 0
                    last_log = now

        except asyncio.CancelledError:
            logger.info("MJPEG generator cancelled for client: %s", client)
        except Exception as exc:
            logger.error("MJPEG stream error for client %s: %s", client, exc)
        finally:
            self._active_clients = max(0, self._active_clients - 1)
            logger.info(
                "MJPEG client cleaned up: %s  (remaining: %d)",
                client,
                self._active_clients,
            )
