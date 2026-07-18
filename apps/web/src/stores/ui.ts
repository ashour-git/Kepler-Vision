"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

type Theme = "light" | "dark" | "system";
type Density = "comfortable" | "compact";

interface UiState {
  theme: Theme;
  density: Density;
  leftRailCollapsed: boolean;
  setTheme: (theme: Theme) => void;
  setDensity: (density: Density) => void;
  toggleLeftRail: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: "system",
      density: "comfortable",
      leftRailCollapsed: false,
      setTheme: (theme) => set({ theme }),
      setDensity: (density) => set({ density }),
      toggleLeftRail: () => set((s) => ({ leftRailCollapsed: !s.leftRailCollapsed })),
    }),
    {
      name: "kepler.ui.v1",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
