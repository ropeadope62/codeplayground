"""
iracing_api.py — iRacing Data API tools for Blacksun

Wraps iracingdataapi.client.irDataClient to expose driver stats,
recent races, lap times, session results, and season data as MCP tools.

Requires:
    pip install iracingdataapi
    .env: IR_USER, IR_PASSWORD
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import logging
import os
from functools import cached_property
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("workstation-agent.iracing-api")


def ms_to_laptime(ms: int) -> str:
    """Convert iRacing internal time (1/10000 sec) to MM:SS.mmm string."""
    total_secs = ms / 10000
    minutes = int(total_secs // 60)
    seconds = int(total_secs % 60)
    remaining_ms = int(ms % 1000)
    return f"{minutes}:{seconds:02d}.{remaining_ms:03d}"


class IRacingAPI:
    """Thin wrapper around irDataClient with lazy auth."""

    @cached_property
    def client(self):
        from iracingdataapi.client import irDataClient
        username = os.getenv("IR_USER")
        password = os.getenv("IR_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "IR_USER and IR_PASSWORD must be set in .env"
            )
        return irDataClient(username=username, password=password)

    def lookup_driver_id(self, display_name: str) -> Optional[int]:
        drivers = self.client.lookup_drivers(display_name)
        if drivers:
            return drivers[0]["cust_id"]
        return None


_ir = IRacingAPI()


def register_iracing_api(mcp: FastMCP):

    @mcp.tool()
    def iracing_driver_stats(display_name: str) -> str:
        """Get career stats for an iRacing driver.

        Args:
            display_name: iRacing display name (e.g. 'Your Name').
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})
            data = _ir.client.stats_member_career(cust_id)
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_recent_races(display_name: str) -> str:
        """Get recent race results for an iRacing driver.

        Args:
            display_name: iRacing display name.
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})
            data = _ir.client.stats_member_recent_races(cust_id)
            races = data.get("races", [])
            # Trim to key fields for readability
            summary = [
                {
                    "subsession_id": r.get("subsession_id"),
                    "series_name": r.get("series_name"),
                    "track": r.get("track", {}).get("track_name"),
                    "car_name": r.get("car_name"),
                    "start_position": r.get("start_position"),
                    "finish_position": r.get("finish_position"),
                    "incidents": r.get("incidents"),
                    "irating_change": r.get("newi_rating", 0) - r.get("oldi_rating", 0),
                    "safety_rating_change": round(
                        r.get("new_cpi", 0) - r.get("old_cpi", 0), 3
                    ),
                    "session_start_time": r.get("session_start_time"),
                }
                for r in races
            ]
            return json.dumps(summary, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_lap_times(display_name: str, subsession_id: str = "") -> str:
        """Get lap times for a driver in a specific race session, or their most recent race.

        Args:
            display_name: iRacing display name.
            subsession_id: Session ID to query. Leave empty for most recent race.
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})

            if subsession_id:
                sid = int(subsession_id)
            else:
                recent = _ir.client.stats_member_recent_races(cust_id)
                sid = recent["races"][0]["subsession_id"]

            lap_data = _ir.client.result_lap_data(cust_id=cust_id, subsession_id=sid)
            lap_times = [lap["lap_time"] for lap in lap_data]
            # Filter out invalid laps (pit, off-track, first lap)
            valid = [lt for lt in lap_times if lt > 0][1:]
            formatted = {
                i + 1: {"raw": lt, "formatted": ms_to_laptime(lt)}
                for i, lt in enumerate(valid)
            }
            avg = sum(valid) / len(valid) if valid else 0
            best = min(valid) if valid else 0
            return json.dumps(
                {
                    "subsession_id": sid,
                    "driver": display_name,
                    "laps": len(valid),
                    "best_lap": ms_to_laptime(best),
                    "avg_lap": ms_to_laptime(int(avg)),
                    "lap_times": formatted,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_session_result(subsession_id: str) -> str:
        """Get full results for an iRacing session by subsession ID.

        Args:
            subsession_id: iRacing subsession ID.
        """
        try:
            data = _ir.client.result(int(subsession_id))
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_member_bests(display_name: str) -> str:
        """Get personal best lap times by track for an iRacing driver.

        Args:
            display_name: iRacing display name.
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})
            data = _ir.client.stats_member_bests(cust_id)
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_irating_history(display_name: str) -> str:
        """Get iRating history chart data for a driver.

        Args:
            display_name: iRacing display name.
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})
            data = _ir.client.member_chart_data(cust_id)
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_incidents(display_name: str) -> str:
        """Get total incident count across recent races for a driver.

        Args:
            display_name: iRacing display name.
        """
        try:
            cust_id = _ir.lookup_driver_id(display_name)
            if not cust_id:
                return json.dumps({"error": f"Driver '{display_name}' not found"})
            recent = _ir.client.stats_member_recent_races(cust_id)
            total = sum(r.get("incidents", 0) for r in recent.get("races", []))
            per_race = [
                {
                    "series": r.get("series_name"),
                    "track": r.get("track", {}).get("track_name"),
                    "incidents": r.get("incidents"),
                    "finish": r.get("finish_position"),
                }
                for r in recent.get("races", [])
            ]
            return json.dumps(
                {"driver": display_name, "total_incidents": total, "by_race": per_race},
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_season_list(season_year: int = 0, season_quarter: int = 0) -> str:
        """Get the list of series for a given iRacing season.

        Args:
            season_year: Year (e.g. 2026). Defaults to current year.
            season_quarter: Quarter 1-4. Defaults to current quarter.
        """
        try:
            if not season_year or not season_quarter:
                import datetime
                now = datetime.datetime.now()
                season_year = season_year or now.year
                month = now.month
                season_quarter = season_quarter or (
                    1 if month < 4 else 2 if month < 7 else 3 if month < 10 else 4
                )
            data = _ir.client.season_list(season_year, season_quarter)
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def iracing_lookup_driver(display_name: str) -> str:
        """Look up an iRacing driver by name and return their customer ID and info.

        Args:
            display_name: Full or partial iRacing display name.
        """
        try:
            drivers = _ir.client.lookup_drivers(display_name)
            if not drivers:
                return json.dumps({"error": f"No drivers found for '{display_name}'"})
            return json.dumps(drivers, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
