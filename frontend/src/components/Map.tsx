"use client";

import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";

// Fix for default Leaflet marker icons in Next.js
// @ts-ignore
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

function RecenterMap({ coords }: { coords: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (coords && coords[0] !== 20) {
      map.setView(coords, 10, { animate: true });
    }
  }, [coords, map]);
  return null;
}

interface LiveMapProps {
  center: [number, number];
  facilities: any[];
}

// Dynamically import Leaflet parts with any casting for Next.js compat
const MapContainerAny = MapContainer as any;

export default function LiveMap({ center, facilities }: LiveMapProps) {
  return (
    <MapContainerAny 
      center={center} 
      zoom={3} 
      style={{ height: "100%", width: "100%", filter: "invert(100%) hue-rotate(180deg) brightness(0.6) contrast(1.2)" }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {facilities.map((f, i) => (
        <Marker key={i} position={[f.lat, f.lng]}>
          <Popup>
            <div className="text-xs font-bold text-slate-900">{f.name}</div>
          </Popup>
        </Marker>
      ))}
      <RecenterMap coords={center} />
    </MapContainerAny>
  );
}
