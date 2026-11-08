"""
Motor Controller — ESC / Brushless Motor Control

Manages the Electronic Speed Controller (ESC) for a brushless motor via PWM.
Supports both real hardware (lgpio / gpiozero on Raspberry Pi) and a simulation
mode that logs PWM values without touching GPIO.

ESC Protocol:
  1. On power-up, send the neutral pulse (1500 µs) for the arming duration.
  2. Once armed, throttle commands map 0.0–1.0 to neutral–max pulse width.
  3. Emergency stop returns immediately to neutral.
"""

import asyncio
import logging
import time
from typing import Optional

from config import ESCConfig

logger = logging.getLogger(__name__)


class MotorController:
    """Controls a brushless motor through an Electronic Speed Controller (ESC).

    The controller manages the full ESC lifecycle: initialization, arming,
    throttle control, and emergency stop. In simulation mode, all GPIO
    operations are replaced by log messages.

    Attributes:
        _config: ESC configuration parameters.
        _simulation: Whether to run in simulation mode (no GPIO).
        _armed: Whether the ESC has been successfully armed.
        _current_throttle: Current throttle value (0.0–1.0).
        _current_pulse_us: Current PWM pulse width in microseconds.
        _gpio_handle: lgpio chip handle (hardware mode only).
        _gpio_lib: Reference to the lgpio module (hardware mode only).
    """

    def __init__(self, config: ESCConfig, simulation: bool = True) -> None:
        """Initialize the motor controller.

        Args:
            config: ESC configuration dataclass.
            simulation: If True, skip GPIO and log PWM values instead.
        """
        self._config = config
        self._simulation = simulation
        self._armed = False
        self._current_throttle: float = 0.0
        self._current_pulse_us: int = config.neutral_pulse_us
        self._gpio_handle: Optional[int] = None
        self._gpio_lib = None
        self._lock = asyncio.Lock()

        logger.info(
            "MotorController created | pin=%d simulation=%s max_throttle=%.2f",
            config.gpio_pin,
            simulation,
            config.max_throttle,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initialize_esc(self) -> None:
        """Initialize the ESC by opening GPIO and sending the neutral signal.

        In hardware mode this opens the lgpio chip and starts PWM output.
        In simulation mode it logs the initialization.
        """
        if not self._simulation:
            await self._init_hardware()
        else:
            logger.info("[SIM] ESC GPIO initialized on pin %d", self._config.gpio_pin)

        # Send neutral signal
        self._set_pwm(self._config.neutral_pulse_us)
        logger.info("ESC neutral signal sent (%d µs)", self._config.neutral_pulse_us)

    async def arm(self) -> None:
        """Arm the ESC by holding the neutral signal for the configured duration.

        The ESC requires a stable neutral pulse for a few seconds on startup
        before it will accept throttle commands. This method blocks (via
        asyncio.sleep) for ``arming_duration`` seconds.

        Raises:
            RuntimeError: If ESC initialization has not been performed.
        """
        async with self._lock:
            logger.info(
                "Arming ESC — sending neutral for %.1f seconds …",
                self._config.arming_duration,
            )
            self._set_pwm(self._config.neutral_pulse_us)
            await asyncio.sleep(self._config.arming_duration)
            self._armed = True
            self._current_throttle = 0.0
            logger.info("ESC armed successfully")

    async def disarm(self) -> None:
        """Disarm the ESC by returning to neutral and clearing the armed flag."""
        async with self._lock:
            self._set_pwm(self._config.neutral_pulse_us)
            self._current_throttle = 0.0
            self._armed = False
            logger.info("ESC disarmed — neutral signal set")

    async def set_throttle(self, value: float) -> None:
        """Set the motor throttle.

        The value is clamped to ``[0.0, max_throttle]``. The pulse width
        is computed via :meth:`_value_to_pulse_width` and applied.

        Args:
            value: Desired throttle from 0.0 (idle) to 1.0 (full).
                   Values above ``max_throttle`` are clamped.
        """
        async with self._lock:
            if not self._armed:
                logger.warning("set_throttle called but ESC is not armed — ignoring")
                return

            clamped = max(0.0, min(value, self._config.max_throttle))
            pulse_us = self._value_to_pulse_width(clamped)
            self._set_pwm(pulse_us)
            self._current_throttle = clamped

    def get_current_throttle(self) -> float:
        """Return the current throttle value (0.0–1.0)."""
        return self._current_throttle

    async def emergency_stop(self) -> None:
        """Immediately set the ESC to neutral — ignores armed state."""
        async with self._lock:
            self._set_pwm(self._config.neutral_pulse_us)
            self._current_throttle = 0.0
            logger.warning("EMERGENCY STOP — motor set to neutral")

    async def cleanup(self) -> None:
        """Return to neutral, release GPIO resources, and mark as disarmed."""
        async with self._lock:
            self._set_pwm(self._config.neutral_pulse_us)
            self._current_throttle = 0.0
            self._armed = False

            if not self._simulation and self._gpio_handle is not None:
                try:
                    self._gpio_lib.tx_pwm(
                        self._gpio_handle, self._config.gpio_pin, 0, 0
                    )
                    self._gpio_lib.gpiochip_close(self._gpio_handle)
                    logger.info("ESC GPIO resources released")
                except Exception as exc:
                    logger.error("Error releasing ESC GPIO: %s", exc)
                finally:
                    self._gpio_handle = None

            logger.info("MotorController cleaned up")

    @property
    def is_armed(self) -> bool:
        """Whether the ESC is currently armed and accepting throttle commands."""
        return self._armed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _value_to_pulse_width(self, value: float) -> int:
        """Map a throttle value (0.0–1.0) to a pulse width in microseconds.

        0.0 → neutral_pulse_us, 1.0 → max_pulse_us.

        Args:
            value: Throttle value in [0.0, 1.0].

        Returns:
            Pulse width in microseconds.
        """
        pulse_range = self._config.max_pulse_us - self._config.neutral_pulse_us
        return int(self._config.neutral_pulse_us + value * pulse_range)

    def _set_pwm(self, pulse_width_us: int) -> None:
        """Set the PWM output to the given pulse width.

        In simulation mode the value is logged. In hardware mode the
        lgpio ``tx_pwm`` function is called with the calculated duty
        cycle derived from the pulse width and frequency.

        Args:
            pulse_width_us: Desired pulse width in microseconds.
        """
        self._current_pulse_us = pulse_width_us

        if self._simulation:
            logger.debug(
                "[SIM] ESC PWM → %d µs  (throttle=%.3f)",
                pulse_width_us,
                self._current_throttle,
            )
            return

        if self._gpio_handle is None:
            logger.error("Cannot set PWM — GPIO handle not initialised")
            return

        try:
            # lgpio tx_pwm expects frequency (Hz) and duty cycle (0–100 %).
            period_us = 1_000_000 / self._config.pwm_frequency
            duty_pct = (pulse_width_us / period_us) * 100.0
            self._gpio_lib.tx_pwm(
                self._gpio_handle,
                self._config.gpio_pin,
                self._config.pwm_frequency,
                duty_pct,
            )
        except Exception as exc:
            logger.error("Failed to set ESC PWM: %s", exc)

    async def _init_hardware(self) -> None:
        """Open the GPIO chip and claim the ESC pin for PWM output.

        Tries lgpio first; falls back to gpiozero Servo if lgpio is
        unavailable.  This method is never called in simulation mode.
        """
        try:
            import lgpio  # type: ignore[import-untyped]

            self._gpio_lib = lgpio
            self._gpio_handle = lgpio.gpiochip_open(0)
            logger.info(
                "lgpio: opened chip 0, handle=%d for ESC pin %d",
                self._gpio_handle,
                self._config.gpio_pin,
            )
        except ImportError:
            logger.warning("lgpio not available — attempting gpiozero fallback")
            try:
                from gpiozero import Servo as GpioServo  # type: ignore[import-untyped]

                # gpiozero Servo maps -1..1 to min..max pulse.  We'll wrap
                # it so _set_pwm still works via .value.
                self._gpiozero_servo = GpioServo(
                    self._config.gpio_pin,
                    min_pulse_width=self._config.min_pulse_us / 1_000_000,
                    max_pulse_width=self._config.max_pulse_us / 1_000_000,
                )
                self._gpio_handle = -1  # sentinel — indicates gpiozero mode
                logger.info("gpiozero Servo fallback active for ESC pin %d", self._config.gpio_pin)
            except ImportError:
                raise RuntimeError(
                    "Neither lgpio nor gpiozero is installed.  "
                    "Install one or enable simulation mode."
                )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialise ESC GPIO hardware: {exc}") from exc
