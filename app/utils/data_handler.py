import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
import os
import json
from typing import Union, List

def load_data(filepath):
    """Load the dataset of renewable energy plants."""
    return pd.read_csv(filepath)

def load_cache(cache_file):
    """Load weather cache if available."""
    if os.path.exists(cache_file):
        with open(cache_file, "r") as file:
            return json.load(file)
    return {}

def save_cache(cache, cache_file):
    """Save cache to file."""
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w") as file:
        json.dump(cache, file)

def fetch_weather_data(data: Union[dict, pd.DataFrame], cache, api_key, cache_file, max_workers=50):
    """
    Fetch weather data for a single location or multiple locations using OpenWeatherMap API with caching.
    
    Args:
        data (dict or pd.DataFrame): A single plant's data (dict) or a DataFrame of multiple plants.
        cache (dict): Cache for storing previously fetched weather data.
        api_key (str): OpenWeatherMap API key.
        cache_file (str): Path to the cache file.
        max_workers (int): Maximum number of threads for multi-threading.
    
    Returns:
        dict or list: Weather data for a single location (dict) or a list of weather data for multiple locations.
    """
    def fetch_single_weather(lat, lon):
        """Fetch weather data for a single location."""
        cache_key = f"{lat},{lon}"
        if cache_key in cache:
            return cache[cache_key]
        
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Extract cloud cover percentage from the API response
            cloud_cover = data.get("clouds", {}).get("all", 0)  # Cloud cover in percentage
            
            weather_data = {
                "temperature": data["main"].get("temp", 0),
                "wind_speed": data["wind"].get("speed", 0),
                "water_flow": data.get("rain", {}).get("1h", 0),  # Precipitation as proxy for hydropower
                "cloud_cover": cloud_cover  # Added cloud cover
            }
            
            cache[cache_key] = weather_data
            return weather_data
        except Exception as e:
            print(f"Error fetching weather data for {lat}, {lon}: {e}")
            return {"temperature": 0, "wind_speed": 0, "water_flow": 0, "cloud_cover": 0}

    if isinstance(data, dict):  # Single location
        return fetch_single_weather(data['y'], data['x'])
    elif isinstance(data, pd.DataFrame):  # Multiple locations
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            weather_data_list = list(executor.map(
                lambda plant: fetch_single_weather(plant['y'], plant['x']),
                [row[1] for row in data.iterrows()]
            ))
        save_cache(cache, cache_file)
        return weather_data_list
    else:
        raise ValueError("Invalid input: data must be a dict (single location) or a DataFrame (multiple locations).")

def estimate_energy_production(plant, weather):
    """
    Estimate energy output based on plant type and weather conditions using updated formulas.
    """
    capacity = plant["Capacity_Latest"]
    source = plant["PriEnergySource"]

    if source == "SUN":  # Solar power estimation
        # Updated solar power formula
        panel_efficiency = 0.22  # Typical solar panel efficiency (22%)
        temp_coeff = -0.004  # Efficiency loss per degree Celsius above 25°C
        age = plant.get("Age", 0)  # Age of the solar panel in years (default to 0 if not provided)
        soiling_loss = 0.05  # Loss due to dust and dirt accumulation (5%)

        # Irradiance (W/m^2) based on cloud cover
        irradiance = 1000 * (1 - weather.get("cloud_cover", 0) / 100)

        # Temperature effect
        cell_temp = weather["temperature"] + irradiance * 0.03  # Simplified cell temperature model
        temp_effect = 1 + temp_coeff * (cell_temp - 25)

        # Age degradation
        age_effect = 1 - age * 0.005

        # Soiling loss effect
        soiling_effect = 1 - soiling_loss

        # Solar power output calculation
        return max(0, capacity * panel_efficiency * irradiance / 1000 * temp_effect * age_effect * soiling_effect)

    elif source == "WND":  # Wind power estimation
        # Updated wind power formula
        turbine_diameter = plant.get("TurbineDiameter", 80)  # Default turbine diameter in meters
        hub_height = plant.get("HubHeight", 100)  # Default hub height in meters
        air_density = weather.get("air_density", 1.225)  # Air density in kg/m^3 (default to standard value)

        # Adjust wind speed for hub height using a logarithmic wind profile law
        wind_speed_hub = weather["wind_speed"] * (hub_height / 10) ** 0.14

        # Simplified power curve logic
        if wind_speed_hub < 3:  # Cut-in speed
            return 0
        elif wind_speed_hub > 15:  # Cut-out speed
            return capacity
        else:
            swept_area = (3.14159 * (turbine_diameter / 2) ** 2)  # Swept area of the turbine blades
            wind_power = (
                0.5 * air_density * swept_area * wind_speed_hub**3 / 1000
            )  # Power in kW
            return min(capacity, wind_power * 0.4)  # Apply power coefficient (Cp)

    elif source == "WAT":  # Hydropower estimation
        # Updated hydropower formula
        head = plant.get("Head", 50)  # Default head height in meters (if not provided)
        efficiency = plant.get("Efficiency", 0.9)  # Turbine efficiency (default to 90%)

        # Water flow rate in m^3/s (convert mm/h over a catchment area)
        flow_rate = weather["water_flow"] * (2.78e-7 * plant.get("CatchmentArea", 1e6))  

        g = 9.81  # Gravitational constant in m/s^2
        density = 1000  # Water density in kg/m^3

        hydro_power = efficiency * density * flow_rate * g * head / 1000  # Power in kW
        return min(capacity, hydro_power)

    else:
        return 0


def save_dataset_with_weather(data, weather_data_list, output_file):
    """Add weather data to dataset and save it."""
    # Create a copy to avoid modifying the original DataFrame
    result_data = data.copy()
    
    result_data["temperature"] = [weather["temperature"] for weather in weather_data_list]
    result_data["wind_speed"] = [weather["wind_speed"] for weather in weather_data_list]
    result_data["water_flow"] = [weather["water_flow"] for weather in weather_data_list]
    
    # Safely get cloud_cover, default to 0 if not present
    result_data["cloud_cover"] = [weather.get("cloud_cover", 0) for weather in weather_data_list]
    
    result_data["estimated_output"] = [estimate_energy_production(row[1], weather) 
                                    for row, weather in zip(result_data.iterrows(), weather_data_list)]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    result_data.to_csv(output_file, index=False)
    return output_file, result_data

def process_data(input_file, output_file, cache_file, api_key, force_refresh=False):
    """Process the data with weather information."""
    data = load_data(input_file)
    
    # Check if we need to fetch new data
    if force_refresh or not os.path.exists(output_file) or not os.path.exists(cache_file):
        print("Fetching new weather data...")
        cache = load_cache(cache_file)
        weather_data_list = fetch_weather_data(data, cache, api_key, cache_file)
        updated_filepath, updated_data = save_dataset_with_weather(data, weather_data_list, output_file)
        return updated_data
    else:
        print("Using existing weather data...")
        return load_data(output_file)