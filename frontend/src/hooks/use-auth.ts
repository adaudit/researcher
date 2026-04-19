"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: string | null;
  activeWorkspaceId: string | null;
  workspaces: Array<{ id: string; name: string; slug: string; role: string }>;
  setAuth: (token: string, userId: string, workspaceId: string) => void;
  setWorkspaces: (workspaces: AuthState["workspaces"]) => void;
  switchWorkspace: (workspaceId: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      activeWorkspaceId: null,
      workspaces: [],
      setAuth: (token, userId, workspaceId) =>
        set({ token, userId, activeWorkspaceId: workspaceId }),
      setWorkspaces: (workspaces) => set({ workspaces }),
      switchWorkspace: (workspaceId) => set({ activeWorkspaceId: workspaceId }),
      logout: () =>
        set({ token: null, userId: null, activeWorkspaceId: null, workspaces: [] }),
    }),
    { name: "researcher-auth" },
  ),
);
