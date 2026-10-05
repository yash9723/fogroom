"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { Skeleton } from "@/components/ui/feedback";
import type { Location } from "@/lib/types";
import type { MapMarker } from "./ops-map-leaflet";

const OpsMapLeaflet = dynamic(() => import("./ops-map-leaflet"), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-48 w-full" />,
});

export type MapReport = { location_key: string | null; title: string; at: number | null };

/** Fictional operational map. Markers only reflect reports the viewer actually holds. */
export function OpsMap({ locations, reports, height = 300 }: { locations: Location[]; reports: MapReport[]; height?: number }) {
  const markers = useMemo<MapMarker[]>(() => {
    const latestAt = Math.max(-1, ...reports.map((r) => r.at ?? -1));
    return locations.map((loc) => {
      const mine = reports.filter((r) => r.location_key === loc.key).sort((a, b) => (b.at ?? 0) - (a.at ?? 0));
      return {
        ...loc,
        reports: mine.length,
        latest: mine[0]?.title,
        highlight: mine.length > 0 && mine[0].at === latestAt,
      };
    });
  }, [locations, reports]);

  return (
    <div style={{ height }} aria-label="Fictional operational map" role="region">
      <OpsMapLeaflet markers={markers} height={height} />
    </div>
  );
}
