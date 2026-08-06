import { create } from "zustand";
import { getWebSocketUrl, refreshSession } from "@/lib/api-client";

type Status = "disconnected" | "connecting" | "connected" | "reconnecting";
type Listener = (event: Record<string, unknown>) => void;
type State = {
  socket: WebSocket | null;
  status: Status;
  reconnectAttempts: number;
  listeners: Set<Listener>;
  connect: () => void;
  disconnect: () => void;
  sendEvent: (event: unknown) => boolean;
  subscribe: (listener: Listener) => () => void;
};

let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let intentionalClose = false;

export const useWebSocketStore = create<State>((set, get) => ({
  socket: null,
  status: "disconnected",
  reconnectAttempts: 0,
  listeners: new Set(),
  connect: () => {
    const existing = get().socket;
    if (existing?.readyState === WebSocket.OPEN || existing?.readyState === WebSocket.CONNECTING) return;
    intentionalClose = false;
    set({ status: get().reconnectAttempts ? "reconnecting" : "connecting" });
    const socket = new WebSocket(getWebSocketUrl());
    socket.onopen = () => set({ socket, status: "connected", reconnectAttempts: 0 });
    socket.onmessage = (message) => {
      try { get().listeners.forEach((listener) => listener(JSON.parse(message.data))); } catch { /* Ignore malformed server frames. */ }
    };
    socket.onclose = async (event) => {
      set({ socket: null, status: "disconnected" });
      if (intentionalClose) return;
      if (event.code === 4401) {
        try {
          await refreshSession();
          get().connect();
          return;
        } catch {
          return;
        }
      }
      const attempt = get().reconnectAttempts + 1;
      set({ reconnectAttempts: attempt, status: "reconnecting" });
      const delay = Math.min(15_000, 1000 * 2 ** Math.min(attempt - 1, 4)) + Math.random() * 500;
      reconnectTimer = setTimeout(() => get().connect(), delay);
    };
    set({ socket });
  },
  disconnect: () => {
    intentionalClose = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    get().socket?.close();
    set({ socket: null, status: "disconnected", reconnectAttempts: 0 });
  },
  sendEvent: (event) => {
    const socket = get().socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(event));
    return true;
  },
  subscribe: (listener) => {
    get().listeners.add(listener);
    return () => { get().listeners.delete(listener); };
  },
}));
