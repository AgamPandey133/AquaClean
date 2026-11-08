# 🚤 RC Boat FPV — Wi-Fi Controlled with Live Camera

A complete Wi-Fi-controlled RC boat system with **live FPV camera streaming**. Built with a Raspberry Pi, ESC, brushless DC motor, servo motor, and Raspberry Pi camera module. The boat is controlled through a modern web dashboard running on your PC with real-time keyboard control and a live video feed.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Hardware Connections & Wiring Diagram](#3-hardware-connections--wiring-diagram)
4. [GPIO Pin Configuration](#4-gpio-pin-configuration)
5. [Required Software](#5-required-software)
6. [Raspberry Pi Setup](#6-raspberry-pi-setup)
7. [PC Frontend Setup](#7-pc-frontend-setup)
8. [Finding the Raspberry Pi IP Address](#8-finding-the-raspberry-pi-ip-address)
9. [Starting the Application](#9-starting-the-application)
10. [Keyboard Controls](#10-keyboard-controls)
11. [ESC Calibration & Arming](#11-esc-calibration--arming)
12. [Troubleshooting](#12-troubleshooting)
13. [Safety Precautions](#13-safety-precautions)
14. [Camera — Hardware & Setup](#14-camera--hardware--setup)
15. [Camera — Configuration & Tuning](#15-camera--configuration--tuning)
16. [Camera — Troubleshooting](#16-camera--troubleshooting)

---

## 1. Project Overview

This project consists of two components and an FPV camera stream:

| Component | Runs On | Technology |
|-----------|---------|------------|
| **Frontend** — Web control dashboard | Your PC (browser) | React, TypeScript, Vite, Tailwind CSS |
| **Backend** — Hardware controller | Raspberry Pi | Python, FastAPI, WebSockets, lgpio |

The frontend captures keyboard input and sends it over WebSockets to the Raspberry Pi, which translates commands into PWM signals for the ESC (motor speed) and servo (rudder steering).

### Features

- **Real-time keyboard control** — W/A/S/D + Space
- **Gradual acceleration** — smooth throttle ramping, no sudden jumps
- **Simultaneous inputs** — steer while moving forward (W+A, W+D)
- **Safety watchdog** — auto-stops motor on connection loss
- **Emergency stop** — Space key or on-screen button
- **Simulation mode** — test everything without hardware
- **Fully configurable** — all pins, PWM values, and limits via environment variables

---

## 2. System Architecture

```
PC (Web Browser)
      │
      │ Keyboard Input (W, A, S, D, Space)
      ▼
Local Web Application (Vite dev server on PC)
      │
      │ WebSocket (ws://<pi-ip>:8000/ws/control)
      ▼
Raspberry Pi (FastAPI Backend)
      │
      │ GPIO PWM Signals
      ├───────────────────┐
      │                   │
      ▼                   ▼
     ESC              Servo Motor
      │                   │
      ▼                   ▼
Brushless Motor        Rudder
      │
      ▼
  Boat Movement
```

### Communication Flow

1. The user presses a key on the PC dashboard.
2. The frontend sends a JSON message over WebSocket: `{"type": "control", "key": "w", "action": "press"}`.
3. The backend receives it and updates internal key state.
4. A 50 Hz control loop applies gradual throttle changes and instant steering updates.
5. PWM signals are sent to the ESC and servo via GPIO.
6. Status telemetry is broadcast back to the frontend at 20 Hz.
7. A heartbeat (200 ms interval) keeps the connection alive; if missed, the safety watchdog triggers an emergency stop.

---

## 3. Hardware Connections & Wiring Diagram

### Components Required

| Component | Description |
|-----------|-------------|
| Raspberry Pi | Any model with GPIO (Pi 3, 4, 5, Zero 2 W, etc.) |
| ESC | Electronic Speed Controller (matched to your motor) |
| Brushless DC Motor | For boat propulsion |
| Servo Motor | Standard hobby servo for rudder steering |
| LiPo Battery | Matched to ESC voltage rating (e.g., 2S or 3S) |
| Propeller & Rudder | Mechanical boat components |
| Power supply for Pi | USB power bank or BEC from ESC |

### Wiring Diagram

```
                     ┌─────────────────┐
                     │   LiPo Battery  │
                     │  (e.g. 11.1V)   │
                     └────┬───────┬────┘
                          │       │
                    ┌─────▼─────┐ │
                    │    ESC    │ │
                    │           │ │
             ┌──────┤ Signal ◄──┼─┼──── GPIO 18 (Pi)
             │      │ GND    ◄──┼─┼──── GND (Pi)
             │      │           │ │
             │      │  3 Motor  │ │
             │      │  Wires    │ │
             │      └───┬─┬─┬──┘ │
             │          │ │ │    │
             │      ┌───▼─▼─▼──┐ │
             │      │ Brushless │ │
             │      │  Motor    │ │
             │      └──────────┘ │
             │                   │
             │  ┌────────────┐   │
             │  │   Servo    │   │
             │  │            │   │
             │  │ Signal ◄───┼───┼──── GPIO 19 (Pi)
             │  │ VCC    ◄───┼───┘  (from BEC/ESC 5V)
             │  │ GND    ◄───┼──────── GND (Pi)
             │  └────────────┘
             │
     ┌───────▼────────┐
     │  Raspberry Pi   │
     │                 │
     │  GPIO 18 ─────── ESC Signal
     │  GPIO 19 ─────── Servo Signal
     │  GND ─────────── Common Ground
     │                 │
     │  Connected to   │
     │  Wi-Fi Network  │
     └─────────────────┘
```

> ⚠️ **CRITICAL WIRING RULES:**
>
> - **NEVER** power the motor from Raspberry Pi GPIO pins.
> - **NEVER** treat the ESC signal wire as a power source.
> - **ALWAYS** connect a common ground between the Raspberry Pi GND and ESC signal ground.
> - The ESC is powered by the LiPo battery. The signal wire only carries the PWM control signal.
> - If your ESC has a BEC (Battery Eliminator Circuit), it can power the servo. Do NOT use it to power the Pi unless the BEC output is specifically designed for it.
> - Follow your specific ESC manufacturer's wiring instructions.

---

## 4. GPIO Pin Configuration

All GPIO pins are configurable via environment variables. Defaults:

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| ESC Pin | `ESC_GPIO_PIN` | `18` | GPIO pin for ESC PWM signal |
| Servo Pin | `SERVO_GPIO_PIN` | `19` | GPIO pin for servo PWM signal |
| ESC Neutral | `ESC_NEUTRAL_PULSE` | `1500` µs | Neutral/idle pulse width |
| ESC Min | `ESC_MIN_PULSE` | `1000` µs | Minimum pulse width |
| ESC Max | `ESC_MAX_PULSE` | `2000` µs | Maximum pulse width |
| ESC Frequency | `ESC_PWM_FREQ` | `50` Hz | PWM frequency |
| Max Throttle | `ESC_MAX_THROTTLE` | `0.7` | Maximum throttle (0.0–1.0) |
| Accel Rate | `ESC_ACCEL_RATE` | `0.5` | Acceleration rate (units/sec) |
| Decel Rate | `ESC_DECEL_RATE` | `1.0` | Deceleration rate (units/sec) |
| Arming Duration | `ESC_ARMING_DURATION` | `3.0` sec | ESC arming hold time |
| Servo Center | `SERVO_CENTER_PULSE` | `1500` µs | Servo center pulse width |
| Servo Left | `SERVO_LEFT_PULSE` | `1000` µs | Servo full-left pulse width |
| Servo Right | `SERVO_RIGHT_PULSE` | `2000` µs | Servo full-right pulse width |
| Max Steering | `SERVO_MAX_ANGLE` | `1.0` | Maximum steering angle (0.0–1.0) |
| Heartbeat Timeout | `HEARTBEAT_TIMEOUT_MS` | `500` ms | Connection timeout |
| Command Timeout | `COMMAND_TIMEOUT_MS` | `500` ms | Control command timeout |
| Simulation Mode | `SIMULATION_MODE` | `true` | Run without hardware |

---

## 5. Required Software

### On the Raspberry Pi

| Software | Version | Install Command |
|----------|---------|-----------------|
| Python | 3.10+ | Pre-installed on Raspberry Pi OS |
| pip | Latest | `sudo apt install python3-pip` |
| lgpio | 0.2+ | `pip install lgpio` |
| FastAPI | 0.115+ | `pip install fastapi` |
| Uvicorn | 0.30+ | `pip install uvicorn[standard]` |

### On your PC

| Software | Version | Install |
|----------|---------|---------|
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | Comes with Node.js |

---

## 6. Raspberry Pi Setup

### Step 1: Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Python dependencies

```bash
sudo apt install python3-pip python3-venv -y
```

### Step 3: Clone / copy the project

Copy the `rc-boat/backend/` directory to your Raspberry Pi. For example, using SCP:

```bash
scp -r rc-boat/backend/ pi@<pi-ip>:~/rc-boat/backend/
```

### Step 4: Create a virtual environment

```bash
cd ~/rc-boat/backend
python3 -m venv .venv
source .venv/bin/activate
```

### Step 5: Install Python packages

```bash
pip install -r requirements.txt
```

### Step 6: Configure environment (optional)

Create a `.env` file or export variables:

```bash
export SIMULATION_MODE=false
export ESC_GPIO_PIN=18
export SERVO_GPIO_PIN=19
export ESC_MAX_THROTTLE=0.5    # Start conservative!
```

### Step 7: Connect to Wi-Fi

Ensure the Raspberry Pi is on the same Wi-Fi network as your PC:

```bash
# Check connection
ping google.com

# Find your IP
hostname -I
```

---

## 7. PC Frontend Setup

### Step 1: Install Node.js

Download and install from [nodejs.org](https://nodejs.org) (LTS version recommended).

### Step 2: Install dependencies

```bash
cd rc-boat/frontend
npm install
```

### Step 3: Configure the Raspberry Pi address

Edit `frontend/.env`:

```env
VITE_WS_URL=ws://192.168.1.100:8000/ws/control
```

Replace `192.168.1.100` with your Raspberry Pi's actual IP address.

### Step 4: Start the dev server

```bash
npm run dev
```

The dashboard will open at `http://localhost:5173`.

---

## 8. Finding the Raspberry Pi IP Address

### Method 1: On the Pi itself

```bash
hostname -I
```

### Method 2: From your PC (same network)

```bash
# Linux/macOS
ping raspberrypi.local

# Windows
ping raspberrypi

# Or scan the network
nmap -sn 192.168.1.0/24
```

### Method 3: From your router

Log into your router admin page (usually `192.168.1.1`) and check the DHCP client list.

### Method 4: Static IP (recommended for boats)

Edit `/etc/dhcpcd.conf` on the Pi:

```bash
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

---

## 9. Starting the Application

### Step 1: Start the Backend (Raspberry Pi)

```bash
cd ~/rc-boat/backend
source .venv/bin/activate

# For testing (simulation mode)
SIMULATION_MODE=true python main.py

# For real hardware
SIMULATION_MODE=false python main.py
```

The backend starts on `0.0.0.0:8000`. You should see:

```
RC Boat Backend — starting up  (simulation=True)
ESC neutral signal sent (1500 µs)
Servo centred (1500 µs)
Startup complete — ready to accept connections
```

### Step 2: Start the Frontend (PC)

```bash
cd rc-boat/frontend
npm run dev
```

### Step 3: Open the Dashboard

Open `http://localhost:5173` in your browser.

### Step 4: Arm the ESC

1. Click the green **🔒 Arm** button.
2. Wait 3 seconds for the ESC arming sequence.
3. The button changes to amber **🔓 Disarm** when armed.

### Step 5: Control the Boat

Press **W** to go forward, **A/D** to steer, **S** or release **W** to stop.

---

## 10. Keyboard Controls

| Key | Action | Behavior |
|-----|--------|----------|
| **W** | Forward | Gradually increases throttle while held |
| **A** | Steer Left | Moves rudder left while held |
| **D** | Steer Right | Moves rudder right while held |
| **S** | Stop Motor | Begins throttle deceleration |
| **Space** | Emergency Stop | Immediately sets throttle to zero |
| Release **W** | Decelerate | Throttle ramps down to zero |
| Release **A** | Center Rudder | Returns to center (if D not pressed) |
| Release **D** | Center Rudder | Returns to center (if A not pressed) |

### Simultaneous Keys

- **W + A** — Move forward while turning left ✅
- **W + D** — Move forward while turning right ✅
- **A + D** — Cancel out, rudder stays centered ✅

### Important Notes

- Keyboard controls are disabled when typing in text fields.
- If you switch browser tabs, all keys are automatically released (window blur handler).
- The ESC must be **armed** before throttle commands take effect.

---

## 11. ESC Calibration & Arming

### What is ESC Arming?

Most ESCs require a "neutral" signal on startup before they accept throttle commands. This is a safety feature to prevent accidental motor activation.

### Default Arming Sequence

1. On backend startup, the ESC pin immediately outputs a 1500 µs pulse (neutral).
2. When you click **Arm** in the dashboard, the backend holds the neutral signal for 3 seconds.
3. After arming, the ESC accepts throttle commands.

### ESC Calibration (if needed)

If your ESC uses a different PWM range (not 1000–2000 µs), adjust these environment variables:

```bash
export ESC_MIN_PULSE=1000      # Your ESC's minimum pulse
export ESC_NEUTRAL_PULSE=1500  # Your ESC's neutral pulse
export ESC_MAX_PULSE=2000      # Your ESC's maximum pulse
```

Some ESCs require a calibration procedure:

1. Set `ESC_MAX_THROTTLE=1.0` temporarily.
2. Power off the ESC.
3. Start the backend and arm with maximum throttle signal.
4. Power on the ESC (you'll hear calibration beeps).
5. Set throttle to minimum.
6. ESC stores the range.

> **Consult your ESC's manual** for the exact calibration procedure. Every ESC brand is different.

---

## 12. Troubleshooting

### Frontend can't connect to backend

| Symptom | Fix |
|---------|-----|
| "Connection Lost" overlay | Check that the backend is running and the IP in `.env` is correct |
| WebSocket connection refused | Ensure firewall allows port 8000 on the Pi: `sudo ufw allow 8000` |
| Works locally but not over Wi-Fi | Make sure both devices are on the same network |

### Motor doesn't respond

| Symptom | Fix |
|---------|-----|
| Motor doesn't spin | Click **Arm** first! The ESC must be armed |
| ESC beeps continuously | ESC isn't detecting valid neutral signal — check `ESC_NEUTRAL_PULSE` |
| Motor stutters | Reduce `ESC_MAX_THROTTLE` and increase `ESC_ACCEL_RATE` |
| Motor runs at full speed immediately | Your ESC uses a different PWM range — recalibrate |

### Servo doesn't move

| Symptom | Fix |
|---------|-----|
| Servo doesn't respond | Check `SERVO_GPIO_PIN` and wiring |
| Servo jitters | May be a power issue — ensure servo has adequate power supply |
| Servo range is wrong | Adjust `SERVO_LEFT_PULSE`, `SERVO_CENTER_PULSE`, `SERVO_RIGHT_PULSE` |

### Backend errors

| Error | Fix |
|-------|-----|
| `lgpio not found` | `pip install lgpio` or enable simulation mode |
| `Permission denied on GPIO` | Run with `sudo` or add user to gpio group: `sudo usermod -aG gpio $USER` |
| `Address already in use` | Another process is using port 8000: `lsof -i :8000` and kill it |

### General debugging

```bash
# Check backend health
curl http://<pi-ip>:8000/health

# Check current config
curl http://<pi-ip>:8000/config

# Run backend with debug logging
LOG_LEVEL=debug python main.py
```

---

## 13. Safety Precautions

### ⚡ Electrical Safety

- **NEVER** connect the motor power wires directly to the Raspberry Pi.
- **NEVER** use GPIO pins to power the ESC or motor.
- **ALWAYS** ensure common ground between Pi and ESC.
- Use appropriate gauge wires for motor current.
- Use a proper LiPo battery charger and follow LiPo safety guidelines.
- Disconnect the battery when not in use.

### 🔧 Mechanical Safety

- Secure the propeller with a prop nut — a loose propeller is dangerous.
- Keep fingers away from the propeller at all times.
- Test on land (with propeller removed!) before water testing.
- Start with LOW `ESC_MAX_THROTTLE` (e.g., 0.3) and increase gradually.

### 💻 Software Safety

- **Simulation first**: Always test with `SIMULATION_MODE=true` before connecting hardware.
- **Low throttle**: Start with `ESC_MAX_THROTTLE=0.3` and increase only after confirming everything works.
- **Heartbeat watchdog**: The safety controller automatically stops the motor if the WebSocket connection drops.
- **Emergency stop**: The Space key and the red Emergency Stop button work at any time.
- **Connection loss**: If your phone/laptop disconnects from Wi-Fi, the motor stops within 500 ms.

### 🌊 Water Safety

- Waterproof all electronics before water testing.
- Use marine-grade silicone sealant on wire entries.
- Keep a long cord attached to the boat during initial water tests.
- Test in calm, shallow water first.
- Never operate near swimmers or wildlife.
- Have a plan to retrieve the boat if controls fail.

---

## Project Structure

```
rc-boat/
├── frontend/                    # React web dashboard (runs on PC)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ControlDashboard.tsx    # Main dashboard layout
│   │   │   ├── ConnectionStatus.tsx    # Connection & status badges
│   │   │   ├── ThrottleIndicator.tsx   # Vertical throttle gauge
│   │   │   └── SteeringIndicator.tsx   # Horizontal steering gauge
│   │   ├── hooks/
│   │   │   └── useBoatControls.ts      # WebSocket + keyboard hook
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── .env                     # WebSocket URL config
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/                     # Python hardware controller (runs on Pi)
│   ├── main.py                  # FastAPI app + WebSocket endpoint
│   ├── motor_controller.py      # ESC / brushless motor control
│   ├── servo_controller.py      # Servo / rudder control
│   ├── safety_controller.py     # Heartbeat watchdog & emergency stop
│   ├── config.py                # All configurable parameters
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

---

## License

This project is provided as-is for educational and hobby purposes. Use at your own risk.


---

## 14. Camera — Hardware & Setup

### Camera Hardware Requirements

| Component | Description |
|-----------|-------------|
| Raspberry Pi Camera Module v2 | 8 MP Sony IMX219, recommended |
| Raspberry Pi Camera Module v3 | 12 MP, also supported |
| CSI ribbon cable | Comes with the camera module |
| Camera mount / case | For waterproof mounting on the boat |

> Any camera module supported by `libcamera` and `Picamera2` will work.

### Connecting the Camera

1. **Power off** the Raspberry Pi completely.
2. Locate the **CSI camera connector** on the Pi (labelled "CAMERA" or "CAM").
3. Lift the plastic latch on the connector gently.
4. Insert the ribbon cable with the **blue side facing the USB ports** (on Pi 4) or as marked.
5. Press the latch back down firmly.
6. Power on the Pi.

### Verify the Camera is Detected

```bash
# Pi 4 / Pi 5 (libcamera stack)
libcamera-hello --list-cameras

# Should output something like:
# Available cameras
# -----------------
# 0 : imx219 [3280x2464] (/base/soc/i2c0mux/i2c@1/imx219@10)
```

### Install Picamera2

```bash
# Update package list
sudo apt update

# Install Picamera2 and its dependencies
sudo apt install -y python3-picamera2 python3-libcamera

# Or install via pip inside the virtual environment
pip install picamera2
```

### Test the Camera from Command Line

```bash
# Quick preview (opens a window if display is attached, or saves JPEG)
libcamera-jpeg -o test.jpg

# Test MJPEG stream directly (optional)
libcamera-vid -t 0 --codec mjpeg -o - | nc -l 5000
```

### Camera Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_ENABLED` | `true` | Enable/disable camera at startup |
| `CAMERA_WIDTH` | `640` | Frame width in pixels |
| `CAMERA_HEIGHT` | `480` | Frame height in pixels |
| `CAMERA_FPS` | `25` | Target frame rate |
| `CAMERA_JPEG_QUALITY` | `70` | JPEG quality 1–95 (lower = smaller/faster) |
| `CAMERA_ROTATION` | `0` | Rotation: 0, 90, 180, or 270 degrees |
| `CAMERA_RESTART_DELAY` | `2.0` | Seconds to wait before restart on failure |
| `CAMERA_MAX_RESTARTS` | `5` | Max auto-restart attempts |

### Supported Resolutions & FPS

| Resolution | FPS | Use Case |
|------------|-----|----------|
| 640×480 | 25–30 | Default — low latency, good for LAN |
| 1280×720 | 20–25 | HD — more bandwidth required |
| 1920×1080 | 10–15 | Full HD — best quality, highest latency |

> Start with 640×480 @ 25fps. Increase only after confirming stable control.

---

## 15. Camera — Configuration & Tuning

### Backend Startup with Camera

```bash
cd ~/rc-boat/backend
source .venv/bin/activate

# Real hardware — simulation off, camera on
SIMULATION_MODE=false CAMERA_ENABLED=true python main.py

# Simulation mode (no Pi camera needed — synthetic frames generated)
SIMULATION_MODE=true python main.py

# Disable camera (motor control only)
CAMERA_ENABLED=false python main.py
```

### Frontend Startup (Update Camera URL)

Edit `frontend/.env`:

```env
VITE_WS_URL=ws://192.168.1.100:8000/ws/control
VITE_CAMERA_URL=http://192.168.1.100:8000/video
VITE_CAMERA_STATUS_URL=http://192.168.1.100:8000/camera/status
```

Replace `192.168.1.100` with your Raspberry Pi's actual IP.

```bash
cd rc-boat/frontend
npm run dev
```

### Video Stream URLs

| Endpoint | Description |
|----------|-------------|
| `http://<pi-ip>:8000/video` | Live MJPEG stream (open in any browser or `<img>` tag) |
| `http://<pi-ip>:8000/camera/status` | JSON camera status (enabled, running, resolution, fps, clients) |

### Verify Stream in Browser

Open directly in your PC browser:
```
http://192.168.1.100:8000/video
```
You should see the live camera feed immediately.

### Network Configuration

The streaming architecture uses two separate channels:

```
Motor Control:  ws://192.168.1.100:8000/ws/control   (WebSocket, low-overhead)
Camera Stream:  http://192.168.1.100:8000/video       (MJPEG over HTTP)
```

These channels are completely independent. Camera lag or failure **cannot** delay motor control commands.

### Performance & Latency Tuning

**Reduce latency:**
```bash
CAMERA_WIDTH=320 CAMERA_HEIGHT=240 CAMERA_FPS=30 CAMERA_JPEG_QUALITY=60 python main.py
```

**Increase quality (more bandwidth):**
```bash
CAMERA_WIDTH=1280 CAMERA_HEIGHT=720 CAMERA_FPS=20 CAMERA_JPEG_QUALITY=80 python main.py
```

**Recommended starting point for RC boat:**
```bash
CAMERA_WIDTH=640 CAMERA_HEIGHT=480 CAMERA_FPS=25 CAMERA_JPEG_QUALITY=70 python main.py
```

### Simulation Mode (No Physical Camera)

When `SIMULATION_MODE=true`, the camera generates synthetic frames showing:
- Animated colour gradient background
- FPV crosshair reticle
- Corner bracket HUD overlay
- Live timestamp, frame counter, resolution label
- Pulsing liveness dot

This lets you develop and test the full dashboard on any computer without Pi hardware.

---

## 16. Camera — Troubleshooting

### Camera not detected

| Symptom | Fix |
|---------|-----|
| `libcamera-hello` shows no cameras | Check ribbon cable orientation and connector latch |
| `RuntimeError: No cameras available` | Enable camera interface: `sudo raspi-config` → Interface Options → Camera |
| Camera works in `libcamera-hello` but not in Python | Install Picamera2: `pip install picamera2` |

### Stream issues

| Symptom | Fix |
|---------|-----|
| `/video` returns HTTP 503 | Camera not initialized. Check logs: camera may have failed to open |
| Dashboard shows "Camera Offline" | Backend not running, or `VITE_CAMERA_STATUS_URL` IP is wrong |
| Stream loads but is frozen | JPEG quality too high for Wi-Fi bandwidth — reduce `CAMERA_JPEG_QUALITY` |
| High latency (> 500 ms) | Reduce resolution or FPS. Check Wi-Fi signal strength |
| Stream drops intermittently | Increase `CAMERA_RESTART_DELAY`. Check for thermal throttling on the Pi |
| Green/corrupted image | Wrong camera rotation — try `CAMERA_ROTATION=90` or `180` |

### Check camera logs

```bash
# Run backend with debug logging to see every frame
LOG_LEVEL=debug SIMULATION_MODE=false python main.py 2>&1 | grep -i cam
```

### Test camera status endpoint

```bash
curl http://<pi-ip>:8000/camera/status
# Expected response:
# {"enabled":true,"running":true,"resolution":{"width":640,"height":480},"framerate":25,"active_clients":0}
```

### Motor control unaffected by camera failure

If the camera fails, motor control continues working. The camera runs in an **isolated daemon thread** — any exception in the camera thread is logged and the camera attempts to restart automatically, but the asyncio event loop (motor/servo/safety) is never interrupted.

To confirm motor control is independent:
1. Start backend with `CAMERA_ENABLED=false`
2. Connect dashboard and arm the motor normally
3. Enable camera dynamically (restart backend with camera on) — controls remain active
