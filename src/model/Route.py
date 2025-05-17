import gpxpy
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from geopy.distance import geodesic
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.signal import savgol_filter
from dataclasses import dataclass
from typing import List, Dict, Optional
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

from model.OpenMeteoAPI import meteo_api_request

@dataclass
class TrackPoint:
    """Classe per rappresentare un punto del percorso"""
    lat: float
    lon: float
    ele: float
    time: Optional[pd.Timestamp] = None
    speed: Optional[float] = None

class Percorso:
    def __init__(self, file_path: str):
        """Inizializza il percorso caricando il file GPX"""
        self.original_points = self._read_gpx(file_path)
        self.simplified_points = []
        self.metrics_df = pd.DataFrame()
        
    def _read_gpx(self, gpx_file: str) -> List[TrackPoint]:
        """Legge il file GPX e restituisce una lista di TrackPoint"""
        try:
            gpx = gpxpy.parse(gpx_file)
        except Exception as e:
            st.error(f"Error reading GPX file: {e}")
            return None
            
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append(TrackPoint(
                        lat=point.latitude,
                        lon=point.longitude,
                        ele=point.elevation,
                        time=pd.to_datetime(point.time) if point.time else None
                    ))
        return points
    
    def simplify(self, min_distance: float = 50) -> None:
        """Semplifica il percorso mantenendo solo punti distanti almeno min_distance metri"""
        if not self.original_points:
            return
            
        self.simplified_points = [self.original_points[0]]
        
        for current_point in self.original_points[1:]:
            last_point = self.simplified_points[-1]
            dist = geodesic((last_point.lat, last_point.lon), 
                          (current_point.lat, current_point.lon)).meters
            
            if dist >= min_distance:
                self.simplified_points.append(current_point)
    
    def calculate_metrics(self, smoothing_window: int = 11) -> None:
        """Calcola tutte le metriche del percorso"""
        if not self.simplified_points:
            self.simplify()  # Semplifica automaticamente se non fatto
            
        df = pd.DataFrame([{
            'lat': p.lat,
            'lon': p.lon,
            'ele': round(p.ele),
            'time': p.time
        } for p in self.simplified_points])
        
        # Calcola distanze tra punti consecutivi
        df['distance'] = df.apply(
            lambda row: self._calculate_distance(df, row.name),
            axis=1
        )

        # Calcolo bearing
        df['bearing'] = df.apply(
            lambda row: self._calculate_bearing(df, row.name),
            axis=1
        )
        
        # Smoothing dell'elevazione
        df['ele_smooth'] = self._smooth_elevation(df['ele'], smoothing_window)
        
        # Calcola metriche derivate
        df['dislivello'] = df['ele_smooth'].diff().fillna(0)
        df['pendenza'] = self._calculate_slope(df)
        df['dist_cumulata'] = df['distance'].cumsum()
        df['dislivello_pos_cumulato'] = df['dislivello'].apply(lambda x: max(0, x)).cumsum()
        df['dislivello_neg_cumulato'] = df['dislivello'].apply(lambda x: min(0, x)).cumsum()
        
        self.metrics_df = df
    
    def _calculate_distance(self, df: pd.DataFrame, index: int) -> float:
        """Calcola distanza tra punto corrente e precedente"""
        if index == 0:
            return 0.0
        p1 = (df.iloc[index-1]['lat'], df.iloc[index-1]['lon'])
        p2 = (df.iloc[index]['lat'], df.iloc[index]['lon'])
        return round(geodesic(p1, p2).meters)

    def _calculate_bearing(self, df: pd.DataFrame, index: int) -> float:
        """Calcola il bearing (direzione di marcia) tra il punto corrente e il precedente, in gradi da nord"""
        if index == 0:
            return 0

        prev_point = df.iloc[index - 1]
        curr_point = df.iloc[index]

        lat1, lon1 = np.radians([prev_point['lat'], prev_point['lon']])
        lat2, lon2 = np.radians([curr_point['lat'], curr_point['lon']])
        
        dlon = lon2 - lon1
        x = np.sin(dlon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
        bearing_rad = np.arctan2(x, y)
        bearing_deg = (np.degrees(bearing_rad) + 360) % 360
        
        return round(bearing_deg)
    
    def _smooth_elevation(self, elevation: pd.Series, window: int) -> np.ndarray:
        """Applica smoothing all'elevazione"""
        if len(elevation) > window:
            window = window if window % 2 == 1 else window - 1  # Finestra dispari
            return savgol_filter(elevation, window, 3)
        return round(elevation.values)
    
    def _calculate_slope(self, df: pd.DataFrame) -> pd.Series:
        """Calcola la pendenza percentuale"""
        return np.where(
            df['distance'] > 0,
            (df['dislivello'] / df['distance']) * 100,
            0
        )
    
    def plot_elevation_profile(self):
        """Visualizza il profilo altimetrico con la nuova palette di colori"""
        if self.metrics_df.empty:
            self.calculate_metrics()
            
        df = self.metrics_df
        
        plt.figure(figsize=(14, 7))
        
        # Creazione della custom colormap
        colors = [
            (1, 1, 1),    # Bianco per discese (slope < 0)
            (0, 0.5, 1),  # Blu chiaro per piano (slope = 0)
            (1, 0, 0),    # Rosso per salita leggera
            (0.7, 0, 0),  # Rosso scuro
            (0.4, 0, 0),  # Rosso molto scuro
            (0, 0, 0)     # Nero per pendenze estreme
        ]
        cmap = LinearSegmentedColormap.from_list('custom_slope', colors, N=256)
        
        # Plot della linea principale
        plt.plot(
            df['dist_cumulata'], 
            df['ele_smooth'], 
            color='#333333', 
            linewidth=1.5,
            zorder=1
        )
        
        # Riempimento con colore in base alla pendenza
        for i in range(len(df)-1):
            slope = df['pendenza'].iloc[i+1]
            
            # Normalizzazione pendenza (0-1 per salite, -1-0 per discese)
            norm_slope = np.clip(slope/30, -1, 1)  # Scala fino a 30% pendenza
            
            if slope < 0:
                color = (1, 1, 1)  # Bianco fisso per discese
            elif slope < 1:
                color = (0, 0.5, 1)  # Blu per pianura
            elif slope < 8:
                color = (1, 0, 0)  # Rosso per salita moderata (1-8%)
            elif slope < 12:
                color = (0.7, 0, 0)  # Rosso per salita ripida (8-12%)
            else:
                # Scala rosso-nero per salite (2-30%+)
                color = cmap((norm_slope + 1)/2)  # Mappatura a [0,1]
            
            plt.fill_between(
                [df['dist_cumulata'].iloc[i], df['dist_cumulata'].iloc[i+1]],
                [df['ele_smooth'].iloc[i], df['ele_smooth'].iloc[i+1]],
                color=color,
                alpha=0.7,
                zorder=0
            )
        
        # Titolo e assi
        plt.title('Profilo Altimetrico - Pendenza', fontsize=16, pad=20)
        plt.xlabel('Distanza cumulativa (m)', fontsize=12)
        plt.ylabel('Elevazione (m)', fontsize=12)
        plt.grid(True, linestyle=':', alpha=0.5)
        
        # Legenda personalizzata
        legend_elements = [
            Patch(facecolor='white', label='Discesa'),
            Patch(facecolor='#0080FF', label='Pianeggiante (<1%)'),
            Patch(facecolor='red', label='Salita moderata (1-8%)'),
            Patch(facecolor='darkred', label='Salita ripida (8-12%)'),
            Patch(facecolor='black', label='Pendenza estrema (>12%)')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        # Aggiungi scala colori
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=-30, vmax=30))
        sm.set_array([])
        cbar = plt.colorbar(sm, label='Pendenza (%)')
        cbar.set_ticks([-30, -15, 0, 15, 30])
        
        plt.tight_layout()
        plt.show()
    
    def get_stats(self) -> Dict[str, float]:
        """Restituisce statistiche riassuntive del percorso"""
        if self.metrics_df.empty:
            self.calculate_metrics()
            
        df = self.metrics_df
        return {
            'distanza_totale_km': df['distance'].sum() / 1000,
            'dislivello_positivo_m': df['dislivello_pos_cumulato'].iloc[-1],
            'dislivello_negativo_m': abs(df['dislivello_neg_cumulato'].iloc[-1]),
            'pendenza_media_perc': df['pendenza'].mean(),
            'pendenza_massima_perc': df['pendenza'].max(),
            'num_punti_originali': len(self.original_points),
            'num_punti_semplificati': len(self.simplified_points)
        }

    def get_speed(self, bike_model, power: float = 180) -> None:
        """
        Aggiunge colonne derivate da bike_model.calculate_speed:
        - speed: velocità stimata
        - time_str: tempo impiegato
        - vam: velocità ascensionale media
        - calories: stima delle calorie consumate

        Args:
            bike_model: oggetto con metodo calculate_speed(power, distanza_km, dislivello, headwind)
            power: potenza media espressa in watt
        """
        if self.metrics_df.empty:
            raise ValueError("metrics_df è vuoto. Eseguire prima calculate_metrics().")

        velocità = []
        tempi = []
        vams = []
        calorie = []

        for _, row in self.metrics_df.iterrows():
            distanza_km = row['distance'] / 1000
            dislivello = round(row['dislivello'])

            speed, components, info = bike_model.calculate_speed(
                power, distanza_km, dislivello, headwind=0
            )

            velocità.append(speed)
            tempi.append(info.get('time_str'))
            vams.append(info.get('vam'))
            calorie.append(info.get('calories'))

        self.metrics_df['speed'] = velocità
        self.metrics_df['time_str'] = tempi
        self.metrics_df['vam'] = vams
        self.metrics_df['calories'] = calorie

        self.total_distance = round(self.metrics_df['distance'].sum() / 1000, 2)
        self.total_calories = round(self.metrics_df['calories'].sum(), 2)

    def plot_speed_profile(self):
        """Mostra grafici interattivi di elevazione e velocità lungo il percorso"""
        if self.metrics_df.empty:
            self.calculate_metrics()

        df = self.metrics_df.copy()

        # === Profilo Altimetrico ===
        fig_elev = go.Figure()
        fig_elev.add_trace(go.Scatter(
            x=df['dist_cumulata']/1000,
            y=df["ele_smooth"],
            mode='lines',
            name='Altitude',
            line=dict(color='green')
        ))
        fig_elev.update_layout(
            xaxis_title="Distance (km)",
            yaxis_title="Altitude (m)",
            template="plotly_white",
            height=500
        )
        st.plotly_chart(fig_elev, use_container_width=True)

        # Velocità
        fig_speed = go.Figure()
        fig_speed.add_trace(go.Scatter(
            x=df['dist_cumulata']/1000,
            y=df['speed'],
            mode='lines',
            name='Speed',
            line=dict(color='blue')
        ))
        fig_speed.update_layout(
            xaxis_title='Distance (km)',
            yaxis_title='Speed (km/h)',
            template='plotly_white',
            height=500
        )

        # Mostra i grafici in Streamlit
        st.plotly_chart(fig_speed, use_container_width=True)

    def add_timestamp(self, start_time: str | datetime) -> None:
        """
        Calcola l'orario di passaggio per ogni segmento basandosi su 'time_str' e un orario di partenza.

        Args:
            start_time: Orario di partenza come stringa (formato 'HH:MM:SS' o 'YYYY-mm-dd HH:MM:SS') o oggetto datetime.
        """
        if self.metrics_df.empty:
            raise ValueError("metrics_df è vuoto. Eseguire prima get_speed().")

        if isinstance(start_time, str):
            try:
                # Prova a interpretare la stringa completa con data
                start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            except ValueError:
                # Altrimenti interpreta solo l'orario
                start_time = datetime.strptime(start_time, "%H:%M")

        passage_times = []
        current_time = start_time

        for time_str in self.metrics_df['time_str']:
            h, m, s = map(int, time_str.split(":"))
            delta = timedelta(hours=h, minutes=m, seconds=s)
            current_time += delta
            passage_times.append(current_time.strftime("%Y-%m-%d %H:%M"))

        self.metrics_df['passage_time'] = passage_times

        self.start_time = start_time.strftime("%Y-%m-%d %H:%M")
        self.end_time = passage_times[-1]

        total_seconds = sum(
            [int(h) * 3600 + int(m) * 60 + int(s)
             for h, m, s in (time.split(":") for time in self.metrics_df['time_str'])]
        )
        delta_total = timedelta(seconds=total_seconds)
        hours, remainder = divmod(delta_total.seconds, 3600)
        minutes = remainder // 60
        self.total_hours = f"{hours:02d}:{minutes:02d}"

        ore_decimali = total_seconds / 3600
        self.avg_speed = round(self.total_distance / ore_decimali, 2) if ore_decimali > 0 else 0

    def mark_forecast_points(self, window_minutes: int = 5) -> None:
        """
        Aggiunge una colonna 'get_forecast' al DataFrame, marcando True solo per
        i timestamp più vicini agli orari HH:00, HH:15, HH:30, HH:45 entro una finestra.

        Args:
            window_minutes: Minuti prima e dopo il quarto d'ora da considerare (default 5).
        """
        if self.metrics_df.empty or 'passage_time' not in self.metrics_df.columns:
            raise ValueError("Eseguire prima add_timestamp() per avere passage_time.")

        df = self.metrics_df.copy()
        df['passage_time'] = pd.to_datetime(df['passage_time'])
        df['get_forecast'] = False

        # Genera tutti i target: HH:00, HH:15, HH:30, HH:45 nel range coperto dal percorso
        start = df['passage_time'].min().floor('H')
        end = df['passage_time'].max().ceil('H') + timedelta(minutes=45)

        quarters = pd.date_range(start=start, end=end, freq='15min')

        # Per ogni quarto d'ora, cerca il timestamp più vicino entro la finestra e marca come True
        window = pd.Timedelta(minutes=window_minutes)

        for target_time in quarters:
            mask = (df['passage_time'] >= target_time - window) & (df['passage_time'] <= target_time + window)
            if mask.any():
                closest_idx = (df.loc[mask, 'passage_time'] - target_time).abs().idxmin()
                df.at[closest_idx, 'get_forecast'] = True

        self.metrics_df['get_forecast'] = df['get_forecast']

    def weather_forecast(self):
        def apply_forecast(row):
            if row['get_forecast']:
                return meteo_api_request(row['lat'], row['lon'], row['passage_time'], row['bearing'])
            else:
                return None

        # Applica la funzione e salva i risultati in una nuova colonna
        self.metrics_df['forecast'] = self.metrics_df.apply(apply_forecast, axis=1)

        # Espandi il dizionario in più colonne
        forecast_df = self.metrics_df['forecast'].apply(pd.Series, dtype='object')
        self.metrics_df = pd.concat([self.metrics_df.drop(columns=['forecast']), forecast_df], axis=1)

    def plot_weather(self):
        """
        Genera grafici interattivi del profilo altimetrico e delle variabili meteorologiche lungo il percorso.
        """
        meteo_cols = ["t_2m_C", "prec_mm", "prec_probability_%", "tailwind", "WMO_code", "UV_index"]
        df = self.metrics_df.copy()
        x = df["dist_cumulata"] / 1000  # Converti in km

        # === Grafici meteo ===
        for col in meteo_cols:
            df[col] = df[col].interpolate()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x,
                y=df[col],
                mode='lines',
                name=col,
                line=dict(width=2, color='steelblue'),
                connectgaps=True
            ))
            fig.update_layout(
                title=col,
                xaxis_title="Distanza (km)",
                yaxis_title=col,
                template="plotly_white",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
        #plt.show()

    def show_interactive_map(self):
        """Mostra una mappa interattiva con tooltip su ogni punto del percorso"""
        if self.metrics_df.empty:
            self.calculate_metrics()

        df = self.metrics_df.copy()

        # Centra la mappa sul primo punto
        center = [df['lat'].iloc[0], df['lon'].iloc[0]]
        m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")

        # Linea del percorso
        points = list(zip(df['lat'], df['lon']))
        folium.PolyLine(points, color="blue", weight=3, opacity=0.7).add_to(m)

        # Marker con tooltip per ogni punto (puoi filtrare per prestazioni)
        step = max(1, len(df) // 500)  # massimo 500 marker
        for i in range(0, len(df), step):
            lat = df.iloc[i]['lat']
            lon = df.iloc[i]['lon']
            km = df.iloc[i]['cum_distance'] / 1000  # converti in km
            time = df.iloc[i]['passage_time']
            tooltip = f"{km:.2f} km<br>{time}"
            folium.CircleMarker(
                location=(lat, lon),
                radius=2,
                color='red',
                fill=True,
                fill_opacity=0.4,
                tooltip=tooltip
            ).add_to(m)

        # Mostra mappa in Streamlit
        st.subheader("Mappa del Percorso")
        st_folium(m, width=700, height=500)