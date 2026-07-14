import type { TripSummary } from "@/lib/types";

export function StatStrip({
  summary,
  cycleUsedAfter,
}: {
  summary: TripSummary;
  cycleUsedAfter: number;
}) {
  const stats = [
    {
      label: "Total Distance",
      value: `${summary.total_distance_miles.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })} mi`,
    },
    {
      label: "Driving Time",
      value: `${summary.total_drive_hours.toFixed(1)} hrs`,
    },
    {
      label: "Trip Length",
      value: `${summary.num_days} day${summary.num_days === 1 ? "" : "s"}`,
    },
    {
      label: "Cycle Hrs Used After",
      value: `${cycleUsedAfter.toFixed(1)} / 70 hrs`,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-md bg-muted px-4 py-3">
          <p className="section-label text-[10px]">{stat.label}</p>
          <p className="mt-1 font-heading text-xl font-bold tracking-tight text-foreground">
            {stat.value}
          </p>
        </div>
      ))}
    </div>
  );
}
