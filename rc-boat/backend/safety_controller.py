"""
Safety Controller — Heartbeat Watchdog & Emergency Stop

Monitors communication health between the client and the boat.  If the
client fails to send heartbeats or control commands within the configured
timeout windows, the safety controller automatically triggers an emergency
stop (motor → neutral, servo → centre).

The watchdog runs as an asyncio background task at ~100 ms intervals.
"""

import asyncio
import logging
import time

from config import SafetyConfig
from motor_controller import MotorController
from servo_controller import ServoController

logger = logging.getLogger(__name__)


class SafetyController:
    """Monitors connection health and enforces emergency-stop on timeout.

    Tracks the most recent heartbeat and command timestamps.  A background
    watchdog task periodically compares them against the configured
    thresholds and triggers an emergency stop when they are exceeded.

    Attributes:
        _config: Safety configuration parameters.
        _motor: Motor controller instance (for emergency stop).
        _servo: Servo controller instance (for emergency centre).
        _last_heartbeat_time: Monotonic timestamp of last heartbeat.
        _last_command_time: Monotonic timestamp of last control command.
        _missed_heartbeats: Consecutive missed heartbeat count.
        _emergency_stopped: Whether an emergency stop is currently active.
        _watchdog_task: The asyncio Task running the watchdog loop.
    """

    def __init__(
        self,
        config: SafetyConfig,
        motor: MotorController,
        servo: ServoController,
    ) -> None:
        """Initialize the safety controller.

        Args:
            config: Safety configuration dataclass.
            motor: Motor controller to stop on timeout.
            servo: Servo controller to centre on timeout.
        """
        self._config = config
        self._motor = motor
        self._servo = servo

        now = time.monotonic()
        self._last_heartbeat_time: float = now
        self._last_command_time: float = now
        self._missed_heartbeats: int = 0
        self._emergency_stopped: bool = False
        self._watchdog_task: asyncio.Task | None = None
        self._watchdog_running: bool = False

        logger.info(
            "SafetyController created | heartbeat_timeout=%d ms  "
            "command_timeout=%d ms  max_missed=%d",
            config.heartbeat_timeout_ms,
            config.command_timeout_ms,
            config.max_consecutive_missed_heartbeats,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_heartbeat(self) -> None:
        """Record that a heartbeat was received from the client.

        Resets the missed-heartbeat counter and updates the timestamp.
        """
        self._last_heartbeat_time = time.monotonic()
        self._missed_heartbeats = 0

    def record_command(self) -> None:
        """Record that a control command was received from the client."""
        self._last_command_time = time.monotonic()

    def check_timeouts(self) -> bool:
        """Check whether heartbeat or command timeouts have been exceeded.

        Returns:
            True if a timeout has been exceeded (emergency stop is warranted).
        """
        now = time.monotonic()

        # Heartbeat timeout
        heartbeat_elapsed_ms = (now - self._last_heartbeat_time) * 1000.0
        if heartbeat_elapsed_ms > self._config.heartbeat_timeout_ms:
            self._missed_heartbeats += 1
            if self._missed_heartbeats >= self._config.max_consecutive_missed_heartbeats:
                logger.warning(
                    "Heartbeat timeout: %.0f ms elapsed, %d consecutive misses",
                    heartbeat_elapsed_ms,
                    self._missed_heartbeats,
                )
                return True

        # Command timeout
        command_elapsed_ms = (now - self._last_command_time) * 1000.0
        if command_elapsed_ms > self._config.command_timeout_ms:
            logger.warning(
                "Command timeout: %.0f ms since last command",
                command_elapsed_ms,
            )
            return True

        return False

    async def trigger_emergency_stop(self) -> None:
        """Trigger an emergency stop — motor neutral, servo centred.

        Safe to call multiple times; subsequent calls while already
        stopped are no-ops.
        """
        if self._emergency_stopped:
            return

        logger.critical("EMERGENCY STOP triggered by safety controller")
        self._emergency_stopped = True

        await self._motor.emergency_stop()
        await self._servo.center()

    @property
    def is_emergency_stopped(self) -> bool:
        """Whether an emergency stop is currently active."""
        return self._emergency_stopped

    def clear_emergency_stop(self) -> None:
        """Clear the emergency-stop flag so normal operation can resume.

        This does NOT re-arm the motor; the client must send an explicit
        arm command after clearing.
        """
        if self._emergency_stopped:
            logger.info("Emergency stop cleared")
            self._emergency_stopped = False
            # Reset timestamps so the watchdog doesn't immediately re-trigger
            now = time.monotonic()
            self._last_heartbeat_time = now
            self._last_command_time = now
            self._missed_heartbeats = 0

    async def start_watchdog(self) -> None:
        """Start the background watchdog task.

        The watchdog runs approximately every 100 ms and checks whether
        heartbeat or command timeouts have been exceeded.  If so, it
        automatically triggers an emergency stop.
        """
        if self._watchdog_running:
            logger.warning("Watchdog is already running")
            return

        self._watchdog_running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("Safety watchdog started (100 ms interval)")

    async def stop_watchdog(self) -> None:
        """Stop the background watchdog task gracefully."""
        self._watchdog_running = False
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
            logger.info("Safety watchdog stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _watchdog_loop(self) -> None:
        """Background loop that periodically checks timeouts.

        Runs every ~100 ms.  If a timeout is detected, an emergency stop
        is triggered.
        """
        logger.debug("Watchdog loop entered")
        try:
            while self._watchdog_running:
                if not self._emergency_stopped and self.check_timeouts():
                    await self.trigger_emergency_stop()
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.debug("Watchdog loop cancelled")
        except Exception as exc:
            logger.error("Watchdog loop error: %s", exc, exc_info=True)
            # On unexpected error, try to stop the motor as a last resort
            try:
                await self._motor.emergency_stop()
                await self._servo.center()
            except Exception:
                pass
