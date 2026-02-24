import { create } from "zustand";
import type { ViewName } from "../types";

interface AppState {
  currentView: ViewName;
  sidebarExpanded: boolean;
  serverUrl: string;
  isConnected: boolean;
  setCurrentView: (view: ViewName) => void;
  toggleSidebar: () => void;
  setConnected: (connected: boolean) => void;
}

// 从环境变量读取后端 URL，默认本地地址
const getBackendUrl = () => {
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  return "http://127.0.0.1:8420";
};

export const useAppStore = create<AppState>((set) => ({
  currentView: "chat",
  sidebarExpanded: true,
  serverUrl: getBackendUrl(),
  isConnected: false,
  setCurrentView: (view) => set({ currentView: view }),
  toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),
  setConnected: (connected) => set({ isConnected: connected }),
}));
