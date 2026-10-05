"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { SocketStatus } from "./ws";

/** WebSocket connection state per room (transient). */
type ConnectionState = {
  status: Record<string, SocketStatus>;
  setStatus: (roomId: string, status: SocketStatus) => void;
};

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: {},
  setStatus: (roomId, status) => set((s) => ({ status: { ...s.status, [roomId]: status } })),
}));

/** Small persisted UI preferences (per tab). */
type UiState = {
  presentation: boolean;
  activeRoomId: string | null;
  setPresentation: (value: boolean) => void;
  setActiveRoomId: (id: string | null) => void;
};

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      presentation: false,
      activeRoomId: null,
      setPresentation: (presentation) => set({ presentation }),
      setActiveRoomId: (activeRoomId) => set({ activeRoomId }),
    }),
    {
      name: "fogroom-ui",
      storage: createJSONStorage(() =>
        typeof window === "undefined"
          ? { getItem: () => null, setItem: () => undefined, removeItem: () => undefined }
          : window.sessionStorage,
      ),
    },
  ),
);
