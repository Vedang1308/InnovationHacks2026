from geopy.geocoders import Nominatim
import json
import os
from typing import Dict, Optional

class GeospatialAgent:
    def __init__(self, cache_file: str = "data/geo_cache.json"):
        self.geolocator = Nominatim(user_agent="tracetrust_auditor")
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=4)

    def geocode(self, location_str: str) -> Optional[Dict[str, float]]:
        """
        Geocode a location string to Lat/Long.
        """
        if location_str in self.cache:
            return self.cache[location_str]

        try:
            location = self.geolocator.geocode(location_str)
            if location:
                result = {"lat": location.latitude, "lon": location.longitude}
                self.cache[location_str] = result
                self._save_cache()
                return result
            return None
        except Exception as e:
            print(f"Error geocoding {location_str}: {e}")
            return None

if __name__ == "__main__":
    # Test stub
    geo = GeospatialAgent()
    print(geo.geocode("Goodyear, Arizona"))
