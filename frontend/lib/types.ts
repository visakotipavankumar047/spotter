export type DutyStatus =
  | "OFF_DUTY"
  | "SLEEPER_BERTH"
  | "DRIVING"
  | "ON_DUTY_NOT_DRIVING";

export interface GeocodeResult {
  label: string;
  lat: number;
  lng: number;
}

export interface RouteStop {
  type: "pickup" | "dropoff" | "fuel" | "rest";
  label: string;
  location?: string;
  lat: number;
  lng: number;
  arrival: string;
  duration_min: number;
  mile_marker?: number;
}

export interface RouteGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface TripSummary {
  total_distance_miles: number;
  total_drive_hours: number;
  total_duty_hours: number;
  num_days: number;
  cycle_hours_remaining_at_finish: number;
  restarts_required: number;
}

export interface DailyLogSegment {
  status: DutyStatus;
  start: string;
  end: string;
}

export interface DailyLogTotals {
  off_duty: number;
  sleeper_berth: number;
  driving: number;
  on_duty_not_driving: number;
}

export interface DailyRemark {
  time: string;
  location: string;
  note: string;
}

export interface DailyLog {
  date: string;
  total_miles_today: number;
  segments: DailyLogSegment[];
  totals: DailyLogTotals;
  remarks: DailyRemark[];
}

export interface TripResponse {
  trip_id: string;
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_hours: number;
  trip_start_datetime?: string;
  summary: TripSummary;
  route: {
    geometry: RouteGeometry;
    stops: RouteStop[];
  };
  daily_logs: DailyLog[];
}

export interface TripCreateRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_hours: number;
  trip_start_datetime?: string;
}
