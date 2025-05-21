import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model.OpenMeteoAPI import APIrequest

class Forecast:
    def __init__(self, route_df: pd.DataFrame):
        """
        Inizializza la classe con un DataFrame contenente dati di traccia (GPX).
        Il DataFrame deve contenere almeno le colonne:
        - passage_time (datetime)
        - dist_cumulata (float)
        - lat (float)
        - lon (float)
        - bearing (integer)
        - get_forecast (boolean)
        """
        self.route_df = route_df[['passage_time', 'dist_cumulata', 'lat', 'lon', 'bearing', 'get_forecast']]
        self.forecast_df = pd.DataFrame()

    def get_forecast(self, models: str) -> pd.DataFrame:
        """
        Richiede i dati di previsione per i punti del percorso dove 'get_forecast' è True.
        I dati vengono salvati come attributo interno (forecast_df).
        """
        forecast_data = []

        mask = self.route_df['get_forecast'] == True
        sub_df = self.route_df[mask]

        for idx in sub_df.index:
            row = self.route_df.loc[idx]
            forecast = APIrequest(row['lat'], row['lon'], row['passage_time'], row['bearing'], models)

            if forecast and isinstance(forecast, dict):
                forecast.update({
                    "index": idx,
                    "passage_time": row["passage_time"],
                    "dist_cumulata": row["dist_cumulata"]
                })
                forecast_data.append(forecast)

        if forecast_data:
            self.forecast_df = pd.DataFrame(forecast_data).set_index("index")
        else:
            self.forecast_df = pd.DataFrame()

        return self.forecast_df

    def plot_forecast(self):
        """
        Genera grafici interattivi delle variabili meteo lungo il percorso.
        """
        if self.forecast_df.empty:
            st.warning("⚠️ Forecast data unavailable for the selected datetime and model.")
            return

        meteo_cols = [
            "temp", "prec_mm", "rain", "snowfall", "tailwind", "lateral_wind", "WMO_code", "cloud_cover", "UV_index"
        ]
        bar_cols = {"prec_mm", "rain", "snowfall"}
        x = self.forecast_df["dist_cumulata"] / 1000  # km

        for col in meteo_cols:
            if col not in self.forecast_df.columns:
                continue

            self.forecast_df[col] = self.forecast_df[col].interpolate()

            fig = go.Figure()
            if col in bar_cols:
                fig.add_trace(go.Bar(
                    x=x,
                    y=self.forecast_df[col],
                    name=col,
                    marker_color='skyblue'
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=x,
                    y=self.forecast_df[col],
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