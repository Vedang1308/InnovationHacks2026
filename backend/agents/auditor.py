"""
Auditor Agent — The Scorer
Compares reported emissions against satellite-observed emissions and
calculates the Veracity Score.

    V = 100 − (|E_satellite − E_reported| / E_satellite) × 100

Flags discrepancies over 20 % as high-risk.
"""

from typing import Callable, Optional


class AuditorAgent:
    """Scores each facility's emissions claim against satellite evidence."""

    DISCREPANCY_THRESHOLD = 20.0  # percent

    def score(
        self,
        facilities: list[dict],
        log_fn: Optional[Callable] = None,
    ) -> dict:
        """Generate the full audit report with per-facility veracity scores."""

        scored_facilities = []
        total_reported = 0.0
        total_satellite = 0.0
        flags = 0

        for f in facilities:
            reported = f.get("reported_emissions_tons") or 0
            satellite = f.get("satellite_emissions_tons")

            if reported and satellite and satellite > 0:
                discrepancy_pct = abs(satellite - reported) / satellite * 100
                veracity = max(0.0, 100.0 - discrepancy_pct)
                direction = "under-reported" if reported < satellite else "over-reported"
            else:
                discrepancy_pct = None
                veracity = None
                direction = "insufficient data"

            flagged = (
                discrepancy_pct is not None
                and discrepancy_pct > self.DISCREPANCY_THRESHOLD
            )
            if flagged:
                flags += 1

            status = self._status_label(veracity)

            entry = {
                "name": f.get("name"),
                "city": f.get("city"),
                "state": f.get("state"),
                "lat": f.get("lat"),
                "lng": f.get("lng"),
                "type": f.get("type"),
                "reported_emissions_tons": reported,
                "satellite_emissions_tons": satellite,
                "veracity_score": round(veracity, 1) if veracity is not None else None,
                "discrepancy_pct": (
                    round(discrepancy_pct, 1)
                    if discrepancy_pct is not None
                    else None
                ),
                "direction": direction,
                "flagged": flagged,
                "status": status,
                "climate_trace": f.get("climate_trace", {}),
                "asdi": f.get("asdi", {}),
            }
            scored_facilities.append(entry)

            if reported:
                total_reported += reported
            if satellite:
                total_satellite += satellite

            if log_fn:
                if veracity is not None:
                    emoji = "🟢" if not flagged else "🔴"
                    log_fn(
                        f"   {emoji} {f['name']}: Veracity={veracity:.1f}% "
                        f"| Reported={self._fmt(reported)} | Satellite={self._fmt(satellite)} "
                        f"| {direction}"
                    )
                else:
                    log_fn(
                        f"   ⚪ {f['name']}: Insufficient satellite data for scoring"
                    )

        # Aggregate
        if total_satellite > 0:
            overall_discrepancy = (
                abs(total_satellite - total_reported) / total_satellite * 100
            )
            overall_veracity = max(0.0, 100.0 - overall_discrepancy)
        else:
            overall_discrepancy = None
            overall_veracity = None

        report = {
            "company_name": facilities[0].get("company_name", "Unknown") if facilities else "Unknown",
            "total_facilities_audited": len(scored_facilities),
            "flagged_facilities": flags,
            "overall_veracity_score": (
                round(overall_veracity, 1) if overall_veracity is not None else None
            ),
            "overall_discrepancy_pct": (
                round(overall_discrepancy, 1)
                if overall_discrepancy is not None
                else None
            ),
            "total_reported_tons": total_reported,
            "total_satellite_tons": total_satellite,
            "facilities": scored_facilities,
        }

        if log_fn:
            log_fn(f"   📋 Overall Veracity Score: {report['overall_veracity_score']}%")
            log_fn(
                f"   🚩 {flags}/{len(scored_facilities)} facilities flagged "
                f"(>{self.DISCREPANCY_THRESHOLD}% discrepancy)"
            )

        return report

    @staticmethod
    def _status_label(veracity) -> str:
        if veracity is None:
            return "unknown"
        if veracity >= 80:
            return "verified"
        if veracity >= 50:
            return "caution"
        return "discrepancy"

    @staticmethod
    def _fmt(tons) -> str:
        if tons is None or tons == 0:
            return "N/A"
        if tons >= 1_000_000:
            return f"{tons / 1_000_000:.1f}M"
        if tons >= 1_000:
            return f"{tons / 1_000:.0f}K"
        return f"{tons:.0f}"
