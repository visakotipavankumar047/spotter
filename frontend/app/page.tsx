import { AppHeader } from "@/components/app-header";
import { TripForm } from "@/components/trip-form";

export default function Home() {
  return (
    <div className="flex min-h-full flex-col bg-white">
      <AppHeader />
      <div className="flex flex-1 flex-col lg:flex-row">
        <aside className="w-full shrink-0 border-b border-border p-5 md:p-6 lg:w-[340px] lg:border-r lg:border-b-0 xl:w-[380px]">
          <TripForm />
        </aside>
        <main className="flex flex-1 items-center justify-center bg-white p-8 md:p-12">
          <div className="max-w-md text-center">
            <p className="section-label">Ready</p>
            <h2 className="mt-2 font-heading text-2xl font-bold text-foreground">
              Enter trip details to generate a compliant plan
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Route map, stops & rest schedule, and FMCSA daily log sheets will
              appear here after you plan a trip.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
