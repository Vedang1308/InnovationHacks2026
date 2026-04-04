import xarray as xr
import numpy as np
import os

def ensure_sample_satellite_data(file_path: str):
    """
    Generates a small, valid NetCDF file for Sentinel-5P demonstration if it doesn't exist.
    This allows the Xarray processing code to be verified with real toolchains.
    """
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return

    print(f"Generating valid Sentinel-5P sample data at {file_path}...")
    
    # Create coordinate grids
    lats = np.linspace(-90, 90, 180)
    lons = np.linspace(-180, 180, 360)
    
    # Create a dummy NO2 concentration field (mol/m^2)
    # Add some "hotspots" to make it interesting
    no2_data = np.random.rand(180, 360) * 1e-5
    # Add a plume at a known coordinate (e.g., San Francisco vicinity)
    sf_lat, sf_lon = 37.7749, -122.4194
    lat_idx = np.abs(lats - sf_lat).argmin()
    lon_idx = np.abs(lons - sf_lon).argmin()
    no2_data[lat_idx-5:lat_idx+5, lon_idx-5:lon_idx+5] += 5e-4
    
    ds = xr.Dataset(
        {
            "nitrogendioxide_tropospheric_column": (["lat", "lon"], no2_data),
        },
        coords={
            "lat": lats,
            "lon": lons,
        },
        attrs={
            "description": "Mock Sentinel-5P NO2 Concentration for TraceTrust Demo",
            "units": "mol/m^2"
        }
    )
    
    ds.to_netcdf(file_path)
    print("Sample satellite data generated successfully.")

if __name__ == "__main__":
    ensure_sample_satellite_data("data/satellite_cache/sample_s5p.nc")
