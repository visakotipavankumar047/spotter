"use client";

import { use, useEffect, useState } from "react";
import { AppHeader } from "@/components/app-header";
import { TripForm } from "@/components/trip-form";
import { TripResults } from "@/components/trip-results";
import { Button } from "@/components/ui/button";
import type { TripResponse } from "@/lib/types";
import { Loader2, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";

export default function TripResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTrip() {
      try {
        const res = await fetch(`/api/trips/${id}`);
        if (!res.ok) {
          throw new Error(`Failed to load trip (${res.status})`);
        }
        const data = await res.json();
        setTrip(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load trip");
      } finally {
        setLoading(false);
      }
    }
    fetchTrip();
  }, [id]);

  return (
    <div className="flex min-h-full flex-col bg-white">
      <AppHeader />
      <div className="flex flex-1 flex-col lg:flex-row">
        <aside className="no-print w-full shrink-0 border-b border-border p-5 md:p-6 lg:w-[340px] lg:border-r lg:border-b-0 xl:w-[380px]">
          {trip ? (
            <TripForm
              key={trip.trip_id}
              initial={{
                current_location: trip.current_location,
                pickup_location: trip.pickup_location,
                dropoff_location: trip.dropoff_location,
                current_cycle_used_hours: trip.current_cycle_used_hours,
              }}
            />
          ) : (
            <TripForm key="loading" />
          )}
        </aside>

        <main className="flex-1 overflow-y-auto p-5 md:p-8">
          {loading && (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {!loading && (error || !trip) && (
            <div className="flex h-64 flex-col items-center justify-center gap-4">
              <AlertTriangle className="h-10 w-10 text-primary" />
              <p className="text-muted-foreground">
                {error || "Trip not found"}
              </p>
              <Button variant="outline" onClick={() => router.push("/")}>
                Back to planner
              </Button>
            </div>
          )}

          {!loading && trip && <TripResults trip={trip} />}
        </main>
      </div>
    </div>
  );
}
