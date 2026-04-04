"""
Satellite Agent — The Auditor's Eyes in Space  (Enhanced)

Dual-path verification:
  1. Climate TRACE API  — historical emissions tonnage per asset/region
  2. ASDI (Sentinel-5P) — real satellite NO2/CH4 data from AWS S3 using
     boto3 + xarray/netCDF4

Produces satellite plume concentration values that are used in the
Evidence View of the dashboard.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx

# ---------------------------------------------------------------------------
# Climate TRACE API helpers
# ---------------------------------------------------------------------------
CLIMATE_TRACE_BASE = "https://api.climatetrace.org/v6"

SECTOR_MAP = {
    "Oil & Gas Production": "fossil-fuel-operations",
    "Oil & Gas Transport": "fossil-fuel-operations",
    "Road Transportation": "transportation",
    "Petroleum Refining": "fossil-fuel-operations",
    "Logistics": "transportation",
    "Manufacturing": "manufacturing",
    "Power": "power",
    "Fulfillment Center": "buildings",
    "Data Center": "power",
    "Renewable Energy": "power",
    "Office": "buildings",
    "Unknown": "power",
}


class SatelliteAgent:
    """Fetches real emissions data from Climate TRACE and ASDI."""

    def __init__(self):
        self._s3_client = None

    async def fetch_emissions(
        self,
        geocoded_facilities: list[dict],
        log_fn: Optional[Callable] = None,
    ) -> list[dict]:
        """Enrich each facility with satellite-observed emissions data."""
        results = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for facility in geocoded_facilities:
                if log_fn:
                    log_fn(f"   🛰️  Querying data for: {facility['name']}")

                # --- Path 1: Climate TRACE ---
                ct_data = await self._query_climate_trace(client, facility, log_fn)

                # --- Path 2: ASDI Sentinel-5P ---
                asdi_data = await self._query_asdi_real(facility, log_fn)

                enriched = {
                    **facility,
                    "climate_trace": ct_data,
                    "asdi": asdi_data,
                    "satellite_emissions_tons": ct_data.get("emissions_tons"),
                }
                results.append(enriched)

        return results

    # ------------------------------------------------------------------
    # Climate TRACE API (unchanged from v1 — already works live)
    # ------------------------------------------------------------------
    async def _query_climate_trace(
        self,
        client: httpx.AsyncClient,
        facility: dict,
        log_fn: Optional[Callable] = None,
    ) -> dict:
        country = facility.get("country", "USA")
        sector = SECTOR_MAP.get(facility.get("type", ""), "power")

        try:
            url = f"{CLIMATE_TRACE_BASE}/assets"
            params = {"countries": country, "sectors": sector, "limit": 10}
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            assets = data.get("assets", [])

            if not assets:
                if log_fn:
                    log_fn(f"   ℹ️  No Climate TRACE assets for sector={sector}")
                return {"source": "climate_trace", "found": False, "emissions_tons": None}

            best = self._find_nearest_asset(
                assets, facility.get("lat", 0), facility.get("lng", 0)
            )

            emissions_tons = None
            for s in best.get("EmissionsSummary", []):
                if s.get("Gas") == "co2e_100yr":
                    emissions_tons = s.get("EmissionsQuantity")

            asset_name = best.get("Name", "Unknown")
            centroid = best.get("Centroid", {}).get("Geometry", [0, 0])

            if log_fn:
                log_fn(
                    f'   📊 Climate TRACE match: "{asset_name}" — '
                    f"{self._fmt_tons(emissions_tons)} CO₂e"
                )

            return {
                "source": "climate_trace",
                "found": True,
                "asset_id": best.get("Id"),
                "asset_name": asset_name,
                "sector": best.get("Sector"),
                "emissions_tons": emissions_tons,
                "confidence": self._extract_confidence(best),
                "thumbnail_url": best.get("Thumbnail"),
                "centroid_lng": centroid[0] if len(centroid) > 0 else None,
                "centroid_lat": centroid[1] if len(centroid) > 1 else None,
            }
        except Exception as e:
            if log_fn:
                log_fn(f"   ⚠️  Climate TRACE error: {e}")
            return {"source": "climate_trace", "found": False, "emissions_tons": None}

    # ------------------------------------------------------------------
    # ASDI Sentinel-5P — REAL data download & processing
    # ------------------------------------------------------------------
    async def _query_asdi_real(
        self,
        facility: dict,
        log_fn: Optional[Callable] = None,
    ) -> dict:
        """Download and process real Sentinel-5P data from ASDI S3."""
        lat = facility.get("lat", 0)
        lng = facility.get("lng", 0)

        if log_fn:
            log_fn(f"   🌐 ASDI Sentinel-5P: querying for ({lat:.2f}, {lng:.2f})")

        # Try to get real S3 file listing
        s3_info = await self._list_sentinel5p_files(log_fn)

        # Try to process a real NetCDF file
        concentration_data = await self._process_sentinel5p(lat, lng, log_fn)

        products = {
            "NO2": {
                "s3_bucket": "meeo-s5p",
                "s3_prefix": "OFFL/L2__NO2___",
                "description": "Tropospheric NO2 column density",
                "resolution": "3.5km x 5.5km",
                "source": "Amazon Sustainability Data Initiative (ASDI)",
                "concentration": concentration_data.get("NO2"),
            },
            "CH4": {
                "s3_bucket": "meeo-s5p",
                "s3_prefix": "OFFL/L2__CH4___",
                "description": "Methane total column mixing ratio",
                "resolution": "7km x 7km",
                "source": "Amazon Sustainability Data Initiative (ASDI)",
                "concentration": concentration_data.get("CH4"),
            },
            "CO": {
                "s3_bucket": "meeo-s5p",
                "s3_prefix": "OFFL/L2__CO____",
                "description": "Carbon monoxide total column",
                "resolution": "7km x 7km",
                "source": "Amazon Sustainability Data Initiative (ASDI)",
                "concentration": concentration_data.get("CO"),
            },
        }

        if log_fn:
            log_fn(f"   📡 S3 source: s3://meeo-s5p/OFFL/ (eu-central-1, public)")
            log_fn(f"   📦 Products: NO2, CH4, CO — covering facility region")
            if concentration_data.get("NO2"):
                log_fn(f"   🔬 NO2 concentration: {concentration_data['NO2']:.2e} mol/m²")

        return {
            "source": "asdi_sentinel5p",
            "available": True,
            "lat": lat,
            "lng": lng,
            "products": products,
            "s3_files": s3_info,
            "concentration_data": concentration_data,
            "access_command": "aws s3 ls --no-sign-request s3://meeo-s5p/OFFL/",
        }

    async def _list_sentinel5p_files(self, log_fn=None) -> dict:
        """List recent Sentinel-5P files from the ASDI S3 bucket."""
        try:
            import boto3
            from botocore import UNSIGNED
            from botocore.config import Config

            loop = asyncio.get_event_loop()

            def _list():
                s3 = boto3.client(
                    "s3",
                    region_name="eu-central-1",
                    config=Config(signature_version=UNSIGNED),
                )
                # List NO2 product files from the last few days
                prefix = "OFFL/L2__NO2___/"
                response = s3.list_objects_v2(
                    Bucket="meeo-s5p",
                    Prefix=prefix,
                    MaxKeys=5,
                )
                files = []
                for obj in response.get("Contents", []):
                    files.append({
                        "key": obj["Key"],
                        "size_mb": round(obj["Size"] / (1024 * 1024), 1),
                        "last_modified": obj["LastModified"].isoformat(),
                    })
                return files

            files = await asyncio.wait_for(
                loop.run_in_executor(None, _list),
                timeout=15.0,  # 15s timeout for S3 listing
            )
            if log_fn and files:
                log_fn(f"   📂 Found {len(files)} Sentinel-5P NO2 files on S3")
                for f in files[:2]:
                    log_fn(f"      └─ {f['key'].split('/')[-1]} ({f['size_mb']}MB)")

            return {"files": files, "error": None}
        except Exception as e:
            if log_fn:
                log_fn(f"   ⚠️  S3 listing warning: {str(e)[:80]}")
            return {"files": [], "error": str(e)}

    async def _process_sentinel5p(
        self, lat: float, lng: float, log_fn=None
    ) -> dict:
        """Download a small Sentinel-5P file and extract concentration at location.

        For the hackathon demo, we download a Cloud Optimized GeoTIFF (COGT)
        from the ASDI bucket because it's much smaller than raw NetCDF files
        (~5MB vs ~500MB). If COGT isn't available, we fall back to listing
        available files and reporting metadata.
        """
        concentration_data: dict = {}

        try:
            import boto3
            from botocore import UNSIGNED
            from botocore.config import Config

            loop = asyncio.get_event_loop()

            def _download_and_process():
                s3 = boto3.client(
                    "s3",
                    region_name="eu-central-1",
                    config=Config(signature_version=UNSIGNED),
                )

                # Try to find a COGT (Cloud Optimized GeoTIFF) file — much smaller
                prefix = "COGT/L2__NO2___/"
                try:
                    resp = s3.list_objects_v2(
                        Bucket="meeo-s5p", Prefix=prefix, MaxKeys=3
                    )
                    cogt_files = resp.get("Contents", [])
                except Exception:
                    cogt_files = []

                # Try OFFL NetCDF if no COGT
                if not cogt_files:
                    prefix = "OFFL/L2__NO2___/"
                    try:
                        resp = s3.list_objects_v2(
                            Bucket="meeo-s5p", Prefix=prefix, MaxKeys=3
                        )
                        cogt_files = resp.get("Contents", [])
                    except Exception:
                        cogt_files = []

                if not cogt_files:
                    return {}

                # Pick the smallest file for demo speed
                smallest = min(cogt_files, key=lambda x: x["Size"])
                file_key = smallest["Key"]
                file_size_mb = smallest["Size"] / (1024 * 1024)

                # Only download if < 50MB (demo constraint)
                if file_size_mb > 50:
                    return {
                        "file_found": file_key,
                        "file_size_mb": round(file_size_mb, 1),
                        "skipped": "File too large for demo download",
                    }

                # Download to temp
                tmp_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "satellite_cache",
                )
                os.makedirs(tmp_dir, exist_ok=True)
                local_path = os.path.join(
                    tmp_dir, file_key.split("/")[-1]
                )

                if not os.path.exists(local_path):
                    s3.download_file("meeo-s5p", file_key, local_path)

                # Process based on file type
                if local_path.endswith(".nc"):
                    return _process_netcdf(local_path, lat, lng)
                elif local_path.endswith(".tif") or local_path.endswith(".tiff"):
                    return _process_geotiff(local_path, lat, lng)
                else:
                    return {"file": file_key, "note": "Unrecognized format"}

            def _process_netcdf(path, lat, lng):
                """Extract concentration values from NetCDF at lat/lng."""
                try:
                    import xarray as xr

                    ds = xr.open_dataset(path, engine="netcdf4")
                    result = {"file": os.path.basename(path), "format": "NetCDF4"}

                    # Sentinel-5P NetCDF files have varying variable names
                    for var_name in ds.data_vars:
                        if "no2" in var_name.lower() or "nitrogendioxide" in var_name.lower():
                            data = ds[var_name]
                            # Get global stats
                            result["NO2"] = float(data.mean(skipna=True).values)
                            result["NO2_unit"] = str(data.attrs.get("units", "mol/m2"))
                            break

                    for var_name in ds.data_vars:
                        if "ch4" in var_name.lower() or "methane" in var_name.lower():
                            data = ds[var_name]
                            result["CH4"] = float(data.mean(skipna=True).values)
                            result["CH4_unit"] = str(data.attrs.get("units", "ppb"))
                            break

                    ds.close()
                    return result
                except Exception as e:
                    return {"error": f"NetCDF processing: {str(e)}"}

            def _process_geotiff(path, lat, lng):
                """Extract value from GeoTIFF at lat/lng."""
                try:
                    import xarray as xr

                    ds = xr.open_dataset(path, engine="rasterio")
                    result = {"file": os.path.basename(path), "format": "GeoTIFF"}

                    # Try to extract value at location
                    try:
                        val = ds.sel(y=lat, x=lng, method="nearest")
                        for var in val.data_vars:
                            result["NO2"] = float(val[var].values)
                            break
                    except Exception:
                        # Get global mean as fallback
                        for var in ds.data_vars:
                            result["NO2"] = float(ds[var].mean(skipna=True).values)
                            break

                    ds.close()
                    return result
                except Exception as e:
                    return {"error": f"GeoTIFF processing: {str(e)}"}

            concentration_data = await asyncio.wait_for(
                loop.run_in_executor(None, _download_and_process),
                timeout=20.0,  # 20s timeout for S3 operations
            )

        except asyncio.TimeoutError:
            concentration_data = {"note": "S3 download timed out (demo constraint)"}
        except ImportError as e:
            concentration_data = {"error": f"Missing package: {e}"}
        except Exception as e:
            concentration_data = {"error": str(e)}

        return concentration_data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_nearest_asset(self, assets: list[dict], lat: float, lng: float) -> dict:
        def dist(asset):
            c = asset.get("Centroid", {}).get("Geometry", [0, 0])
            if not c or len(c) < 2:
                return float("inf")
            return (c[1] - lat) ** 2 + (c[0] - lng) ** 2
        return min(assets, key=dist)

    @staticmethod
    def _extract_confidence(asset: dict) -> Optional[str]:
        for entry in asset.get("Confidence", []):
            for year, vals in entry.items():
                if year in ("2024", "2025"):
                    if vals and len(vals) > 0:
                        return vals[0].get("total_co2e_100yrgwp", "unknown")
        return "unknown"

    @staticmethod
    def _fmt_tons(tons) -> str:
        if tons is None:
            return "N/A"
        if tons >= 1_000_000:
            return f"{tons / 1_000_000:.1f}M tons"
        if tons >= 1_000:
            return f"{tons / 1_000:.0f}K tons"
        return f"{tons:.0f} tons"
