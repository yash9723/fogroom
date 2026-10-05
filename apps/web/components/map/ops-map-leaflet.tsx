"use client";

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { CircleMarker, ImageOverlay, MapContainer, Tooltip } from "react-leaflet";
import type { Location } from "@/lib/types";

export type MapMarker = Location & { reports: number; latest?: string; highlight?: boolean };

const W = 1000;
const H = 640;
const BOUNDS: L.LatLngBoundsExpression = [
  [0, 0],
  [H, W],
];

const KIND_COLOR: Record<string, string> = {
  medical: "#e5574e",
  bridge: "#e3a63c",
  port: "#4fc1d6",
  airfield: "#a48cf0",
  relay: "#7aa5f5",
  hq: "#3fb87f",
};

/** Leaflet with CRS.Simple over a bundled fictional SVG map - no external tiles. */
export default function OpsMapLeaflet({ markers, height }: { markers: MapMarker[]; height: number }) {
  return (
    <MapContainer
      crs={L.CRS.Simple}
      bounds={BOUNDS}
      maxBounds={BOUNDS}
      minZoom={-1}
      maxZoom={2}
      zoomSnap={0.25}
      style={{ height, width: "100%", borderRadius: 8 }}
      attributionControl={false}
      scrollWheelZoom={false}
    >
      <ImageOverlay url="/maps/orion-delta.svg" bounds={BOUNDS} />
      {markers.map((m) => (
        <CircleMarker
          key={m.key}
          center={[H - m.y, m.x]}
          radius={m.reports > 0 ? 9 : 6}
          pathOptions={{
            color: KIND_COLOR[m.kind] ?? "#8b98a9",
            fillColor: KIND_COLOR[m.kind] ?? "#8b98a9",
            fillOpacity: m.reports > 0 ? 0.55 : 0.15,
            weight: m.highlight ? 3 : 1.5,
          }}
        >
          <Tooltip className="fr-tooltip" direction="top" permanent={m.highlight}>
            <strong>{m.name}</strong>
            {m.reports > 0 ? ` · ${m.reports} report${m.reports > 1 ? "s" : ""}` : " · no reports"}
            {m.latest ? <div style={{ maxWidth: 220, whiteSpace: "normal" }}>{m.latest}</div> : null}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
