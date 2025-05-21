import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict
from math import floor

@dataclass
class BikeSetup:
    """Configurazione della bicicletta e del ciclista"""
    W_cyclist: float            # Peso ciclista [kg]
    W_bike: float               # Peso bici [kg]
    W_other: float              # Altro peso [kg]
    Crr: float                  # Coefficiente resistenza rotolamento
    Cd: float                   # Coefficiente aerodinamico
    A: float                    # Area frontale [m²]
    drivetrain_loss: float      # Perdite trasmissione (2%)
    metabolic_efficiency: float # Efficienza metabolica (25% tipico)
    max_descent_speed: float    # Velocità massima in discesa

class CyclingPowerModel:
    """
    Modello per il calcolo della velocità
    basato sulla potenza applicata e sulle resistenze
    """
        
    def __init__(self, bike_setup: BikeSetup):
        self.bike = bike_setup
        
    def calculate_speed(self, power: float, distance: float = 1.0, 
                       elevation: float = 0.0, headwind: float = 0.0,
                       air_density: float = 1.226) -> Tuple[float, Dict[str, float]]:
        """
        Calcola la velocità e le componenti di resistenza
        
        Args:
            power: Potenza applicata dal ciclista [W]
            distance: Distanza percorso [km]
            elevation: Dislivello [m]
            headwind: Vento contrario [km/h]
            air_density: Densità aria [kg/m³]
            
        Returns:
            tuple: (velocità [km/h], componenti di resistenza [W])
        """
        # Peso totale e pendenza
        total_weight = self.bike.W_cyclist + self.bike.W_bike + self.bike.W_other
        gradient = np.arctan(elevation / (distance * 1000)) if distance > 0 else 0
        
        # Funzione per calcolare la potenza richiesta
        def power_required(v_kmh: float) -> Tuple[float, Dict[str, float]]:
            v_ms = v_kmh / 3.6
            v_app = (v_kmh - headwind) / 3.6  # Velocità apparente
            
            # Componenti di resistenza
            f_gravity = 9.81 * np.sin(gradient) * total_weight
            f_rolling = 9.81 * np.cos(gradient) * total_weight * self.bike.Crr
            f_drag = 0.5 * self.bike.Cd * self.bike.A * air_density * v_app**2
            
            # Potenza alla ruota e perdite
            power_wheel = (f_gravity + f_rolling + f_drag) * v_ms
            power_total = power_wheel / (1 - self.bike.drivetrain_loss)
            power_loss = power_total - power_wheel
            
            # Calcolo tempo, VAM e calorie
            time_h = distance / v_kmh if v_kmh > 0 else 0
            hours = floor(time_h)
            minutes = floor((time_h - hours) * 60)
            seconds = floor(((time_h - hours) * 60 - minutes) * 60)
            time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
            
            vam = elevation / time_h if time_h > 0 else 0
            
            # Calcolo calorie (1 W = 1 J/s, 1 kcal = 4184 J)
            calories = (power_total / self.bike.metabolic_efficiency) * time_h * 3600 / 4184
            
            power_components = {
                'gravity': round(f_gravity * v_ms),
                'rolling': round(f_rolling * v_ms),
                'drag': round(f_drag * v_ms),
                'drivetrain_loss': round(power_loss),
                'p_rel': round(power_total/self.bike.W_cyclist, 1)
            }

            info = {
                'gradient': round(gradient*100, 1),
                'time_h': time_h,
                'time_str': time_str,
                'vam': round(vam),
                'calories': round(calories)
            }
            
            return power_total, power_components, info
        
        # Metodo di Newton-Raphson per trovare la velocità
        # Guess iniziale velocità
        if gradient > 0:
            v_guess = 30
        elif -0.05 < gradient <= 0:
            v_guess = 50
        elif -0.10 < gradient <= -0.05:
            v_guess = 70
        else:  # gradient <= -10
            v_guess = 100
        
        tolerance = 0.01
        max_iter = 100
        step_size = 0.01
        
        for _ in range(max_iter):
            P, components, info = power_required(v_guess) 
            dP = power_required(v_guess + 0.1)[0] - P
            
            if abs(P - power) < tolerance:
                return v_guess, components, info
                
            v_guess -= (P - power) / (dP / 0.1)
            
        # Se raggiunge il max_iter, restituisce l'ultimo valore con info
        _, components, info = power_required(v_guess)
        return v_guess, components, info
