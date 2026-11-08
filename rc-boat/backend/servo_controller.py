"""
Servo Controller — Rudder / Steering Servo Control

Manages a standard hobby servo for boat rudder control via PWM.
Supports hardware (lgpio / gpiozero on Raspberry Pi) and simulation mode.

Steering convention:
  -1.0 = full left   (left_pulse_us)
   0.0 = center      (center_pulse_us)
  +1.0 = full right  (right_pulse_us)
"""

import asyncio
import logging
from typing import Optional

from config import ServoConfig

logger = logging.getLogger(__name__)


class ServoController:
    """Controls a rudder servo for boat steering.

    Maps a normalised steering value (-1.0 … +1.0) to PWM pulse widths
    and drives the servo accordingly.  In simulation mode all GPIO
    interactions are replaced by log messages.

    Attributes:
        _config: Servo configuration parameters.
        _simulation: Whether to run without real GPIO.
        _current_steering: Current steering position (-1.0 … +1.0).
        _current_pulse_us: Current PWM pulse width in microseconds.
        _gpio_handle: lgpio chip handle (hardware mode only).
        _gpio_lib: Reference to the lgpio module (hardware mode only).
    """

    def __init__(self, config: ServoConfig, simulation: bool = True) -> None:
        """Initialize the servo controller.

        Args:
            config: Servo configuration dataclass.
            simulation: If True, skip GPIO and log PWM values instead.
        """
        self._config = config
        self._simulation = simulation
        self._current_steering: float = 0.0
        self._current_pulse_us: int = config.center_pulse_us
        self._gpio_handle: Optional[int] = None
        self._gpio_lib = None
        self._lock = asyncio.Lock()

        logger.info(
            "ServoController created | pin=%d simulation=%s max_angle=%.2f",
            config.gpio_pin,
            simulation,
            config.max_steering_angle,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize GPIO and centre the servo.

        In hardware mode this opens the lgpio chip and claims the pin.
        In simulation mode it logs the initialization.
        """
        if not self._simulation:
            await self._init_hardware()
        else:
            logger.info("[SIM] Servo GPIO initialized on pin %d", self._config.gpio_pin)

        # Centre the servo on startup
        self._set_pwm(self._config.center_pulse_us)
        self._current_steering = 0.0
        logger.info("Servo centred (%d µs)", self._config.center_pulse_us)

    async def set_steering(self, value: float) -> None:
        """Set the rudder steering position.

        The value is clamped to ``[-max_steering_angle, +max_steering_angle]``.
        Negative values steer left, positive values steer right.

        Args:
            value: Desired steering from -1.0 (full left) to +1.0 (full right).
        """
        async with self._lock:
            clamped = max(
                -self._config.max_steering_angle,
                min(value, self._config.max_steering_angle),
            )
            pulse_us = self._value_to_pulse_width(clamped)
            self._set_pwm(pulse_us)
            self._current_steering = clamped

    def get_current_steering(self) -> float:
        """Return the current steering value (-1.0 … +1.0)."""
        return self._current_steering

    async def center(self) -> None:
        """Return the servo to the centre position."""
        async with self._lock:
            self._set_pwm(self._config.center_pulse_us)
            self._current_steering = 0.0
            logger.info("Servo centred")

    async def cleanup(self) -> None:
        """Centre the servo and release GPIO resources."""
        async with self._lock:
            self._set_pwm(self._config.center_pulse_us)
            self._current_steering = 0.0

            if not self._simulation and self._gpio_handle is not None:
                try:
                    self._gpio_lib.tx_pwm(
                        self._gpio_handle, self._config.gpio_pin, 0, 0
                    )
                    self._gpio_lib.gpiochip_close(self._gpio_handle)
                    logger.info("Servo GPIO resources released")
                except Exception as exc:
                    logger.error("Error releasing Servo GPIO: %s", exc)
                finally:
                    self._gpio_handle = None

            logger.info("ServoController cleaned up")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _value_to_pulse_width(self, value: float) -> int:
        """Map a steering value (-1.0 … +1.0) to a pulse width (µs).

        Mapping:
          -1.0 → left_pulse_us
           0.0 → center_pulse_us
          +1.0 → right_pulse_us

        The mapping is linear and symmetrical around centre.

        Args:
            value: Steering position in [-1.0, +1.0].

        Returns:
            Pulse width in microseconds.
        """
        if value < 0:
            # Map -1.0 … 0.0  →  left_pulse_us … center_pulse_us
            pulse_range = self._config.center_pulse_us - self._config.left_pulse_us
            return int(self._config.center_pulse_us + value * pulse_range)
        else:
            # Map  0.0 … 1.0  →  center_pulse_us … right_pulse_us
            pulse_range = self._config.right_pulse_us - self._config.center_pulse_us
            return int(self._config.center_pulse_us + value * pulse_range)

    def _set_pwm(self, pulse_width_us: int) -> None:
        """Set the PWM output to the given pulse width.

        Args:
            pulse_width_us: Desired pulse width in microseconds.
        """
        self._current_pulse_us = pulse_width_us

        if self._simulation:
            logger.debug(
                "[SIM] Servo PWM → %d µs  (steering=%.3f)",
                pulse_width_us,
                self._current_steering,
            )
            return

        if self._gpio_handle is None:
            logger.error("Cannot set PWM — GPIO handle not initialised")
            return

        try:
            period_us = 1_000_000 / self._config.pwm_frequency
            duty_pct = (pulse_width_us / period_us) * 100.0
            self._gpio_lib.tx_pwm(
                self._gpio_handle,
                self._config.gpio_pin,
                self._config.pwm_frequency,
                duty_pct,
            )
        except Exception as exc:
            logger.error("Failed to set Servo PWM: %s", exc)

    async def _init_hardware(self) -> None:
        """Open the GPIO chip and claim the servo pin for PWM output.

        Tries lgpio first; falls back to gpiozero if unavailable.
        Never called in simulation mode.
        """
        try:
            import lgpio  # type: ignore[import-untyped]

            self._gpio_lib = lgpio
            self._gpio_handle = lgpio.gpiochip_open(0)
            logger.info(
                "lgpio: opened chip 0, handle=%d for Servo pin %d",
                self._gpio_handle,
                self._config.gpio_pin,
            )
        except ImportError:
            logger.warning("lgpio not available — attempting gpiozero fallback")
            try:
                from gpiozero import Servo as GpioServo  # type: ignore[import-untyped]

                self._gpiozero_servo = GpioServo(
                    self._config.gpio_pin,
                    min_pulse_width=self._config.left_pulse_us / 1_000_000,
                    max_pulse_width=self._config.right_pulse_us / 1_000_000,
                )
                self._gpio_handle = -1  # sentinel — indicates gpiozero mode
                logger.info(
                    "gpiozero Servo fallback active for Servo pin %d",
                    self._config.gpio_pin,
                )
            except ImportError:
                raise RuntimeError(
                    "Neither lgpio nor gpiozero is installed.  "
                    "Install one or enable simulation mode."
                )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise Servo GPIO hardware: {exc}"
            ) from exc
