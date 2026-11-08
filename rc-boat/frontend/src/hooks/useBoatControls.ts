import { useState, useEffect, useRef, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface BoatState {
  connected: boolean;
  armed: boolean;
  throttle: number;
  steering: number;
  emergencyStopped: boolean;
  simulation: boolean;
  keysPressed: {
    w: boolean;
    a: boolean;
    d: boolean;
  };
}

export interface BoatControls {
  state: BoatState;
  arm: () => void;
  disarm: () => void;
  emergencyStop: () => void;
}

// Messages sent from client to server
interface ControlMessage {
  type: 'control';
  key: 'w' | 'a' | 'd' | 's' | 'space';
  action: 'press' | 'release';
}

interface HeartbeatMessage {
  type: 'heartbeat';
}

interface ArmMessage {
  type: 'arm';
}

interface DisarmMessage {
  type: 'disarm';
}

type ClientMessage = ControlMessage | HeartbeatMessage | ArmMessage | DisarmMessage;

// Messages received from server
interface StatusMessage {
  type: 'status';
  throttle: number;
  steering: number;
  armed: boolean;
  emergency_stopped: boolean;
  simulation: boolean;
}

interface HeartbeatAckMessage {
  type: 'heartbeat_ack';
}

interface ErrorMessage {
  type: 'error';
  message: string;
}

type ServerMessage = StatusMessage | HeartbeatAckMessage | ErrorMessage;

// ── Constants ──────────────────────────────────────────────────────────────────

const HEARTBEAT_INTERVAL_MS = 200;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 8000;
const CONTROL_KEYS = new Set(['w', 'a', 'd', 's', ' ']);
const RELEASE_KEYS = new Set(['w', 'a', 'd']);
const INPUT_ELEMENTS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useBoatControls(): BoatControls {
  const [state, setState] = useState<BoatState>({
    connected: false,
    armed: false,
    throttle: 0,
    steering: 0,
    emergencyStopped: false,
    simulation: false,
    keysPressed: { w: false, a: false, d: false },
  });

  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS);
  const mountedRef = useRef(true);
  const keysPressedRef = useRef<Set<string>>(new Set());

  // ── WebSocket Send Helper ──────────────────────────────────────────────────

  const sendMessage = useCallback((message: ClientMessage) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }, []);

  // ── Heartbeat Management ──────────────────────────────────────────────────

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatTimerRef.current = setInterval(() => {
      sendMessage({ type: 'heartbeat' });
    }, HEARTBEAT_INTERVAL_MS);
  }, [sendMessage]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current !== null) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // ── WebSocket Connection ──────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/control';

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
    } catch {
      // Schedule reconnect if WebSocket constructor fails
      scheduleReconnect();
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS;
      setState((prev) => ({ ...prev, connected: true }));
      startHeartbeat();
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      stopHeartbeat();
      setState((prev) => ({ ...prev, connected: false }));
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will be called after onerror, so we just let onclose handle reconnect
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;

      let data: ServerMessage;
      try {
        data = JSON.parse(event.data as string) as ServerMessage;
      } catch {
        return; // Ignore malformed messages
      }

      switch (data.type) {
        case 'status':
          setState((prev) => ({
            ...prev,
            throttle: data.throttle,
            steering: data.steering,
            armed: data.armed,
            emergencyStopped: data.emergency_stopped,
            simulation: data.simulation,
          }));
          break;
        case 'heartbeat_ack':
          // Connection is alive — nothing to update
          break;
        case 'error':
          console.error('[RC Boat WS] Server error:', data.message);
          break;
      }
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startHeartbeat, stopHeartbeat]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectTimerRef.current !== null) return;

    const delay = reconnectDelayRef.current;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      // Exponential backoff
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 2,
        MAX_RECONNECT_DELAY_MS,
      );
      connect();
    }, delay);
  }, [connect]);

  // ── Public Actions ────────────────────────────────────────────────────────

  const arm = useCallback(() => {
    sendMessage({ type: 'arm' });
  }, [sendMessage]);

  const disarm = useCallback(() => {
    sendMessage({ type: 'disarm' });
  }, [sendMessage]);

  const emergencyStop = useCallback(() => {
    // Send the space key press as emergency stop
    sendMessage({ type: 'control', key: 'space', action: 'press' });
    // Also update local state immediately for responsiveness
    setState((prev) => ({ ...prev, emergencyStopped: true }));
  }, [sendMessage]);

  // ── Keyboard Event Handlers ───────────────────────────────────────────────

  useEffect(() => {
    const normalizeKey = (key: string): string => {
      return key === ' ' ? 'space' : key.toLowerCase();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't capture when typing in form elements
      const target = event.target as HTMLElement;
      if (INPUT_ELEMENTS.has(target.tagName)) return;
      if (target.isContentEditable) return;

      const key = event.key.toLowerCase();

      // Only handle our control keys
      if (!CONTROL_KEYS.has(key)) return;

      // Prevent default browser behavior (e.g., scrolling with space)
      event.preventDefault();

      // Prevent key repeat
      if (event.repeat) return;

      const normalizedKey = normalizeKey(key);
      keysPressedRef.current.add(key);

      // Update keysPressed state for visual indicators
      if (key === 'w' || key === 'a' || key === 'd') {
        setState((prev) => ({
          ...prev,
          keysPressed: { ...prev.keysPressed, [key]: true },
        }));
      }

      // Send control message
      sendMessage({
        type: 'control',
        key: normalizedKey as ControlMessage['key'],
        action: 'press',
      });
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (INPUT_ELEMENTS.has(target.tagName)) return;
      if (target.isContentEditable) return;

      const key = event.key.toLowerCase();

      if (!CONTROL_KEYS.has(key)) return;

      event.preventDefault();

      keysPressedRef.current.delete(key);

      // Only send release for keys that support it (w, a, d)
      if (RELEASE_KEYS.has(key)) {
        const normalizedKey = normalizeKey(key);

        setState((prev) => ({
          ...prev,
          keysPressed: { ...prev.keysPressed, [key]: false },
        }));

        sendMessage({
          type: 'control',
          key: normalizedKey as ControlMessage['key'],
          action: 'release',
        });
      }
    };

    // Handle window blur — release all pressed keys
    const handleBlur = () => {
      const pressed = keysPressedRef.current;
      pressed.forEach((key) => {
        if (RELEASE_KEYS.has(key)) {
          const normalizedKey = normalizeKey(key);
          sendMessage({
            type: 'control',
            key: normalizedKey as ControlMessage['key'],
            action: 'release',
          });
        }
      });
      pressed.clear();
      setState((prev) => ({
        ...prev,
        keysPressed: { w: false, a: false, d: false },
      }));
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [sendMessage]);

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      stopHeartbeat();

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, stopHeartbeat]);

  return { state, arm, disarm, emergencyStop };
}
