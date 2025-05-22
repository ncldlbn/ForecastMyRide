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
        self.route_df = route_df[['passage_time', 'dist_cumulata', 'lat', 'lon', 'bearing', 'get_forecast']].copy()
        self.forecast = pd.DataFrame()  # Qui verranno salvati solo i punti con previsione

    def get_forecast(self, models: str) -> pd.DataFrame:
        """
        Richiede i dati di previsione per i punti del percorso dove 'get_forecast' è True.
        I dati vengono salvati come attributo interno (data).
        """
        forecast_data = []

        mask = self.route_df['get_forecast'] == True
        sub_df = self.route_df[mask]

        for idx in sub_df.index:
            row = self.route_df.loc[idx]
            if row['get_forecast']:
                forecast = APIrequest(row['lat'], row['lon'], row['passage_time'], row['bearing'], models)

                if forecast and isinstance(forecast, dict):
                    forecast.update({
                        "index": idx,
                        "passage_time": row["passage_time"],
                        "dist_km": row["dist_cumulata"]/1000
                    })
                    forecast_data.append(forecast)

        if forecast_data:
            self.data = pd.DataFrame(forecast_data).set_index("index")
        else:
            self.data = pd.DataFrame()

        self.data.to_csv("forecast_df.csv")

        return self.data
    
    # def plot_forecast(self):
    #     """
    #     Genera grafici interattivi delle variabili meteo lungo il percorso.
    #     """
    #     if self.forecast_df.empty:
    #         st.warning("⚠️ Forecast data unavailable for the selected datetime and model.")
    #         return

    #     meteo_cols = [
    #         "temp", "prec_mm", "rain", "snowfall", "tailwind", "lateral_wind", "WMO_code", "cloud_cover", "UV_index"
    #     ]
    #     bar_cols = {"prec_mm", "rain", "snowfall"}
    #     x = self.forecast_df["dist_cumulata"] / 1000  # km

    #     for col in meteo_cols:
    #         if col not in self.forecast_df.columns:
    #             continue

    #         self.forecast_df[col] = self.forecast_df[col].interpolate()

    #         fig = go.Figure()
    #         if col in bar_cols:
    #             fig.add_trace(go.Bar(
    #                 x=x,
    #                 y=self.forecast_df[col],
    #                 name=col,
    #                 marker_color='skyblue'
    #             ))
    #         else:
    #             fig.add_trace(go.Scatter(
    #                 x=x,
    #                 y=self.forecast_df[col],
    #                 mode='lines',
    #                 name=col,
    #                 line=dict(width=2, color='steelblue'),
    #                 connectgaps=True
    #             ))

    #         fig.update_layout(
    #             title=col,
    #             xaxis_title="Distanza (km)",
    #             yaxis_title=col,
    #             template="plotly_white",
    #             height=500
    #         )
    #         st.plotly_chart(fig, use_container_width=True)

    def plot_temperature(self):
        """
        Crea e visualizza un grafico interattivo della temperatura lungo il percorso.
        Il grafico mostra la distanza in km sull'asse x e la temperatura sull'asse y.
        Include tooltip con temperatura, distanza e orario di passaggio quando si passa con il mouse sopra i punti.
        """
        import plotly.graph_objects as go
        import pandas as pd
        
        # Assicuriamoci che i dati necessari siano presenti
        if 'temp' not in self.data.columns:
            st.error("Temperature data not available.")
            return

        df_plot = self.data[['dist_km', 'temp', 'passage_time']].copy()
            
        if pd.api.types.is_datetime64_any_dtype(df_plot['passage_time']):
            df_plot['passage_time'] = df_plot['passage_time'].dt.strftime('%H:%M:%S')
        
        # Creazione del grafico con Plotly
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_plot['passage_time'],
            y=df_plot['temp'],
            mode='lines+markers',
            name='Temperatura',
            line=dict(color='#FF5733', width=3),
            marker=dict(size=8),
            hovertemplate='<b>Temperature:</b> %{y:.1f}°C<br>' +
                        '<b>Distance:</b> %{customdata:.1f} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot['dist_km']
        ))
        
        # Configurazione del layout
        fig.update_layout(
            yaxis=dict(range=[df_plot['temp'].min() - 1, df_plot['temp'].max() + 1]),
            xaxis_title='Time',
            yaxis_title='Temperature (°C)',
            hovermode='closest',
            template='plotly_white',
            height=500
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        
        # Visualizzazione in Streamlit
        st.plotly_chart(fig, use_container_width=True)

    def plot_precipitation(self):
        """
        Crea e visualizza due grafici interattivi per i dati di precipitazione lungo il percorso:
        1. Un grafico combinato con istogrammi per la precipitazione e una linea per la copertura nuvolosa
        2. Un grafico che mostra i codici WMO (condizioni meteo) lungo il percorso
        
        Entrambi i grafici mostrano la distanza in km sull'asse x e includono tooltip interattivi.
        """
        import plotly.graph_objects as go
        import plotly.subplots as sp
        import pandas as pd
        
        # Assicuriamoci che i dati necessari siano presenti
        required_columns = ['prec_mm', 'cloud_cover', 'WMO_code', 'dist_km', 'passage_time']
        missing_columns = [col for col in required_columns if col not in self.data.columns]
        
        if missing_columns:
            st.error(f"No data available: {', '.join(missing_columns)}.")
            return
            
        # Prendiamo i dati necessari
        df_plot = self.data[['dist_km', 'prec_mm', 'cloud_cover', 'WMO_code', 'passage_time']].copy()
        
        # Convertiamo passage_time in formato stringa leggibile se non lo è già
        if pd.api.types.is_datetime64_any_dtype(df_plot['passage_time']):
            df_plot['passage_time'] = df_plot['passage_time'].dt.strftime('%H:%M:%S')
        
        # PRIMO GRAFICO: Precipitazione e copertura nuvolosa
        fig1 = go.Figure()
        
        # Aggiungiamo le barre per la precipitazione
        fig1.add_trace(go.Bar(
            x=df_plot['passage_time'],
            y=df_plot['prec_mm'],
            name='Precipitation',
            marker_color='#5E9DE6',
            opacity=0.7,
            hovertemplate='<b>Precipitation:</b> %{y:.1f} mm<br>' +
                        '<b>Distance:</b> %{customdata:.1f} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot[['dist_km']]
        ))
        
        # Aggiungiamo la linea per la copertura nuvolosa
        fig1.add_trace(go.Scatter(
            x=df_plot['passage_time'],
            y=df_plot['cloud_cover'],
            mode='lines+markers',
            name='Cloud Cover',
            line=dict(color='#808080', width=3),
            marker=dict(size=6),
            yaxis='y2',
            hovertemplate='<b>Precipitation:</b> %{y:.1f} mm<br>' +
                        '<b>Distance:</b> %{customdata:.1} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot[['dist_km']]
        ))
        
        # Configurazione del layout per il primo grafico
        fig1.update_layout(
            xaxis_title='Time',
            yaxis_title='Precipitation (mm)',
            yaxis=dict(range=[0, max(1, df_plot['prec_mm'].max() + 0.5)]),
            yaxis2=dict(
                title='Cloud Cover (%)',
                overlaying='y',
                side='right',
                range=[0, 110],
                showgrid=False
            ),
            hovermode='closest',
            template='plotly_white',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Visualizzazione in Streamlit
        st.plotly_chart(fig1, use_container_width=True)
        
        # # SECONDO GRAFICO: Codici WMO (condizioni meteo)
        # fig2 = go.Figure()
        
        # # Creiamo un codice colore per le diverse condizioni meteo
        # weather_categories = {
        #     'Clear': [0, 1],
        #     'Cloudy': [2, 3],
        #     'Fog': [45, 48],
        #     'Drizzle': [51, 53, 55, 56, 57],
        #     'Rain': [61, 63, 65, 66, 67, 80, 81, 82],
        #     'Snow': [71, 73, 75, 77, 85, 86],
        #     'Storm': [95, 96, 99]
        # }
        
        # color_map = {
        #     'Clear': '#FFD700',      # Oro
        #     'Cloudy': '#A9A9A9',     # Grigio scuro
        #     'Fog': '#D3D3D3',        # Grigio chiaro
        #     'Drizzle': '#87CEEB',    # Azzurro cielo
        #     'Rain': '#1E90FF',       # Blu
        #     'Snow': '#F0F8FF',       # Bianco ghiaccio
        #     'Storm': '#8B0000'       # Rosso scuro
        # }
        
        # # Determina la categoria per ogni codice WMO
        # def get_weather_category(wmo_code):
        #     for category, codes in weather_categories.items():
        #         if wmo_code in codes:
        #             return category
        #     return 'Other'
        
        # df_plot['weather_category'] = df_plot['WMO_code'].apply(get_weather_category)
        # df_plot['color'] = df_plot['weather_category'].map(color_map)
        
        # # Aggiungiamo i marker per i codici WMO
        # fig2.add_trace(go.Scatter(
        #     x=df_plot['dist_km'],
        #     y=[1] * len(df_plot),  # Posizione fissa sull'asse y
        #     mode='markers+text',
        #     marker=dict(
        #         size=20,
        #         color=df_plot['color'],
        #         symbol='square',
        #         line=dict(width=1, color='DarkSlateGrey')
        #     ),
        #     text=df_plot['WMO_code'],
        #     textposition="middle center",
        #     name='Codice WMO',
        #     hovertemplate='<b>Condizione meteo:</b> %{customdata[1]}<br>' +
        #                 '<b>Codice WMO:</b> %{customdata[0]}<br>' +
        #                 '<b>Distanza:</b> %{x:.2f} km<br>' +
        #                 '<b>Orario:</b> %{customdata[2]}<extra></extra>',
        #     customdata=df_plot[['WMO_code', 'WMO_description', 'passage_time']]
        # ))
        
        # # Configurazione del layout per il secondo grafico
        # fig2.update_layout(
        #     title={
        #         'text': 'Condizioni meteo (codici WMO) lungo il percorso',
        #         'y': 0.9,
        #         'x': 0.5,
        #         'xanchor': 'center',
        #         'yanchor': 'top',
        #         'font': dict(size=20)
        #     },
        #     xaxis_title='Distanza (km)',
        #     yaxis=dict(
        #         showticklabels=False,
        #         showgrid=False,
        #         zeroline=False,
        #         range=[0, 2]
        #     ),
        #     hovermode='closest',
        #     template='plotly_white',
        #     height=300
        # )
        
        # # Aggiungiamo una legenda personalizzata per i codici WMO
        # legend_items = []
        # for category, color in color_map.items():
        #     legend_items.append(
        #         go.Scatter(
        #             x=[None], y=[None],
        #             mode='markers',
        #             marker=dict(size=10, color=color),
        #             name=category,
        #             showlegend=True
        #         )
        #     )
        
        # for item in legend_items:
        #     fig2.add_trace(item)
        
        # # Visualizzazione in Streamlit
        # st.plotly_chart(fig1, use_container_width=True)
        
        # # Mostriamo anche alcune statistiche sulla precipitazione
        # col1, col2, col3 = st.columns(3)
        # with col1:
        #     # Calcoliamo la percentuale di percorso con precipitazione
        #     perc_with_rain = (df_plot['prec_mm'] > 0).mean() * 100
        #     st.metric("Tratti con precipitazione", f"{perc_with_rain:.1f}%")
        # with col2:
        #     st.metric("Precipitazione media", f"{df_plot['prec_mm'].mean():.1f} mm")
        # with col3:
        #     st.metric("Precipitazione massima", f"{df_plot['prec_mm'].max():.1f} mm")
        
        # # Visualizziamo il secondo grafico
        # st.plotly_chart(fig2, use_container_width=True)
        
        # # Aggiungiamo una tabella esplicativa per i codici WMO più comuni presenti nel percorso
        # st.subheader("Legenda codici WMO nel percorso")
        
        # # Prendiamo solo i codici WMO unici presenti nel percorso
        # unique_wmo_codes = df_plot['WMO_code'].unique()
        
        # # Creiamo un dataframe per la tabella
        # wmo_df = pd.DataFrame({
        #     'Codice WMO': [code for code in unique_wmo_codes],
        #     'Descrizione': [wmo_descriptions.get(code, f"Codice {code}") for code in unique_wmo_codes],
        #     'Categoria': [get_weather_category(code) for code in unique_wmo_codes]
        # })
        
        # # Ordiniamo per codice
        # wmo_df = wmo_df.sort_values('Codice WMO')
        
        # Visualizziamo la tabella
        #st.dataframe(wmo_df, use_container_width=True, hide_index=True)

    def plot_wind(self):
        """
        Crea e visualizza un grafico interattivo della componente del vento lungo il percorso.
        Mostra sia il vento a favore (tailwind) che il vento laterale (crosswind).
        """
        import plotly.graph_objects as go
        import pandas as pd

        # Verifica presenza dati
        if not {'tailwind', 'crosswind'}.issubset(self.data.columns):
            st.error("Wind data not available.")
            return

        df_plot = self.data[['dist_km', 'tailwind', 'crosswind', 'passage_time']].copy()

        if pd.api.types.is_datetime64_any_dtype(df_plot['passage_time']):
            df_plot['passage_time'] = df_plot['passage_time'].dt.strftime('%H:%M:%S')

        # Creazione grafico
        fig = go.Figure()

        # Tailwind
        fig.add_trace(go.Scatter(
            x=df_plot['passage_time'],
            y=df_plot['tailwind'],
            mode='lines+markers',
            name='Tailwind',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6),
            hovertemplate='<b>Tailwind:</b> %{y:.1f} km/h<br>' +
                        '<b>Distance:</b> %{customdata:.1f} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot['dist_km']
        ))

        # Crosswind
        fig.add_trace(go.Scatter(
            x=df_plot['passage_time'],
            y=df_plot['crosswind'],
            mode='lines+markers',
            name='Crosswind',
            line=dict(color='#3299a8', width=2, dash='dash'),
            marker=dict(size=6),
            hovertemplate='<b>Tailwind:</b> %{y:.1f} km/h<br>' +
                        '<b>Distance:</b> %{customdata:.1f} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot['dist_km']
        ))

        # Layout
        fig.update_layout(
            xaxis_title='Distance (km)',
            yaxis_title='Wind Speed (km/h)',
            hovermode='closest',
            template='plotly_white',
            height=500,
            legend_title_text='',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

        # Mostra in Streamlit
        st.plotly_chart(fig, use_container_width=True)

    def plot_uv_index(self):
        """
        Crea un grafico interattivo dell'indice UV lungo il percorso.
        Colora lo sfondo in base al livello di rischio UV.
        """
        import plotly.graph_objects as go
        import pandas as pd

        if 'UV_index' not in self.data.columns:
            st.error("UV Index data not available.")
            return

        df_plot = self.data[['dist_km', 'UV_index', 'passage_time']].copy()

        if pd.api.types.is_datetime64_any_dtype(df_plot['passage_time']):
            df_plot['passage_time'] = df_plot['passage_time'].dt.strftime('%H:%M:%S')

        fig = go.Figure()

        # UV Line
        fig.add_trace(go.Scatter(
            x=df_plot['passage_time'],
            y=df_plot['UV_index'],
            mode='lines+markers',
            name='UV Index',
            line=dict(color='#000000', width=3),
            marker=dict(size=6),
            hovertemplate='<b>UV Index:</b> %{y:.1f}<br>' +
                        '<b>Distance:</b> %{customdata:.1f} km<br>' +
                        '<b>Time:</b> %{x}<extra></extra>',
            customdata=df_plot['dist_km']
        ))

        # Background color ranges (OMS UV levels)
        fig.update_layout(
            shapes=[
                # Minimum (0-1) - dark green
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=0, y1=1,
                    fillcolor="white", opacity=0.3, layer="below", line_width=0),
                # low (1-3) - light green
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=1, y1=3,
                    fillcolor="lightgreen", opacity=0.3, layer="below", line_width=0),
                # Moderate (3-6) - yellow
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=3, y1=6,
                    fillcolor="yellow", opacity=0.3, layer="below", line_width=0),
                # High (6-8) - orange
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=6, y1=8,
                    fillcolor="orange", opacity=0.3, layer="below", line_width=0),
                # Very High (8-11) - red
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=8, y1=11,
                    fillcolor="red", opacity=0.3, layer="below", line_width=0),
                # Extreme (11-12) - violet
                dict(type="rect", xref="paper", yref="y",
                    x0=0, x1=1, y0=11, y1=12,
                    fillcolor="purple", opacity=0.3, layer="below", line_width=0),
            ],
            yaxis=dict(range=[-1, 12], showgrid=False),
            xaxis_title='Distance (km)',
            yaxis_title='UV Index',
            hovermode='closest',
            template='plotly_white',
            height=500,
            legend_title_text='',
        )

        #fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        #fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', range=[0, max(12, df_plot['UV_index'].max() + 1)])

        st.plotly_chart(fig, use_container_width=True)

        
        