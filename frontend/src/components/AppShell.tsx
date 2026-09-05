import { Outlet } from "react-router-dom"

import { MainSidebar } from "@/components/MainSidebar"

/**
 * Outer shell for every authenticated route. Contains just the global
 * sidebar; each page controls its own header + inner layout so the chat
 * surface (with its session sub-sidebar) doesn't need to fight this
 * shell for space.
 */
export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <MainSidebar />
      {/*
        Regular worker pages, especially the clause-by-clause Contract Reader,
        can exceed one viewport. Keep chat's own inner transcript scroller,
        but make the shell's content pane vertically scrollable for every
        other route instead of clipping it at the viewport boundary.
      */}
      <main className="flex min-h-0 min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
