"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { GeocodeResult, TripCreateRequest } from "@/lib/types";
import { MapPin, Loader2 } from "lucide-react";

const ASSUMPTIONS = [
  "Property-carrying driver, 70 hrs / 8 days",
  "No adverse driving conditions",
  "Fuel stop every 1,000 miles",
  "1 hour allotted for pickup and drop-off",
  "Breaks and off-duty resets inserted per HOS",
];

const INPUT_CLASS =
  "h-10 rounded-lg border border-transparent bg-muted text-sm text-foreground shadow-none focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary";

function LocationAutocomplete({
  id,
  label,
  value,
  onChange,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}) {
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const [noResults, setNoResults] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const requestIdRef = useRef(0);

  const search = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setNoResults(false);
      setShowDropdown(false);
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = ++requestIdRef.current;

    setLoading(true);
    setNoResults(false);

    try {
      const res = await fetch("/api/geocode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: trimmed }),
        signal: controller.signal,
      });

      if (requestId !== requestIdRef.current) return;

      if (!res.ok) {
        setResults([]);
        setShowDropdown(false);
        return;
      }

      const data = (await res.json()) as GeocodeResult[];
      if (requestId !== requestIdRef.current) return;

      setResults(data);
      setNoResults(data.length === 0);
      setShowDropdown(true);
      setHighlighted(-1);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (requestId !== requestIdRef.current) return;
      setResults([]);
      setShowDropdown(false);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectResult = (result: GeocodeResult) => {
    onChange(result.label);
    setResults([]);
    setShowDropdown(false);
    setHighlighted(-1);
    setNoResults(false);
  };

  const handleInputChange = (val: string) => {
    onChange(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 250);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown) return;

    if (e.key === "ArrowDown") {
      if (results.length === 0) return;
      e.preventDefault();
      setHighlighted((p) => Math.min(p + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      if (results.length === 0) return;
      e.preventDefault();
      setHighlighted((p) => Math.max(p - 1, 0));
    } else if (e.key === "Enter" && highlighted >= 0 && results[highlighted]) {
      e.preventDefault();
      selectResult(results[highlighted]);
    } else if (e.key === "Escape") {
      setShowDropdown(false);
      setHighlighted(-1);
    }
  };

  return (
    <div className="space-y-1.5" ref={wrapperRef}>
      <Label htmlFor={id} className="text-sm font-normal text-muted-foreground">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          value={value}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => {
            if (results.length > 0 || noResults) setShowDropdown(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`${INPUT_CLASS} pr-9`}
          autoComplete="off"
          role="combobox"
          aria-expanded={showDropdown}
          aria-autocomplete="list"
          aria-controls={`${id}-suggestions`}
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
        {showDropdown && (
          <div
            id={`${id}-suggestions`}
            role="listbox"
            className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-border bg-white shadow-lg"
          >
            {results.length > 0 ? (
              results.map((r, i) => (
                <button
                  key={`${r.lat}-${r.lng}-${i}`}
                  type="button"
                  role="option"
                  aria-selected={i === highlighted}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => selectResult(r)}
                  className={`flex w-full items-start gap-2 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted ${
                    i === highlighted ? "bg-muted" : ""
                  }`}
                >
                  <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                  <span className="leading-snug text-foreground">{r.label}</span>
                </button>
              ))
            ) : (
              <div className="px-3 py-2.5 text-sm text-muted-foreground">
                {noResults ? "No places found" : "Type to search places…"}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function TripForm({
  initial,
}: {
  initial?: {
    current_location?: string;
    pickup_location?: string;
    dropoff_location?: string;
    current_cycle_used_hours?: number;
  };
}) {
  const router = useRouter();
  const [currentLocation, setCurrentLocation] = useState(
    initial?.current_location ?? ""
  );
  const [pickupLocation, setPickupLocation] = useState(
    initial?.pickup_location ?? ""
  );
  const [dropoffLocation, setDropoffLocation] = useState(
    initial?.dropoff_location ?? ""
  );
  const [cycleHours, setCycleHours] = useState(
    initial?.current_cycle_used_hours != null
      ? String(initial.current_cycle_used_hours)
      : ""
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: TripCreateRequest = {
      current_location: currentLocation,
      pickup_location: pickupLocation,
      dropoff_location: dropoffLocation,
      current_cycle_used_hours: parseFloat(cycleHours) || 0,
    };

    try {
      const res = await fetch("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Request failed (${res.status})`);
      }

      const data = await res.json();
      router.push(`/trip/${data.trip_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to plan trip");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <p className="section-label">Trip Details</p>
      <h2 className="mt-1 font-heading text-2xl font-bold tracking-tight text-foreground">
        Plan a compliant route
      </h2>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-1 flex-col gap-4">
        <LocationAutocomplete
          id="current_location"
          label="Current Location"
          value={currentLocation}
          onChange={setCurrentLocation}
          placeholder="e.g. Dallas, TX"
        />
        <LocationAutocomplete
          id="pickup_location"
          label="Pickup Location"
          value={pickupLocation}
          onChange={setPickupLocation}
          placeholder="e.g. Oklahoma City, OK"
        />
        <LocationAutocomplete
          id="dropoff_location"
          label="Drop-off Location"
          value={dropoffLocation}
          onChange={setDropoffLocation}
          placeholder="e.g. Chicago, IL"
        />

        <div className="space-y-1.5">
          <Label
            htmlFor="cycle_hours"
            className="text-sm font-normal text-muted-foreground"
          >
            Current Cycle Used (Hrs){" "}
            <span className="text-muted-foreground/80">— 70 hr / 8 day</span>
          </Label>
          <Input
            id="cycle_hours"
            type="number"
            step="0.5"
            min="0"
            max="70"
            value={cycleHours}
            onChange={(e) => setCycleHours(e.target.value)}
            placeholder="e.g. 20"
            className={INPUT_CLASS}
          />
        </div>

        {error && (
          <div className="rounded-md bg-primary/10 px-3 py-2 text-sm text-primary">
            {error}
          </div>
        )}

        <Button
          type="submit"
          disabled={
            submitting ||
            !currentLocation ||
            !pickupLocation ||
            !dropoffLocation
          }
          className="mt-2 h-11 w-full rounded-lg bg-primary text-base font-semibold text-primary-foreground hover:bg-primary/90"
        >
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Planning…
            </>
          ) : (
            "Plan Trip"
          )}
        </Button>

        <div className="mt-auto pt-8">
          <p className="section-label">Assumptions</p>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {ASSUMPTIONS.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </form>
    </div>
  );
}
