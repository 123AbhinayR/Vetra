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
    """Estimate energy output based on plant type and weather conditions."""
    capacity = plant["Capacity_Latest"]
    source = plant["PriEnergySource"]
    
    if source == "SUN":  # Solar power estimation
        temperature_effect = max(0, 1 - abs(25 - weather["temperature"]) * 0.005)
        cloud_factor = max(0, 1 - (weather.get("cloud_cover", 0) / 100))  # Safely get cloud_cover
        efficiency = 0.2
        return capacity * efficiency * temperature_effect * cloud_factor
    
    elif source == "WND":  # Wind power estimation (simplified)
        air_density = 1.225
        swept_area = 1000
        power_coefficient = 0.4
        wind_power = 0.5 * air_density * swept_area * (weather["wind_speed"] ** 3)
        return min(capacity, wind_power * power_coefficient / 1000)
    
    elif source == "WAT":  # Hydropower estimation (simplified)
        efficiency = 0.85  # Assumed efficiency
        return capacity * efficiency * (weather["water_flow"] / 100)
    
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