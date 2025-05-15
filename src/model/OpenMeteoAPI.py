import openmeteo_requests

import requests_cache
from retry_requests import retry

import pandas as pd
import numpy as np
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz

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
    - wind_parallel (float): positiva se favorevole (vento da dietro), negativa se contraria
    - wind_lateral (float): componente laterale (destra/sinistra)
    """

    # Calcola la direzione verso cui soffia il vento (inversione)
    wind_blowing_towards = (wind_direction + 180) % 360

    # Calcola angolo relativo tra vento che soffia e direzione del ciclista
    relative_angle_rad = np.radians(wind_blowing_towards - bearing)

    # Componente parallela (positiva = vento favorevole, negativa = contrario)
    wind_parallel = wind_speed * np.cos(relative_angle_rad)

    # Componente ortogonale (vento laterale)
    wind_lateral = wind_speed * np.sin(relative_angle_rad)

    return round(wind_parallel,1), round(wind_lateral,1)


def meteo_api_request(lat, lon, datetime_str, bearing):
    # Setup Open-Meteo API client
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["uv_index", "precipitation_probability"],
        "minutely_15": ["temperature_2m", "precipitation", "wind_speed_10m", "weather_code", "wind_direction_10m"],
        "models": "best_match",
        "timezone": "auto",
        "temporal_resolution": "native"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    # Ottieni la timezone locale dalla risposta dell'API
    timezone_name = response.Timezone()
    local_tz = pytz.timezone(timezone_name)

    # Parse input datetime (localtime)
    target_time_local = pd.to_datetime(datetime_str)
    target_time_utc = local_tz.localize(target_time_local).astimezone(pytz.UTC)

    # --- Minutely 15 data ---
    minutely_15 = response.Minutely15()
    minutely_15_df = pd.DataFrame({
        "date": pd.date_range(
            start=pd.to_datetime(minutely_15.Time(), unit="s", utc=True),
            end=pd.to_datetime(minutely_15.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=minutely_15.Interval()),
            inclusive="left"
        ),
        "temperature_2m": minutely_15.Variables(0).ValuesAsNumpy(),
        "precipitation": minutely_15.Variables(1).ValuesAsNumpy(),
        "wind_speed_10m": minutely_15.Variables(2).ValuesAsNumpy(),
        "weather_code": minutely_15.Variables(3).ValuesAsNumpy(),
        "wind_direction_10m": minutely_15.Variables(4).ValuesAsNumpy()
    })

    hourly = response.Hourly()
    hourly_df = pd.DataFrame({
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "uv_index": hourly.Variables(0).ValuesAsNumpy(),
        "precipitation_probability": hourly.Variables(1).ValuesAsNumpy(),
    })


    # Converti i timestamp minutely_15 da UTC a ora locale
    minutely_15_df['datetime_local'] = minutely_15_df['date'].dt.tz_convert(local_tz)
    hourly_df['datetime_local'] = hourly_df['date'].dt.tz_convert(local_tz)

    # 2. Assicurati che 'target_time_local' sia timezone-aware
    target_time_local = local_tz.localize(target_time_local) 

    # Verifica se target_time_local è dentro il range della previsione
    if target_time_local < minutely_15_df['datetime_local'].min():
        print("Target time is before the first available forecast time.")
        return None
    elif target_time_local > minutely_15_df['datetime_local'].max():
        print("Target time is after the last available forecast time.")
        return None
    else:
        # Trova il timestamp più vicino
        minutely_15_df['time_diff'] = (minutely_15_df['datetime_local'] - target_time_local).abs()
        closest_15_min = minutely_15_df.loc[minutely_15_df['time_diff'].idxmin()]
        hourly_df['time_diff'] = (hourly_df['datetime_local'] - target_time_local).abs()
        closest_hourly = hourly_df.loc[hourly_df['time_diff'].idxmin()]

    # 4. Estrai i dati del timestamp più vicino come JSON
    forecast_data = {
        "t_2m_C": round(closest_15_min['temperature_2m'], 1),
        "prec_mm": round(closest_15_min['precipitation'], 1),
        "prec_probability_%": round(closest_hourly['precipitation_probability']),
        "ws_10m_kmh": round(closest_15_min['wind_speed_10m'], 1),
        "wd_10m_deg": round(closest_15_min['wind_direction_10m']),
        "tailwind": wind_components(closest_15_min['wind_speed_10m'], closest_15_min['wind_direction_10m'], bearing)[0],
        "lateral_wind": wind_components(closest_15_min['wind_speed_10m'], closest_15_min['wind_direction_10m'], bearing)[1],
        "WMO_code": map_weather_code(closest_15_min['weather_code']),
        "UV_index": round(closest_hourly['uv_index'],1)
    }

    return forecast_data