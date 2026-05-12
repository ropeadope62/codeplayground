"""
Weather tools — daily and weekly forecasts via Open-Meteo API.

Free, no API key required. Hardcoded to Montreal by default
but can be overridden per-call.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# Montreal coordinates
DEFAULT_LAT = 45.5019
DEFAULT_LON = -73.5674
DEFAULT_CITY = "Montreal"
DEFAULT_TIMEZONE = "America/Montreal"

# WMO weather code descriptions
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "WorkstationAgent/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _weather_description(code: int) -> str:
    """Convert WMO weather code to human-readable description."""
    return WMO_CODES.get(code, f"Unknown ({code})")


class WeatherTools:
    """Weather forecasts via Open-Meteo API."""

    def __init__(self, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON,
                 city: str = DEFAULT_CITY, timezone: str = DEFAULT_TIMEZONE):
        self.lat = lat
        self.lon = lon
        self.city = city
        self.timezone = timezone

    def current_weather(self) -> dict:
        """Get current weather conditions."""
        params = urllib.parse.urlencode({
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation",
            "timezone": self.timezone,
            "wind_speed_unit": "kmh",
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        data = _fetch_json(url)
        current = data.get("current", {})

        return {
            "city": self.city,
            "time": current.get("time", ""),
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "conditions": _weather_description(current.get("weather_code", -1)),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_gusts_kmh": current.get("wind_gusts_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "precipitation_mm": current.get("precipitation"),
        }

    def daily_forecast(self, days: int = 1) -> dict:
        """Get daily forecast.

        Args:
            days: Number of days (1 = today only, 7 = full week, max 16).
        """
        days = min(max(days, 1), 16)
        params = urllib.parse.urlencode({
            "latitude": self.lat,
            "longitude": self.lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset,uv_index_max",
            "timezone": self.timezone,
            "forecast_days": days,
            "wind_speed_unit": "kmh",
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        data = _fetch_json(url)
        daily = data.get("daily", {})

        forecasts = []
        times = daily.get("time", [])
        for i in range(len(times)):
            forecasts.append({
                "date": times[i],
                "conditions": _weather_description(daily.get("weather_code", [0])[i]),
                "temp_high_c": daily.get("temperature_2m_max", [None])[i],
                "temp_low_c": daily.get("temperature_2m_min", [None])[i],
                "feels_high_c": daily.get("apparent_temperature_max", [None])[i],
                "feels_low_c": daily.get("apparent_temperature_min", [None])[i],
                "precipitation_mm": daily.get("precipitation_sum", [None])[i],
                "precipitation_chance_pct": daily.get("precipitation_probability_max", [None])[i],
                "wind_max_kmh": daily.get("wind_speed_10m_max", [None])[i],
                "wind_gusts_kmh": daily.get("wind_gusts_10m_max", [None])[i],
                "uv_index": daily.get("uv_index_max", [None])[i],
                "sunrise": daily.get("sunrise", [None])[i],
                "sunset": daily.get("sunset", [None])[i],
            })

        return {"city": self.city, "days": forecasts}

    def weekly_report(self) -> str:
        """Generate a formatted markdown weather report for the week."""
        current = self.current_weather()
        forecast = self.daily_forecast(days=7)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Weather Report — {self.city}",
            f"*Generated: {now}*\n",
            "## Right Now\n",
            f"- **{current['temperature_c']}°C** (feels like {current['feels_like_c']}°C)",
            f"- {current['conditions']}",
            f"- Humidity: {current['humidity_pct']}%",
            f"- Wind: {current['wind_speed_kmh']} km/h (gusts {current['wind_gusts_kmh']} km/h)",
        ]

        if current.get("precipitation_mm", 0) > 0:
            lines.append(f"- Precipitation: {current['precipitation_mm']} mm")

        lines.append("\n## 7-Day Forecast\n")
        lines.append("| Day | Conditions | High | Low | Precip | Wind |")
        lines.append("|-----|-----------|------|-----|--------|------|")

        for day in forecast["days"]:
            date_str = day["date"]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = dt.strftime("%a %b %d")
            except ValueError:
                day_name = date_str

            precip = f"{day['precipitation_mm']}mm" if day.get('precipitation_mm') else "—"
            if day.get('precipitation_chance_pct'):
                precip += f" ({day['precipitation_chance_pct']}%)"

            lines.append(
                f"| {day_name} | {day['conditions']} | {day['temp_high_c']}°C | "
                f"{day['temp_low_c']}°C | {precip} | {day['wind_max_kmh']} km/h |"
            )

        return "\n".join(lines)

    def daily_report(self) -> str:
        """Generate a formatted markdown weather report for today."""
        current = self.current_weather()
        forecast = self.daily_forecast(days=1)
        today = forecast["days"][0] if forecast["days"] else {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Today's Weather — {self.city}",
            f"*Generated: {now}*\n",
            f"## Current Conditions\n",
            f"**{current['temperature_c']}°C** — {current['conditions']}",
            f"- Feels like: {current['feels_like_c']}°C",
            f"- Humidity: {current['humidity_pct']}%",
            f"- Wind: {current['wind_speed_kmh']} km/h (gusts {current['wind_gusts_kmh']} km/h)",
        ]

        if today:
            lines.extend([
                f"\n## Today's Forecast\n",
                f"- High: **{today['temp_high_c']}°C** / Low: **{today['temp_low_c']}°C**",
                f"- Conditions: {today['conditions']}",
            ])
            if today.get('precipitation_mm', 0) > 0 or today.get('precipitation_chance_pct', 0) > 0:
                lines.append(f"- Precipitation: {today['precipitation_mm']}mm ({today['precipitation_chance_pct']}% chance)")
            if today.get('uv_index'):
                uv = today['uv_index']
                uv_level = "Low" if uv < 3 else "Moderate" if uv < 6 else "High" if uv < 8 else "Very High"
                lines.append(f"- UV Index: {uv} ({uv_level})")
            if today.get('sunrise') and today.get('sunset'):
                lines.append(f"- Sunrise: {today['sunrise'][-5:]} / Sunset: {today['sunset'][-5:]}")

        return "\n".join(lines)
