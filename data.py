import os
import requests

FFWC_URL = os.getenv("FFWC_URL", "").strip()
FFWC_TOKEN = os.getenv("FFWC_TOKEN", "").strip()

def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,rain,precipitation",
        "hourly": "precipitation,rain,temperature_2m,soil_moisture_0_to_10cm",
        "forecast_days": 2, "timezone": "Asia/Dhaka"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        j = r.json()
        hourly = j.get("hourly", {})
        rain = hourly.get("rain", []) or hourly.get("precipitation", [])
        rain24 = sum(float(x or 0) for x in rain[:24])
        current = j.get("current", {})
        return {
            "source": "Open-Meteo live",
            "temperature_c": current.get("temperature_2m"),
            "rain_now_mm": current.get("rain", current.get("precipitation", 0)) or 0,
            "rain_next_24h_mm": round(rain24, 1)
        }
    except Exception as e:
        return {"source": "Fallback", "temperature_c": None, "rain_now_mm": 0, "rain_next_24h_mm": 0, "error": str(e)}

def _try_ffwc(key, station):
    if not FFWC_URL:
        return None
    headers = {"Authorization": f"Bearer {FFWC_TOKEN}"} if FFWC_TOKEN else {}
    try:
        r = requests.get(FFWC_URL, params={"station": key, "format": "json"}, headers=headers, timeout=12)
        r.raise_for_status()
        j = r.json()
        rows = j.get("results", j.get("data", j if isinstance(j, list) else []))
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            return None
        row = rows[0]
        wl = row.get("water_level", row.get("waterlevel", row.get("wl")))
        if wl is None:
            return None
        danger = row.get("danger_level", row.get("dangerlevel", row.get("dl")))
        return {
            "source": "FFWC/BWDB API",
            "water_level": float(wl),
            "water_level_6h_ago": float(row.get("water_level_6h_ago", wl)),
            "water_level_12h_ago": float(row.get("water_level_12h_ago", wl)),
            "water_level_24h_ago": float(row.get("water_level_24h_ago", wl)),
            "upstream_level": float(row.get("upstream_level", wl)),
            "upstream_change": float(row.get("upstream_change", 0)),
            "danger_level": float(danger) if danger is not None else None,
            "trend": row.get("trend", "unknown")
        }
    except Exception:
        return None

def get_station_data(key, station):
    live = _try_ffwc(key, station)
    if live:
        return live

    # DEMO ONLY: replace with real FFWC historical/live observations before judging.
    demo = {
        "mymensingh": (8.10, 7.92, 7.74, 7.45, 8.35, 0.18),
        "sylhet": (7.20, 6.92, 6.60, 6.15, 7.55, 0.22),
        "sunamganj": (5.20, 4.98, 4.75, 4.40, 5.50, 0.17),
        "kurigram": (24.80, 24.55, 24.30, 23.95, 25.10, 0.20)
    }
    v = demo.get(key, demo["mymensingh"])
    return {
        "source": "DEMO — replace with FFWC data",
        "water_level": v[0], "water_level_6h_ago": v[1],
        "water_level_12h_ago": v[2], "water_level_24h_ago": v[3],
        "upstream_level": v[4], "upstream_change": v[5],
        "danger_level": station["danger_level"], "trend": "rising"
    }
