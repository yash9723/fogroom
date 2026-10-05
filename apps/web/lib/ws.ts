import { serverFrameSchema, type RoomEvent } from "@fogroom/shared";
import { WS_URL } from "./config";

export type SocketStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "unauthorized";

type Handlers = {
  onStatus: (status: SocketStatus) => void;
  onHello: (lastSeq: number) => void;
  onEvent: (event: RoomEvent) => void;
};

/**
 * Room WebSocket with first-frame authentication, keep-alive pings and exponential
 * reconnect. Frames are validated with zod before reaching the app. Missed events are
 * recovered by the caller via REST `/sync?since_seq=` after each (re)connect.
 */
export class RoomSocket {
  private ws: WebSocket | null = null;
  private attempts = 0;
  private stopped = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly roomId: string,
    private readonly getToken: () => string | null,
    private readonly handlers: Handlers,
  ) {}

  connect(): void {
    this.stopped = false;
    this.open();
  }

  close(): void {
    this.stopped = true;
    this.clearTimers();
    this.ws?.close(1000, "client closing");
    this.ws = null;
    this.handlers.onStatus("closed");
  }

  private open(): void {
    const token = this.getToken();
    if (!token) {
      this.handlers.onStatus("unauthorized");
      return;
    }
    this.handlers.onStatus(this.attempts === 0 ? "connecting" : "reconnecting");
    const ws = new WebSocket(`${WS_URL}/ws/rooms/${this.roomId}`);
    this.ws = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", token }));
    };
    ws.onmessage = (msg) => {
      let data: unknown;
      try {
        data = JSON.parse(String(msg.data));
      } catch {
        return;
      }
      const parsed = serverFrameSchema.safeParse(data);
      if (!parsed.success) return;
      const frame = parsed.data;
      if (frame.type === "hello") {
        this.attempts = 0;
        this.handlers.onStatus("open");
        this.handlers.onHello(frame.last_seq);
        this.startPing();
      } else if (frame.type === "event") {
        this.handlers.onEvent(frame.event);
      } else if (frame.type === "error") {
        this.handlers.onStatus("unauthorized");
      }
    };
    ws.onclose = (ev) => {
      this.clearTimers();
      if (this.stopped) return;
      if (ev.code === 4403) {
        this.handlers.onStatus("unauthorized");
        return;
      }
      this.scheduleReconnect();
    };
    ws.onerror = () => {
      /* onclose handles reconnect */
    };
  }

  private scheduleReconnect(): void {
    this.attempts += 1;
    const delay = Math.min(15_000, 500 * 2 ** Math.min(this.attempts, 5)) + Math.random() * 300;
    this.handlers.onStatus("reconnecting");
    this.retryTimer = setTimeout(() => this.open(), delay);
  }

  private startPing(): void {
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "ping" }));
    }, 20_000);
  }

  private clearTimers(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.pingTimer = null;
    this.retryTimer = null;
  }
}
