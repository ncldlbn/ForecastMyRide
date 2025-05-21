CRR_VALUES = {
    'Tubular 23mm': 0.0027,
    'Slick 25mm': 0.0030,
    'Slick 28mm': 0.0032,
    'Slick 30mm': 0.0038,
    'Endurance 32mm': 0.0040,
    'Gravel semi-slick 35mm': 0.0055,
    'Gravel 40mm': 0.0065,
    'Gravel 45mm': 0.0075,
    'XC 2.1–2.25"': 0.0085,
    'Trail 2.3–2.5"': 0.0110,
    'Enduro 2.4–2.6"': 0.0135,
    'Fatbike': 0.0300
}

CD_VALUES = {
    'TT bike': 0.70,
    'Aero bars': 0.80,
    'Drop': 0.90,
    'Hoods': 1.00,
    'Tops': 1.15,
    'MTB': 1.20,
    'Fat bike': 1.30
}

AREA_VALUES = {
    'TT bike': 0.25,
    'Aero bars': 0.30,
    'Drop': 0.35,
    'Hoods': 0.40,
    'Tops': 0.60,
    'MTB': 0.65,
    'Fat bike': 0.70
} 

WEATHER = [
    "Temperature",
    "Precipitation",
    "Rain",
    "Snowfall",
    "WMO code",
    "Cloud cover",
    "Wind speed",
    "Wind direction",
    "Tailwind",
    "Crosswind",
    "UV-index"
]

MODELS = {
    "Best Match": "best_match",
    "DWD ICON": "icon_global",
    "DWD ICON-EU": "icon_eu",
    "DWD ICON-D2": "icon_d2",
    "GEM GLOBAL": "gem_global",
    "Météo-France ARPEGE Europe": "meteofrance_arpege_europe",
    "Météo-France AROME France HD": "meteofrance_arome_france_hd",
    "UK Met Office UK 2km": "ukmo_uk_deterministic_2km",
    "ItaliaMeteo ARPAE ICON 2I": "italia_meteo_arpae_icon_2i"
}