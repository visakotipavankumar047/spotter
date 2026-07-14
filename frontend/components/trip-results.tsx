"use client";

import { StatStrip } from "@/components/stat-strip";
import { RouteMap } from "@/components/route-map";
import { StopsSchedule } from "@/components/stops-schedule";
import { LogSheet } from "@/components/log-sheet";
import { Badge } from "@/components/ui/badge";
import type { DailyLog, TripResponse } from "@/lib/types";
import { AlertTriangle } from "lucide-react";

function buildLogMeta(
  logs: DailyLog[],
  startingCycleHours: number
): {
  milesToDate: number;
  onDutyLast7: number;
  hoursAvailableTomorrow: number;
}[] {
  const result: {
    milesToDate: number;
    onDutyLast7: number;
    hoursAvailableTomorrow: number;
  }[] = [];

  let miles = 0;
  let onDuty = startingCycleHours;

  for (const log of logs) {
    miles += log.total_miles_today;
    onDuty += log.totals.driving + log.totals.on_duty_not_driving;
    const onDutyLast7 = Math.min(70, onDuty);
    result.push({
      milesToDate: miles,
      onDutyLast7,
      hoursAvailableTomorrow: Math.max(0, 70 - onDutyLast7),
    });
  }

  return result;
}

export function TripResults({ trip }: { trip: TripResponse }) {
  const cycleUsedAfter = Math.max(
    0,
    70 - trip.summary.cycle_hours_remaining_at_finish
  );

  const logMeta = buildLogMeta(
    trip.daily_logs,
    trip.current_cycle_used_hours ?? 0
  );

  return (
    <div className="space-y-8">
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <p className="section-label">Trip Summary</p>
          {trip.summary.restarts_required > 0 && (
            <Badge className="gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90">
              <AlertTriangle className="h-3 w-3" />
              {trip.summary.restarts_required} restart
              {trip.summary.restarts_required > 1 ? "s" : ""} required
            </Badge>
          )}
        </div>
        <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground md:text-3xl">
          {trip.current_location} → {trip.pickup_location} →{" "}
          {trip.dropoff_location}
        </h2>
        <div className="mt-4">
          <StatStrip summary={trip.summary} cycleUsedAfter={cycleUsedAfter} />
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <p className="section-label">Route Map</p>
          <span className="text-xs text-muted-foreground">
            OpenFreeMap · live route geometry
          </span>
        </div>
        <RouteMap geometry={trip.route.geometry} stops={trip.route.stops} />
      </section>

      <StopsSchedule stops={trip.route.stops} />

      <section>
        <p className="section-label mb-3">
          Daily Log Sheets ({trip.daily_logs.length})
        </p>
        <div className="space-y-5">
          {trip.daily_logs.map((log, idx) => (
            <LogSheet
              key={`${log.date}-${idx}`}
              log={log}
              dayIndex={idx}
              totalDays={trip.daily_logs.length}
              fromLocation={trip.current_location}
              toLocation={trip.dropoff_location}
              milesToDate={logMeta[idx].milesToDate}
              onDutyLast7={logMeta[idx].onDutyLast7}
              hoursAvailableTomorrow={logMeta[idx].hoursAvailableTomorrow}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
