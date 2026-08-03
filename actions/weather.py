"""
Weather summary using Open-Meteo API (Met Office data integration).
Default location is Grantham, UK with lat/lon for hyper-local accuracy.
Supports current conditions, tomorrow, specific weekday, and 10-day outlook.
"""

from __future__ import annotations

import datetime as dt

import requests

# Mapping Open-Meteo condition codes to simple spoken phrases
WMO_CODES = {
    0: "clear skies",
    1: "mainly clear skies",
    2: "partly cloudy skies",
    3: "overcast skies",
    45: "foggy conditions",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "a slight or moderate thunderstorm",
    96: "a thunderstorm with slight hail",
    99: "a thunderstorm with heavy hail",
}

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def get_weather_summary(location: str | None = None) -> str:
    raw_query = (location or "").strip().lower()
    now = dt.datetime.now()

    # Lat/Lon for Grantham, UK to ensure hyper-local accuracy
    lat, lon, city_name = 52.915, -0.638, "Grantham"

    # Determine target day offset from the query string
    target_day_index = 0  # Default to 0 (Today)
    is_forecast = False

    if "tomorrow" in raw_query or "yarin" in raw_query or "yarın" in raw_query:
        target_day_index = 1
        is_forecast = True
    else:
        # Check if a specific weekday name was requested
        for i, day in enumerate(WEEKDAYS):
            if day.lower() in raw_query:
                is_forecast = True
                target_day_index = (i - now.weekday()) % 7
                if target_day_index == 0:
                    target_day_index = 0
                break

    try:
        # Call Open-Meteo API for hyper-local data
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "relative_humidity_2m", "weather_code"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min"],
            "timezone": "Europe/London",
            "forecast_days": 10,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # SUMMARY 10-DAY OUTLOOK
        if "10 day" in raw_query or "10-day" in raw_query or "outlook" in raw_query:
            daily = data["daily"]
            lines = [f"Here is the 10-day weather outlook for {city_name}:"]
            for i in range(10):
                day_date = dt.datetime.strptime(daily["time"][i], "%Y-%m-%d")
                day_label = (
                    "Today"
                    if i == 0
                    else "Tomorrow" if i == 1 else WEEKDAYS[day_date.weekday()]
                )
                max_t = round(daily["temperature_2m_max"][i])
                min_t = round(daily["temperature_2m_min"][i])
                code = daily["weather_code"][i]
                cond = WMO_CODES.get(code, "variable weather")
                lines.append(
                    f"- {day_label}: highs of {max_t}, lows of {min_t} with {cond}"
                )
            return "\n".join(lines)

        # TARGETED SINGLE DAY FORECAST (e.g., Tomorrow or Specific Day)
        if is_forecast:
            daily = data["daily"]
            if target_day_index >= len(daily["time"]):
                return f"My local data forecast only extends up to 10 days out."

            max_t = round(daily["temperature_2m_max"][target_day_index])
            min_t = round(daily["temperature_2m_min"][target_day_index])
            code = daily["weather_code"][target_day_index]
            cond = WMO_CODES.get(code, "variable weather")

            day_str = (
                "tomorrow"
                if target_day_index == 1
                else f"on {WEEKDAYS[(now.weekday() + target_day_index) % 7]}"
            )
            return (
                f"Weather forecast for {city_name} {day_str}: Expect {cond}, "
                f"with a low of {min_t} degrees and highs reaching {max_t} degrees."
            )

        # STANDARD CURRENT WEATHER
        current = data["current"]
        temp = round(current["temperature_2m"])
        humidity = current["relative_humidity_2m"]
        code = current["weather_code"]
        cond = WMO_CODES.get(code, "variable weather")

        return (
            f"Current weather for {city_name}: It is currently {temp} degrees with "
            f"{cond}. Relative humidity is {humidity}%."
        )

    except Exception:
        return f"Local weather updates for {city_name} are currently offline."