"""
Geospatial Agent — The Mapper
Converts facility names/cities to GPS coordinates using geopy + OpenStreetMap.
"""

import asyncio
from typing import Callable, Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


class GeospatialAgent:
    """Geocodes facility addresses to lat/long coordinates."""

    def __init__(self):
        self.geocoder = Nominatim(
            user_agent="tracetrust_auditor_v1",
            timeout=10,
        )
        self._cache: dict[str, tuple[float, float]] = {}

    async def geocode_facilities(
        self,
        facilities: list[dict],
        log_fn: Optional[Callable] = None,
    ) -> list[dict]:
        """Add lat/lng to each facility dict. Returns a new enriched list."""

        results = []
        for facility in facilities:
            query = self._build_query(facility)
            if log_fn:
                log_fn(f"   🔎 Geocoding: {query}")

            coords = await self._geocode(query)
            enriched = {**facility, "lat": coords[0], "lng": coords[1]}

            if coords[0] != 0.0:
                if log_fn:
                    log_fn(
                        f"   ✅ Located: {facility['name']} → "
                        f"({coords[0]:.4f}, {coords[1]:.4f})"
                    )
            else:
                if log_fn:
                    log_fn(f"   ⚠️  Could not geocode: {facility['name']} — using fallback coordinates")

            results.append(enriched)
            # Small delay to respect Nominatim rate limits
            await asyncio.sleep(1.1)

        return results

    async def _geocode(self, query: str) -> tuple[float, float]:
        if query in self._cache:
            return self._cache[query]

        try:
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None, lambda: self.geocoder.geocode(query)
            )
            if location:
                coords = (location.latitude, location.longitude)
                self._cache[query] = coords
                return coords
        except GeocoderTimedOut:
            pass
        except Exception:
            pass

        # Fallback: return approximate US center
        return (39.8283, -98.5795)

    @staticmethod
    def _build_query(facility: dict) -> str:
        parts = []
        if facility.get("city"):
            parts.append(facility["city"])
        if facility.get("state"):
            parts.append(facility["state"])
        if facility.get("country"):
            parts.append(facility["country"])
        return ", ".join(parts) if parts else facility.get("name", "")
