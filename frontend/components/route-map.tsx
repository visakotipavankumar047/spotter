"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { RouteGeometry, RouteStop } from "@/lib/types";

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

const STOP_COLORS: Record<string, string> = {
  pickup: "#e54d2d",
  dropoff: "#111111",
  fuel: "#e54d2d",
  rest: "#525252",
};

const STOP_LABELS: Record<string, string> = {
  pickup: "Pickup",
  dropoff: "Drop-off",
  fuel: "Fuel stop",
  rest: "Rest",
};

export function RouteMap({
  geometry,
  stops,
}: {
  geometry: RouteGeometry;
  stops: RouteStop[];
}) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const coords = geometry.coordinates;
    if (!coords.length) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OPENFREEMAP_STYLE,
      center: coords[0] as [number, number],
      zoom: 5,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("route", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry,
          properties: {},
        },
      });

      map.addLayer({
        id: "route-glow",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": "#e54d2d",
          "line-width": 8,
          "line-opacity": 0.2,
        },
      });

      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": "#e54d2d",
          "line-width": 3.5,
        },
      });

      stops.forEach((stop) => {
        const color = STOP_COLORS[stop.type] || "#e54d2d";
        const label = STOP_LABELS[stop.type] || stop.type;
        const place = stop.location || stop.label;

        const el = document.createElement("div");
        el.style.cssText = `
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: ${color};
          border: 2px solid #ffffff;
          box-shadow: 0 1px 4px rgba(0,0,0,0.25);
          cursor: pointer;
        `;

        const mile =
          typeof stop.mile_marker === "number"
            ? `<div style="color:#666;margin-top:4px;">mile ${stop.mile_marker.toLocaleString()}</div>`
            : "";

        const popup = new maplibregl.Popup({ offset: 18 }).setHTML(`
          <div style="font-family:system-ui,sans-serif;font-size:12px;min-width:140px;">
            <div style="font-weight:600;color:${color};margin-bottom:2px;">${label}</div>
            <div style="color:#111;">${place}</div>
            <div style="color:#666;margin-top:4px;">
              ${new Date(stop.arrival).toLocaleString()} · ${stop.duration_min} min
            </div>
            ${mile}
          </div>
        `);

        new maplibregl.Marker({ element: el })
          .setLngLat([stop.lng, stop.lat])
          .setPopup(popup)
          .addTo(map);
      });

      if (coords.length > 1) {
        const bounds = coords.reduce(
          (b, coord) => b.extend(coord as [number, number]),
          new maplibregl.LngLatBounds(
            coords[0] as [number, number],
            coords[0] as [number, number]
          )
        );
        map.fitBounds(bounds, { padding: 56 });
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [geometry, stops]);

  return (
    <div
      ref={mapContainer}
      className="h-[360px] w-full overflow-hidden rounded-md border border-border bg-muted md:h-[440px]"
    />
  );
}
