"""
RC Boat Configuration
All hardware pins, PWM values, throttle limits, and network settings are configurable here.
Every parameter can be overridden via environment variables.
"""
from dataclasses import dataclass, field
import os

from camera.camera_config import CameraConfig


@dataclass
class ESCConfig:
    """Electronic Speed Controller configuration.

    Controls the brushless motor via PWM signals. The ESC interprets
    pulse widths to determine motor speed:
      - 1000 µs = minimum (off)
      - 1500 µs = neutral (arm/idle)
      - 2000 µs = maximum throttle

    Attributes:
        gpio_pin: BCM GPIO pin number for ESC signal wire.
        neutral_pulse_us: Pulse width in microseconds for neutral/idle.
        min_pulse_us: Minimum pulse width in microseconds.
        max_pulse_us: Maximum pulse width in microseconds.
        pwm_frequency: PWM signal frequency in Hz (standard servo = 50 Hz).
        max_throttle: Software throttle limit (0.0–1.0). Prevents full power.
        acceleration_rate: Throttle increase rate in units per second.
        deceleration_rate: Throttle decrease rate in units per second.
        arming_duration: Time in seconds to hold neutral for ESC arming.
    """
    gpio_pin: int = int(os.getenv("ESC_GPIO_PIN", "18"))

    # PWM pulse widths in microseconds
    neutral_pulse_us: int = int(os.getenv("ESC_NEUTRAL_PULSE", "1500"))
    min_pulse_us: int = int(os.getenv("ESC_MIN_PULSE", "1000"))
    max_pulse_us: int = int(os.getenv("ESC_MAX_PULSE", "2000"))

    # PWM frequency in Hz
    pwm_frequency: int = int(os.getenv("ESC_PWM_FREQ", "50"))

    # Throttle limits (0.0 to 1.0)
    max_throttle: float = float(os.getenv("ESC_MAX_THROTTLE", "0.7"))

    # Acceleration/deceleration rate (units per second)
    acceleration_rate: float = float(os.getenv("ESC_ACCEL_RATE", "0.5"))
    deceleration_rate: float = float(os.getenv("ESC_DECEL_RATE", "1.0"))

    # Arming sequence duration in seconds
    arming_duration: float = float(os.getenv("ESC_ARMING_DURATION", "3.0"))


@dataclass
class ServoConfig:
    """Servo motor configuration for rudder steering.

    Controls the rudder servo via PWM signals. Pulse widths map to
    steering positions:
      - 1000 µs = full left
      - 1500 µs = center
      - 2000 µs = full right

    Attributes:
        gpio_pin: BCM GPIO pin number for servo signal wire.
        center_pulse_us: Pulse width in microseconds for center position.
        left_pulse_us: Pulse width in microseconds for full left.
        right_pulse_us: Pulse width in microseconds for full right.
        pwm_frequency: PWM signal frequency in Hz.
        max_steering_angle: Software steering limit (0.0–1.0 maps to ±max).
        steering_speed: Steering rate in units per second for smooth transitions.
    """
    gpio_pin: int = int(os.getenv("SERVO_GPIO_PIN", "19"))

    # PWM pulse widths in microseconds
    center_pulse_us: int = int(os.getenv("SERVO_CENTER_PULSE", "1500"))
    left_pulse_us: int = int(os.getenv("SERVO_LEFT_PULSE", "1000"))
    right_pulse_us: int = int(os.getenv("SERVO_RIGHT_PULSE", "2000"))

    # PWM frequency in Hz
    pwm_frequency: int = int(os.getenv("SERVO_PWM_FREQ", "50"))

    # Steering limits (-1.0 = full left, 0.0 = center, 1.0 = full right)
    max_steering_angle: float = float(os.getenv("SERVO_MAX_ANGLE", "1.0"))

    # Steering speed (units per second for smooth transitions)
    steering_speed: float = float(os.getenv("SERVO_STEER_SPEED", "3.0"))


@dataclass
class SafetyConfig:
    """Safety-related configuration.

    Controls heartbeat monitoring and command timeouts to ensure
    the boat stops if communication is lost.

    Attributes:
        heartbeat_timeout_ms: Max time between heartbeats before emergency stop.
        heartbeat_interval_ms: Expected interval between client heartbeats.
        command_timeout_ms: Max time between control commands before emergency stop.
        max_consecutive_missed_heartbeats: Number of missed heartbeats before action.
    """
    heartbeat_timeout_ms: int = int(os.getenv("HEARTBEAT_TIMEOUT_MS", "500"))
    heartbeat_interval_ms: int = int(os.getenv("HEARTBEAT_INTERVAL_MS", "200"))
    command_timeout_ms: int = int(os.getenv("COMMAND_TIMEOUT_MS", "500"))
    max_consecutive_missed_heartbeats: int = int(os.getenv("MAX_MISSED_HEARTBEATS", "3"))


@dataclass
class ServerConfig:
    """Server configuration.

    Attributes:
        host: Bind address for the server.
        port: Port number for the server.
        cors_origins: Allowed CORS origins (comma-separated in env var).
    """
    host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    port: int = int(os.getenv("SERVER_PORT", "8000"))
    cors_origins: list = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(","))


@dataclass
class AppConfig:
    """Top-level application configuration.

    Aggregates all sub-configurations and provides the global
    simulation_mode flag. When simulation_mode is True, no GPIO
    hardware is accessed — all PWM operations are logged instead.

    Attributes:
        simulation_mode: If True, GPIO operations are simulated (logged only).
        esc: ESC / motor controller configuration.
        servo: Servo / rudder controller configuration.
        safety: Safety and watchdog configuration.
        server: HTTP / WebSocket server configuration.
        camera: Camera and MJPEG streaming configuration.
    """
    simulation_mode: bool = os.getenv("SIMULATION_MODE", "true").lower() == "true"
    esc: ESCConfig = field(default_factory=ESCConfig)
    servo: ServoConfig = field(default_factory=ServoConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)


# Global config instance
config = AppConfig()
