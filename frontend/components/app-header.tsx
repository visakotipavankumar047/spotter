"use client";

import { Truck, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-white px-4 md:px-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Truck className="h-5 w-5 text-foreground" strokeWidth={2.25} />
          <span className="font-heading text-lg font-bold tracking-tight text-foreground">
            Spotter
          </span>
        </div>
        <span className="rounded border border-primary px-2 py-0.5 text-[11px] font-medium text-primary">
          ELD Trip Planner
        </span>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="no-print gap-2 border-foreground/20 bg-white text-foreground hover:bg-muted"
        onClick={() => window.print()}
      >
        <Printer className="h-4 w-4" />
        <span className="hidden sm:inline">Print / Save as PDF</span>
      </Button>
    </header>
  );
}
