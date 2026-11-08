# 🚤 AquaClean — Wi-Fi Controlled RC Boat with FPV Camera

AquaClean is a complete Wi-Fi-controlled RC boat system featuring real-time low-latency keyboard controls and continuous FPV (First Person View) live video streaming from a Raspberry Pi camera to a PC web dashboard.

---

## 🏗️ System Architecture

```text
PC (Web Browser)
      │
      ├────────────────── Keyboard Input (W, A, S, D, Space)
      │                   via WebSocket (ws://<pi-ip>:8000/ws/control)
      │
      └────────────────── Live FPV Video Feed
                          via MJPEG HTTP Stream (http://<pi-ip>:8000/video)
      ▼
Raspberry Pi (FastAPI Backend + Picamera2)
      │
      ├────────────────── GPIO 18 (PWM) ──► ESC ──► Brushless Propulsion Motor
      │
      ├────────────────── GPIO 19 (PWM) ──► Servo Motor ──► Rudder Steering
      │
      └────────────────── CSI Interface  ──► Camera Module (OV5647/IMX219)
```

---

## 📁 Repository Structure

```text
AquaClean/
│
├── rc-boat/
│   ├── backend/                     # Python FastAPI server (runs on Raspberry Pi)
│   │   ├── camera/                  # Camera controller & MJPEG streaming service
│   │   │   ├── camera_config.py
│   │   │   ├── camera_controller.py
│   │   │   └── streaming_service.py
│   │   ├── config.py                # Hardware pins, PWM pulse widths & safety settings
│   │   ├── motor_controller.py      # ESC & brushless motor control (lgpio)
│   │   ├── servo_controller.py      # Rudder servo control (lgpio)
│   │   ├── safety_controller.py     # Heartbeat watchdog & emergency stop
│   │   ├── main.py                  # FastAPI app & WebSocket endpoint
│   │   └── requirements.txt
│   │
│   ├── frontend/                    # React + Vite + Tailwind dashboard (runs on PC)
│   │   ├── src/
│   │   │   ├── components/          # CameraStream, Dashboard, Gauges, Status
│   │   │   ├── hooks/               # useBoatControls, useCameraStream
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── .env.example             # Template for network configuration
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   └── README.md                    # Detailed circuit wiring, ESC calibration & setup
│
├── .gitignore
└── README.md
```

---

## 🎮 Navigation Controls

| Key | Action | Physical Output | Behavior |
|:---:|:---|:---|:---|
| <kbd>W</kbd> | **Forward** | ESC / Brushless Motor | Smooth throttle acceleration to configurable limit (default 70%) |
| **Release** <kbd>W</kbd> | **Coast / Idle** | ESC Neutral | Throttle smoothly ramps down to neutral |
| <kbd>A</kbd> | **Steer Left** | Rudder Servo | Deflects rudder left up to limit (−45°) |
| <kbd>D</kbd> | **Steer Right** | Rudder Servo | Deflects rudder right up to limit (+45°) |
| **Release** <kbd>A</kbd> / <kbd>D</kbd> | **Center** | Rudder Servo | Rudder automatically returns to dead center (0°) |
| <kbd>S</kbd> | **Stop Motor** | ESC Neutral | Immediate motor stop |
| <kbd>Space</kbd> | **Emergency Stop** | Instant Cutoff | Overrides all inputs, cuts throttle immediately |

---

## 🚀 Quick Start

### 1. Raspberry Pi Setup (Backend)
```bash
cd rc-boat/backend
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
SIMULATION_MODE=false python main.py
```

### 2. PC Setup (Frontend)
```bash
cd rc-boat/frontend
cp .env.example .env
# Edit .env with your Raspberry Pi's IP address
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

For complete wiring diagrams, pinouts, and ESC arming instructions, see [`rc-boat/README.md`](rc-boat/README.md).
