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
            queries = self._build_queries(facility)
            coords = (0.0, 0.0)
            
            for q in queries:
                if log_fn:
                    log_fn(f"   🔎 Geocoding: {q}")
                
                coords = await self._geocode(q)
                if coords[0] != 0.0:
                    break
                # small delay between fallback attempts
                await asyncio.sleep(1.1)

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
    def _build_queries(facility: dict) -> list[str]:
        """Build exactly targeted queries with fallbacks."""
        queries = []
        
        base_parts = []
        if facility.get("city"):
            base_parts.append(facility["city"])
        if facility.get("state"):
            base_parts.append(facility["state"])
        if facility.get("country"):
            base_parts.append(facility["country"])
            
        base_str = ", ".join(base_parts)

        # 1. Best attempt: Street Address + Region
        if facility.get("street_address") and base_str:
            queries.append(f"{facility['street_address']}, {base_str}")
        
        # 2. Point of Interest Attempt: Name + Region
        if facility.get("name") and base_str:
            # Clean name a bit (Nominatim struggles with 'Fulfillment Center' sometimes, but we try)
            queries.append(f"{facility['name']}, {base_str}")
            
        # 3. Safe fallback: Just the city center
        if base_str:
            queries.append(base_str)
            
        # 4. Ultimate fallback
        if not queries:
            queries.append(facility.get("name", ""))

        return queries
