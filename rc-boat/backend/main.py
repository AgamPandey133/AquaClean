"""
RC Boat Control Server — FastAPI + WebSocket

Provides:
  • WebSocket endpoint ``/ws/control`` for real-time boat control.
  • REST endpoints ``/health`` and ``/config`` for diagnostics.
  • A 50 Hz control loop that translates key-press state into smooth
    throttle acceleration / deceleration and instant steering updates.
  • A 20 Hz status broadcast loop that pushes telemetry to the client.

WebSocket JSON protocol
-----------------------
**Client → Server:**

.. code-block:: json

    {"type": "control", "key": "w"|"a"|"d"|"s"|"space", "action": "press"|"release"}
    {"type": "heartbeat"}
    {"type": "arm"}
    {"type": "disarm"}

**Server → Client:**

.. code-block:: json

    {"type": "status", "throttle": 0.0, "steering": 0.0, "armed": false,
     "emergency_stopped": false, "simulation": true}
    {"type": "heartbeat_ack"}
    {"type": "error", "message": "..."}
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import config
from motor_controller import MotorController
from servo_controller import ServoController
from safety_controller import SafetyController
from camera.camera_controller import CameraController
from camera.streaming_service import StreamingService

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared controller instances (populated in lifespan)
# ---------------------------------------------------------------------------
motor: MotorController | None = None
servo: ServoController | None = None
safety: SafetyController | None = None
camera_ctrl: CameraController | None = None
stream_svc: StreamingService | None = None


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the FastAPI application.

    On startup:
      1. Create motor, servo, and safety controllers.
      2. Initialize ESC and servo hardware (or simulation).
      3. Start the safety watchdog.

    On shutdown:
      1. Stop the safety watchdog.
      2. Cleanup motor and servo controllers.
    """
    global motor, servo, safety, camera_ctrl, stream_svc

    logger.info("=" * 60)
    logger.info("RC Boat Backend — starting up  (simulation=%s)", config.simulation_mode)
    logger.info("=" * 60)

    motor = MotorController(config.esc, simulation=config.simulation_mode)
    servo = ServoController(config.servo, simulation=config.simulation_mode)

    await motor.initialize_esc()
    await servo.initialize()

    safety = SafetyController(config.safety, motor, servo)

    # ── Camera startup (independent of motor control) ──
    if config.camera.enabled:
        camera_ctrl = CameraController(config.camera)
        await camera_ctrl.initialize_camera()
        stream_svc = StreamingService(camera_ctrl)
        logger.info("Camera streaming service started")
    else:
        logger.info("Camera disabled (CAMERA_ENABLED=false)")

    logger.info("Startup complete — ready to accept connections")

    yield  # ---- application runs here ----

    logger.info("Shutting down …")
    if safety is not None:
        await safety.stop_watchdog()
    if motor is not None:
        await motor.cleanup()
    if servo is not None:
        await servo.cleanup()
    if camera_ctrl is not None:
        await camera_ctrl.stop_camera()
        logger.info("Camera stopped")
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="RC Boat Control API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health-check endpoint.

    Returns:
        JSON with status, simulation mode flag, and armed state.
    """
    return {
        "status": "ok",
        "simulation": config.simulation_mode,
        "armed": motor.is_armed if motor else False,
        "emergency_stopped": safety.is_emergency_stopped if safety else False,
    }


@app.get("/config")
async def get_config() -> Dict[str, Any]:
    """Return the current application configuration (excluding raw GPIO pin numbers).

    Returns:
        JSON representation of the active configuration.
    """
    return {
        "simulation_mode": config.simulation_mode,
        "esc": {
            "neutral_pulse_us": config.esc.neutral_pulse_us,
            "min_pulse_us": config.esc.min_pulse_us,
            "max_pulse_us": config.esc.max_pulse_us,
            "pwm_frequency": config.esc.pwm_frequency,
            "max_throttle": config.esc.max_throttle,
            "acceleration_rate": config.esc.acceleration_rate,
            "deceleration_rate": config.esc.deceleration_rate,
            "arming_duration": config.esc.arming_duration,
        },
        "servo": {
            "center_pulse_us": config.servo.center_pulse_us,
            "left_pulse_us": config.servo.left_pulse_us,
            "right_pulse_us": config.servo.right_pulse_us,
            "pwm_frequency": config.servo.pwm_frequency,
            "max_steering_angle": config.servo.max_steering_angle,
            "steering_speed": config.servo.steering_speed,
        },
        "safety": {
            "heartbeat_timeout_ms": config.safety.heartbeat_timeout_ms,
            "heartbeat_interval_ms": config.safety.heartbeat_interval_ms,
            "command_timeout_ms": config.safety.command_timeout_ms,
            "max_consecutive_missed_heartbeats": config.safety.max_consecutive_missed_heartbeats,
        },
    }


@app.get("/video")
async def mjpeg_stream(request: Request) -> StreamingResponse:
    """MJPEG video stream from the Raspberry Pi camera.

    Connect an ``<img>`` tag to this URL to display live video in a browser.
    Multiple clients can connect simultaneously without affecting one another.

    Returns:
        multipart/x-mixed-replace StreamingResponse at the configured FPS.

    Raises:
        503 if the camera sub-system was not initialised (disabled or failed).
    """
    if stream_svc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Camera not available")
    return await stream_svc.stream_response(request)


@app.get("/camera/status")
async def camera_status() -> Dict[str, Any]:
    """Return camera streaming status.

    Returns:
        JSON with enabled flag, running state, resolution, framerate,
        and active client count.
    """
    if stream_svc is None or camera_ctrl is None:
        return {"enabled": False, "running": False, "active_clients": 0}
    status = await stream_svc.get_camera_status()
    status["enabled"] = config.camera.enabled
    return status


# ---------------------------------------------------------------------------
# WebSocket control endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/control")
async def websocket_control(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time boat control.

    Manages key-press state, runs a 50 Hz control loop for smooth
    throttle ramping, and broadcasts status at ~20 Hz.
    """
    await ws.accept()
    client = ws.client
    logger.info("WebSocket client connected: %s", client)

    # ---- per-connection state ----
    key_state: Dict[str, bool] = {
        "w": False,
        "a": False,
        "s": False,
        "d": False,
        "space": False,
    }
    current_throttle: float = 0.0
    control_task: asyncio.Task | None = None
    status_task: asyncio.Task | None = None
    connected = True

    # Reset safety timestamps for this new connection
    if safety is not None:
        safety.clear_emergency_stop()
        safety.record_heartbeat()
        safety.record_command()
        await safety.start_watchdog()

    # ------------------------------------------------------------------
    # Control loop (50 Hz) — runs as a background task
    # ------------------------------------------------------------------
    async def control_loop() -> None:
        """Apply throttle acceleration / deceleration and steering at 50 Hz."""
        nonlocal current_throttle

        last_tick = time.monotonic()
        try:
            while connected:
                now = time.monotonic()
                dt = now - last_tick
                last_tick = now

                if motor is None or servo is None or safety is None:
                    await asyncio.sleep(0.02)
                    continue

                # Skip control updates while emergency-stopped
                if safety.is_emergency_stopped:
                    current_throttle = 0.0
                    await asyncio.sleep(0.02)
                    continue

                # ---- Throttle ----
                if key_state["space"]:
                    # Space = immediate stop
                    current_throttle = 0.0
                elif key_state["w"]:
                    # Accelerate toward max_throttle
                    target = config.esc.max_throttle
                    current_throttle = min(
                        target,
                        current_throttle + config.esc.acceleration_rate * dt,
                    )
                else:
                    # Decelerate toward 0
                    current_throttle = max(
                        0.0,
                        current_throttle - config.esc.deceleration_rate * dt,
                    )

                await motor.set_throttle(current_throttle)

                # ---- Steering ----
                if key_state["a"] and not key_state["d"]:
                    target_steering = -config.servo.max_steering_angle
                elif key_state["d"] and not key_state["a"]:
                    target_steering = config.servo.max_steering_angle
                else:
                    target_steering = 0.0

                await servo.set_steering(target_steering)

                await asyncio.sleep(0.02)  # ~50 Hz
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Control loop error: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Status broadcast loop (20 Hz) — runs as a background task
    # ------------------------------------------------------------------
    async def status_loop() -> None:
        """Send status updates to the client at ~20 Hz."""
        try:
            while connected:
                if motor is None or servo is None or safety is None:
                    await asyncio.sleep(0.05)
                    continue

                status_msg = {
                    "type": "status",
                    "throttle": round(motor.get_current_throttle(), 4),
                    "steering": round(servo.get_current_steering(), 4),
                    "armed": motor.is_armed,
                    "emergency_stopped": safety.is_emergency_stopped,
                    "simulation": config.simulation_mode,
                }
                try:
                    await ws.send_json(status_msg)
                except Exception:
                    break  # client disconnected

                await asyncio.sleep(0.05)  # ~20 Hz
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Status loop error: %s", exc, exc_info=True)

    # Start background tasks
    control_task = asyncio.create_task(control_loop())
    status_task = asyncio.create_task(status_loop())

    # ------------------------------------------------------------------
    # Message receive loop
    # ------------------------------------------------------------------
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "heartbeat":
                if safety is not None:
                    safety.record_heartbeat()
                await ws.send_json({"type": "heartbeat_ack"})

            elif msg_type == "control":
                key = msg.get("key")
                action = msg.get("action")

                if key not in key_state:
                    await ws.send_json({
                        "type": "error",
                        "message": f"Unknown key: {key}",
                    })
                    continue

                if action not in ("press", "release"):
                    await ws.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })
                    continue

                key_state[key] = action == "press"

                if safety is not None:
                    safety.record_command()
                    safety.record_heartbeat()

                # 's' key triggers deceleration via key_state (w released);
                # 'space' triggers immediate stop via control loop.
                # If 's' is pressed we simply release 'w' logic (already
                # handled — if w is not pressed, deceleration kicks in).

                logger.debug("Key %s %s", key, action)

            elif msg_type == "arm":
                if motor is not None and safety is not None:
                    if safety.is_emergency_stopped:
                        safety.clear_emergency_stop()
                    await motor.arm()
                    # Reset safety timers after arming
                    safety.record_heartbeat()
                    safety.record_command()
                    logger.info("Motor armed via client command")

            elif msg_type == "disarm":
                if motor is not None:
                    await motor.disarm()
                    current_throttle = 0.0
                    logger.info("Motor disarmed via client command")

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", client)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc, exc_info=True)
    finally:
        connected = False

        # Cancel background tasks
        if control_task is not None:
            control_task.cancel()
            try:
                await control_task
            except asyncio.CancelledError:
                pass

        if status_task is not None:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass

        # Ensure safe state on disconnect
        if motor is not None:
            await motor.emergency_stop()
        if servo is not None:
            await servo.center()
        if safety is not None:
            await safety.stop_watchdog()

        logger.info("Client session cleaned up: %s", client)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
