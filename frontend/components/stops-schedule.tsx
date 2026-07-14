import {
  MapPin,
  Package,
  Fuel,
  Clock,
  CheckSquare,
} from "lucide-react";
import type { RouteStop } from "@/lib/types";

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)} hr`;
}

function formatArrival(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function stopIcon(type: RouteStop["type"]) {
  switch (type) {
    case "pickup":
      return { Icon: Package, className: "bg-primary text-white" };
    case "dropoff":
      return { Icon: CheckSquare, className: "bg-primary text-white" };
    case "fuel":
      return { Icon: Fuel, className: "bg-primary text-white" };
    case "rest":
      return { Icon: Clock, className: "bg-neutral-700 text-white" };
    default:
      return { Icon: MapPin, className: "bg-foreground text-white" };
  }
}

function stopTitle(stop: RouteStop): string {
  const label = stop.label.toLowerCase();
  if (label.includes("30")) return "30-minute break";
  if (label.includes("10")) return "10-hr off-duty reset";
  if (label.includes("34")) return "34-hour restart";
  if (stop.type === "pickup") return "Pickup";
  if (stop.type === "dropoff") return "Drop-off";
  if (stop.type === "fuel") return "Fuel stop";
  return stop.label;
}

export function StopsSchedule({ stops }: { stops: RouteStop[] }) {
  if (!stops.length) return null;

  return (
    <section>
      <p className="section-label mb-3">Stops & Rest Schedule</p>
      <div className="overflow-hidden rounded-md bg-muted">
        <ul>
          {stops.map((stop, idx) => {
            const { Icon, className } = stopIcon(stop.type);
            const place = stop.location || stop.label;
            const mile =
              typeof stop.mile_marker === "number"
                ? `mile ${stop.mile_marker.toLocaleString()}`
                : null;

            return (
              <li
                key={`${stop.type}-${stop.arrival}-${idx}`}
                className="flex items-center gap-3 border-b border-border/70 px-4 py-3 last:border-b-0"
              >
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${className}`}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {stopTitle(stop)}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {[place, formatArrival(stop.arrival), mile]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <span className="shrink-0 rounded bg-white/80 px-2 py-1 text-xs text-muted-foreground">
                  {formatDuration(stop.duration_min)}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
