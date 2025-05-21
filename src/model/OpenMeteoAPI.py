# Chiamate API
import openmeteo_requests
import requests_cache
from retry_requests import retry

# Elaborazione dati
import pandas as pd
import numpy as np

# Date e Timezone
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz

# Grafici meteo
import plotly.graph_objects as go
import streamlit as st

def map_weather_code(code):
    weather_map = {
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
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Heavy rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    return weather_map.get(code, "Unknown weather code")

def wind_components(wind_speed: float, wind_direction: float, bearing: float) -> tuple[float, float]:
    """
    Calcola le componenti del vento parallela (vento frontale o di coda)
    e ortogonale (vento laterale) rispetto alla direzione del ciclista.

    Parametri:
    - wind_speed (float): velocità del vento in km/h
    - wind_direction (float): direzione *da cui* proviene il vento (in gradi, 0 = da nord)
    - bearing (float): direzione in cui si muove il ciclista (in gradi, 0 = verso nord)

    Ritorna:
    - tailwind (float): positiva se favorevole (vento da dietro), negativa se contraria
    - crosswind (float): componente laterale (destra/sinistra)
    """

    # Calcola la direzione verso cui soffia il vento (inversione)
    wind_blowing_towards = (wind_direction + 180) % 360

    # Calcola angolo relativo tra vento che soffia e direzione del ciclista
    relative_angle_rad = np.radians(wind_blowing_towards - bearing)

    # Componente parallela (positiva = vento favorevole, negativa = contrario)
    tailwind = wind_speed * np.cos(relative_angle_rad)

    # Componente ortogonale (vento laterale)
    crosswind = wind_speed * np.sin(relative_angle_rad)

    return round(tailwind,1), round(crosswind,1)


def APIrequest(lat, lon, datetime_str, bearing, models):
    def safe_extract_and_round(df, key, ndigits=0):
        val = df.get(key, np.nan)
        return round(val, ndigits) if pd.notna(val) else np.nan

    # Setup Open-Meteo API client
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["uv_index", "cloud_cover"],
        "minutely_15": [
            "temperature_2m", "precipitation", "rain", "snowfall",
            "weather_code", "wind_speed_10m", "wind_direction_10m"
        ],
        "models": models,
        "timezone": "auto",
        "temporal_resolution": "native"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    timezone_name = response.Timezone()
    local_tz = pytz.timezone(timezone_name)

    # Parse input datetime
    target_time_local = local_tz.localize(pd.to_datetime(datetime_str))
    target_time_utc = target_time_local.astimezone(pytz.UTC)

    # === MINUTELY_15 ===
    minutely_15 = response.Minutely15()
    minutely_keys = [
        "temperature_2m", "precipitation", "rain", "snowfall",
        "weather_code", "wind_speed_10m", "wind_direction_10m"
    ]
    minutely_data = {
        "date": pd.date_range(
            start=pd.to_datetime(minutely_15.Time(), unit="s", utc=True),
            end=pd.to_datetime(minutely_15.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=minutely_15.Interval()),
            inclusive="left"
        )
    }

    for i, key in enumerate(minutely_keys):
        try:
            minutely_data[key] = minutely_15.Variables(i).ValuesAsNumpy()
        except:
            minutely_data[key] = [np.nan] * len(minutely_data["date"])  # Fill with NaNs if missing

    minutely_15_df = pd.DataFrame(minutely_data)
    minutely_15_df["datetime_local"] = minutely_15_df["date"].dt.tz_convert(local_tz)

    # === HOURLY ===
    hourly = response.Hourly()
    hourly_keys = ["uv_index", "cloud_cover"]
    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )
    }

    for i, key in enumerate(hourly_keys):
        try:
            hourly_data[key] = hourly.Variables(i).ValuesAsNumpy()
        except:
            hourly_data[key] = [np.nan] * len(hourly_data["date"])

    hourly_df = pd.DataFrame(hourly_data)
    hourly_df["datetime_local"] = hourly_df["date"].dt.tz_convert(local_tz)

    # Check valid range
    if target_time_local < minutely_15_df['datetime_local'].min() or target_time_local > minutely_15_df['datetime_local'].max():
        print("⚠️ Target time fuori intervallo previsione.")
        return None

    # Trova record più vicino
    minutely_15_df["time_diff"] = (minutely_15_df["datetime_local"] - target_time_local).abs()
    closest_15_min = minutely_15_df.loc[minutely_15_df["time_diff"].idxmin()]

    hourly_df["time_diff"] = (hourly_df["datetime_local"] - target_time_local).abs()
    closest_hourly = hourly_df.loc[hourly_df["time_diff"].idxmin()]

    # === Composizione dati previsione ===
    forecast_data = {
        "temp": safe_extract_and_round(closest_15_min, "temperature_2m", 1),
        "prec_mm": safe_extract_and_round(closest_15_min, "precipitation", 1),
        "rain": safe_extract_and_round(closest_15_min, "rain", 1),
        "snowfall": safe_extract_and_round(closest_15_min, "snowfall", 1),
        "ws_10m_kmh": safe_extract_and_round(closest_15_min, "wind_speed_10m", 1),
        "wd_10m_deg": safe_extract_and_round(closest_15_min, "wind_direction_10m"),
        "tailwind": wind_components(
            closest_15_min.get("wind_speed_10m", 0),
            closest_15_min.get("wind_direction_10m", 0),
            bearing
        )[0],
        "crosswind": wind_components(
            closest_15_min.get("wind_speed_10m", 0),
            closest_15_min.get("wind_direction_10m", 0),
            bearing
        )[1],
        "WMO_code": map_weather_code(closest_15_min.get("weather_code", np.nan)),
        "UV_index": safe_extract_and_round(closest_hourly, "uv_index", 1),
        "cloud_cover": safe_extract_and_round(closest_hourly, "cloud_cover"),
        "model": models
    }

    return forecast_data