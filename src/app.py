# --------------------------------------------------------------------
# LIBRARIES
# --------------------------------------------------------------------
# Import Libraries
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime, time
import gpxpy
import gpxpy.gpx
# Custom libraries
from UI.functions import *
from model.defaults import *
from model.Route import Percorso
from model.SpeedModel import CyclingPowerModel, BikeSetup
from model.OpenMeteoAPI import APIrequest
from model.Weather import Forecast

# --------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------
st.set_page_config(page_title="ForecastMyRide", page_icon="🌦️", layout="wide")
st.title("🌦️ ForecastMyRide")

# --------------------------------------------------------------------
# SIDEBAR
# --------------------------------------------------------------------
st.sidebar.header("Configuration")

# === Cyclist and Bike === #
with st.sidebar.expander("🚴 Cyclist and Bike", expanded=True):
    # Weights
    col1, col2, col3 = st.columns(3)
    with col1:
        W_cyclist = st.number_input(
            "Cyclist Weight [kg]", 
            min_value=0.0, 
            max_value=500.0, 
            value=60.0, 
            step=0.1, 
            format="%.1f",
            help="Body weight of the rider."
            )
    with col2:
        W_bike = st.number_input(
            "Bike Weight [kg]", 
            min_value=0.0, 
            max_value=50.0, 
            value=10.0, 
            step=0.1, 
            format="%.1f", 
            help="Weight of the bicycle including base accessories."
            )
    with col3:
        W_other = st.number_input(
            "Load [kg]", 
            min_value=0.0, 
            max_value=100.0, 
            value=2.2, 
            step=0.1, 
            format="%.1f", 
            help="Weight of bags, water bottles, tools, etc."
            )
    # Power
    power = st.slider(
        "Average Power [W]", 
        0, 500, 100,
        help="Average Power in Watt")

# === Loss Coefficients === #
with st.sidebar.expander("⚙️ Loss Coefficients", expanded=False):
    # Crr
    crr_options = list(CRR_VALUES.keys()) + ["Custom"]
    col1, col2 = st.columns(2)
    with col1:
        crr_option = st.selectbox(
            "Tires", 
            crr_options, 
            index=crr_options.index('Slick 30mm'), 
            help="Choose your tires, or select 'Custom' to manually enter a Crr value."
            )
    with col2:
        if crr_option == "Custom":
            Crr = st.number_input(
                "Rolling Resistance (Crr)", 
                min_value=0.0001, 
                max_value=0.05, 
                value=0.0040, 
                step=0.0001, 
                format="%.4f"
                )
        else:
            Crr = st.number_input(
                "Rolling Resistance (Crr)", 
                min_value=CRR_VALUES[crr_option], 
                max_value=CRR_VALUES[crr_option], 
                value=CRR_VALUES[crr_option], 
                step=0.0001, 
                format="%.4f"
                )
    # Cd
    pos_options = list(CD_VALUES.keys()) + ["Custom"]
    col1, col2 = st.columns(2)
    with col1:
        position = st.selectbox(
            "Riding position", 
            pos_options, 
            index=pos_options.index('Hoods'), 
            help="Choose your riding position, or select 'Custom' to manually enter a Cd and Frontal Area values."
            )
    with col2:
        if position == "Custom":
            Cd = st.number_input(
                "Drag Coefficient (Cd)", 
                min_value=0.5, 
                max_value=2.0, 
                value=1.0, 
                step=0.01, 
                format="%.2f"
                )
            A = st.number_input(
                "Frontal Area [m²]", 
                min_value=0.2, 
                max_value=1.0, 
                value=0.4, 
                step=0.01, 
                format="%.2f"
                )
        else:
            Cd = st.number_input(
                "Drag Coefficient (Cd)", 
                min_value=CD_VALUES[position], 
                max_value=CD_VALUES[position], 
                value=CD_VALUES[position], 
                step=0.01, 
                format="%.2f"
                )
            A = st.number_input(
                "Frontal Area [m²]", 
                min_value=AREA_VALUES[position], 
                max_value=AREA_VALUES[position], 
                value=AREA_VALUES[position], 
                step=0.01, 
                format="%.2f"
                )

# === Weather Forecast === #
with st.sidebar.expander("🌦️ Weather Forecast", expanded=True):
    # Start datetime
    col1, col2 = st.columns(2)
    date_default, time_default = default_datetime()
    with col1:
        date_input = st.date_input(
            "Date", 
            value=date_default
            )
    with col2:
        time_input = st.time_input(
            "Time", 
            value=time_default, 
            help="Start date and time of your ride."
            )
    # Select Weather model
    selected_model = st.selectbox("Model", options=MODELS)
    model = MODELS[selected_model]

# === Footer === #
st.sidebar.markdown("**Credits**")
st.sidebar.markdown("Created with [Streamlit](https://streamlit.io/) using weather data from [OpenMeteoAPI](https://open-meteo.com/)")
st.sidebar.markdown(f"🐙 [Github](https://github.com/ncldlbn/ForecastMyRide/tree/main) Repository", unsafe_allow_html=True)
#st.sidebar.markdown(f"🍺 Support me on [PayPal](https://www.paypal.com/it/home)", unsafe_allow_html=True)

# --------------------------------------------------------------------
# MAIN PAGE
# --------------------------------------------------------------------

# === SETUP === #
# Define start datetime
dt = datetime.combine(date_input, time_input)
# Warning if start datetime is in the past
if dt <= datetime.now():
    st.warning("Date and time must be in the future!")
# Define Bike setup
bike_setup = BikeSetup(W_cyclist, W_bike, W_other, Crr, Cd, A, drivetrain_loss=0.02, metabolic_efficiency=0.25, max_descent_speed=50.0)
bike_model = CyclingPowerModel(bike_setup)

# === Upload GPX File === #
# Init session state
if "percorso" not in st.session_state:
    st.session_state["percorso"] = None
if "time_estimated" not in st.session_state:
    st.session_state["time_estimated"] = False

# Upload GPX button
uploaded_file = st.file_uploader("", type=["gpx"], accept_multiple_files=False, help="Drag the file here or click to select it.")
if uploaded_file is not None:
    if st.button("⏱️ Estimate Ride Time", use_container_width=True):
        percorso = Percorso(uploaded_file)
        percorso.simplify(min_distance=50)
        percorso.calculate_metrics()
        percorso.get_speed(bike_model, power)
        percorso.add_timestamp(dt)

        st.session_state["percorso"] = percorso
        st.session_state["time_estimated"] = True

# Display route info
if st.session_state["time_estimated"]:
    percorso = st.session_state["percorso"]

    cols = st.columns(2)
    with cols[0]:
        st.metric("Start datetime", percorso.start_time)
        st.metric("Distance", f"{percorso.total_distance} km")
        st.metric("Avg speed", f"{percorso.avg_speed} km/h")
    with cols[1]:
        st.metric("End datetime", percorso.end_time)
        st.metric("Total time", f"{percorso.total_hours}")
        st.metric("Kcal", f"{percorso.total_calories:.0f} kcal")

    percorso.plot_speed_profile()

    percorso.mark_forecast_points()

# === Weather Forecast === #
if st.session_state["time_estimated"]:
    if st.button("🌤️ Get Weather Forecast", use_container_width=True):

        percorso = st.session_state["percorso"]
        
        weather = Forecast(percorso.metrics_df)
        weather.get_forecast(model)
        weather.plot_forecast()
