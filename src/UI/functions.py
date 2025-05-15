import gpxpy
import gpxpy.gpx
import folium
from datetime import datetime, timedelta

# GPX file parsing
def parse_gpx(gpx_file):
    try:
        gpx = gpxpy.parse(gpx_file)
        return gpx
    except Exception as e:
        st.error(f"Errore durante il parsing del file GPX: {e}")
        return None

# Create map
def create_map(gpx):
    if not gpx.tracks:
        st.warning("GPX file has no tracks.")
        return None
    
    # Estrai punti della traccia
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((point.latitude, point.longitude))
    
    if not points:
        st.warning("GPX file has no points.")
        return None
    
    # Crea mappa (temporaneamente centrata sul primo punto)
    m = folium.Map(location=points[0], zoom_start=13)
    
    # Aggiungi linea del percorso
    folium.PolyLine(points, color="red", weight=2.5, opacity=1).add_to(m)
    
    # Aggiungi marker inizio/fine
    if len(points) > 1:
        folium.Marker(
            points[0], 
            tooltip=f"Inizio: {points[0]}",
            icon=folium.Icon(color="green", icon="play", prefix="fa")
        ).add_to(m)
        
        folium.Marker(
            points[-1], 
            tooltip=f"Fine: {points[-1]}",
            icon=folium.Icon(color="red", icon="stop", prefix="fa")
        ).add_to(m)
    
    # Centra la mappa su tutti i punti della traccia
    m.fit_bounds(points)
    
    return m

def default_datetime():
    now = datetime.now() + timedelta(minutes=5)

    # Calcolo dei minuti arrotondati al quarto d'ora successivo
    minute = ((now.minute // 15) + 1) * 15
    if minute == 60:
        now = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        now = now.replace(minute=minute, second=0, microsecond=0)

    return now.date(), now.time()


 
