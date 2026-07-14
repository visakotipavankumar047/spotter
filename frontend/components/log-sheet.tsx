"use client";

import { useEffect, useRef } from "react";
import type { DailyLog } from "@/lib/types";

const STATUS_ROWS = [
  { key: "OFF_DUTY", label: "1. Off Duty", totalKey: "off_duty" as const },
  {
    key: "SLEEPER_BERTH",
    label: "2. Sleeper Berth",
    totalKey: "sleeper_berth" as const,
  },
  { key: "DRIVING", label: "3. Driving", totalKey: "driving" as const },
  {
    key: "ON_DUTY_NOT_DRIVING",
    label: "4. On Duty (not driving)",
    totalKey: "on_duty_not_driving" as const,
  },
] as const;

const LEFT = 148;
const RIGHT = 56;
const TOP = 28;
const ROW_H = 40;
const GRID_W = 24 * 28;
const SVG_W = LEFT + GRID_W + RIGHT;
const SVG_H = TOP + ROW_H * 4 + 8;

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function xAt(minutes: number): number {
  return LEFT + (minutes / 60) * 28;
}

function yAt(status: string): number {
  const idx = STATUS_ROWS.findIndex((r) => r.key === status);
  return TOP + idx * ROW_H + ROW_H / 2;
}

function formatDate(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatRemarkTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return `${hour}:${m.toString().padStart(2, "0")} ${period}`;
}

export function LogSheet({
  log,
  dayIndex,
  totalDays,
  fromLocation,
  toLocation,
  milesToDate,
  onDutyLast7,
  hoursAvailableTomorrow,
}: {
  log: DailyLog;
  dayIndex: number;
  totalDays: number;
  fromLocation: string;
  toLocation: string;
  milesToDate: number;
  onDutyLast7: number;
  hoursAvailableTomorrow: number;
}) {
  const pathRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced || !pathRef.current) return;

    const length = pathRef.current.getTotalLength();
    pathRef.current.style.strokeDasharray = `${length}`;
    pathRef.current.style.strokeDashoffset = `${length}`;

    const frame = requestAnimationFrame(() => {
      if (!pathRef.current) return;
      pathRef.current.style.transition = "stroke-dashoffset 1.4s ease-in-out";
      pathRef.current.style.strokeDashoffset = "0";
    });

    return () => cancelAnimationFrame(frame);
  }, [log.date]);

  const segments = log.segments;
  if (!segments.length) return null;

  const points: { x: number; y: number }[] = [];
  for (const seg of segments) {
    const x1 = xAt(toMinutes(seg.start));
    const x2 = xAt(toMinutes(seg.end));
    const y = yAt(seg.status);
    if (!points.length) points.push({ x: x1, y });
    else points.push({ x: points[points.length - 1].x, y });
    points.push({ x: x2, y });
  }

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  return (
    <article className="overflow-hidden rounded-md border border-border bg-muted">
      <div className="flex items-start justify-between gap-4 border-b border-border px-5 pt-5 pb-4">
        <div>
          <h3 className="font-heading text-xl font-bold text-foreground">
            Driver&apos;s Daily Log
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            (24 hours) · Original – file at home terminal · Duplicate – driver
            retains 8 days
          </p>
        </div>
        <div className="text-right">
          <p className="font-semibold text-foreground">{formatDate(log.date)}</p>
          <p className="text-xs text-muted-foreground">
            Day {dayIndex + 1} of {totalDays} days
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-b border-border">
        <div className="border-r border-border px-5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            From
          </p>
          <p className="font-semibold text-foreground">{fromLocation}</p>
        </div>
        <div className="px-5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            To
          </p>
          <p className="font-semibold text-foreground">{toLocation}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 border-b border-border">
        <div className="border-r border-border px-5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Total Miles Driving Today
          </p>
          <p className="font-semibold text-foreground">
            {log.total_miles_today.toLocaleString(undefined, {
              maximumFractionDigits: 0,
            })}{" "}
            mi
          </p>
        </div>
        <div className="border-r border-border px-5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Total Mileage To Date
          </p>
          <p className="font-semibold text-foreground">
            {milesToDate.toLocaleString(undefined, {
              maximumFractionDigits: 0,
            })}{" "}
            mi
          </p>
        </div>
        <div className="px-5 py-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Carrier / Truck-Trailer No.
          </p>
          <p className="font-semibold text-foreground">
            Spotter Freight Co. · Unit 4471 / Trlr 8823
          </p>
        </div>
      </div>

      <div className="overflow-x-auto border-b border-border px-2 py-3">
        <svg
          width={SVG_W}
          height={SVG_H}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="mx-auto block min-w-[720px]"
        >
          {Array.from({ length: 25 }, (_, h) => h).map((h) => {
            const x = xAt(h * 60);
            return (
              <g key={h}>
                <line
                  x1={x}
                  y1={TOP}
                  x2={x}
                  y2={TOP + ROW_H * 4}
                  stroke="#d4d4d4"
                  strokeWidth={h % 6 === 0 ? 1.25 : 0.5}
                />
                {h < 24 && (
                  <text
                    x={x + 2}
                    y={TOP - 10}
                    fontSize="9"
                    fill="#8a8a8a"
                    fontFamily="system-ui,sans-serif"
                  >
                    {h}
                  </text>
                )}
              </g>
            );
          })}

          {Array.from({ length: 96 }, (_, i) => i * 15).map((min) => {
            if (min % 60 === 0) return null;
            const x = xAt(min);
            return (
              <line
                key={min}
                x1={x}
                y1={TOP + ROW_H * 4}
                x2={x}
                y2={TOP + ROW_H * 4 + (min % 30 === 0 ? 5 : 3)}
                stroke="#c4c4c4"
                strokeWidth={0.5}
              />
            );
          })}

          {STATUS_ROWS.map((row, i) => {
            const y = TOP + i * ROW_H;
            return (
              <g key={row.key}>
                <line
                  x1={LEFT}
                  y1={y}
                  x2={LEFT + GRID_W}
                  y2={y}
                  stroke="#d4d4d4"
                  strokeWidth={0.5}
                />
                <text
                  x={8}
                  y={y + ROW_H / 2 + 4}
                  fontSize="11"
                  fill="#333"
                  fontFamily="system-ui,sans-serif"
                >
                  {row.label}
                </text>
                <text
                  x={LEFT + GRID_W + 10}
                  y={y + ROW_H / 2 + 4}
                  fontSize="12"
                  fontWeight="700"
                  fill="#111"
                  fontFamily="system-ui,sans-serif"
                >
                  {log.totals[row.totalKey].toFixed(1)}
                </text>
              </g>
            );
          })}

          <line
            x1={LEFT}
            y1={TOP + ROW_H * 4}
            x2={LEFT + GRID_W}
            y2={TOP + ROW_H * 4}
            stroke="#b0b0b0"
            strokeWidth={1}
          />

          <path
            ref={pathRef}
            d={pathD}
            fill="none"
            stroke="#e54d2d"
            strokeWidth={2.25}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <div className="grid gap-0 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="border-b border-border px-5 py-4 md:border-r md:border-b-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Remarks
          </p>
          <ul className="mt-2 space-y-1.5">
            {log.remarks.map((r, i) => (
              <li key={`${r.time}-${i}`} className="text-sm text-foreground">
                <span className="text-muted-foreground">
                  {formatRemarkTime(r.time)}
                </span>
                {" — "}
                {r.note}
                {r.location ? `, ${r.location}` : ""}
              </li>
            ))}
            {!log.remarks.length && (
              <li className="text-sm text-muted-foreground">No remarks</li>
            )}
          </ul>
        </div>
        <div className="border-b border-border px-5 py-4 md:border-r md:border-b-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            A. On-Duty Hrs, Last 7 Days Incl. Today
          </p>
          <p className="mt-2 text-lg font-bold text-foreground">
            {onDutyLast7.toFixed(1)} hrs
          </p>
        </div>
        <div className="px-5 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            B. Hours Available Tomorrow
          </p>
          <p className="mt-2 text-lg font-bold text-foreground">
            {hoursAvailableTomorrow.toFixed(1)} hrs
          </p>
        </div>
      </div>
    </article>
  );
}
