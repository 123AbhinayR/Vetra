import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
import os
import json
from typing import Union, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data(filepath):
    """Load the dataset of renewable energy plants."""
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        return pd.read_csv(filepath)
    except Exception as e:
        logger.error(f"Error loading data from {filepath}: {e}")
        raise

def load_cache(cache_file):
    """Load weather cache if available."""
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as file:
                return json.load(file)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading cache file {cache_file}: {e}")
    return {}

def save_cache(cache, cache_file):
    """Save cache to file."""
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as file:
            json.dump(cache, file)
    except Exception as e:
        logger.error(f"Error saving cache to {cache_file}: {e}")

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
        # Validate coordinates
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            logger.warning(f"Invalid coordinates: lat={lat}, lon={lon}")
            return {"temperature": 15, "wind_speed": 5, "water_flow": 0, "cloud_cover": 50}
        
        cache_key = f"{lat},{lon}"
        if cache_key in cache:
            return cache[cache_key]
        
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract cloud cover percentage from the API response
            cloud_cover = data.get("clouds", {}).get("all", 0)
            
            weather_data = {
                "temperature": data["main"].get("temp", 15),
                "wind_speed": data["wind"].get("speed", 5),
                "water_flow": data.get("rain", {}).get("1h", 0),
                "cloud_cover": cloud_cover
            }
            
            cache[cache_key] = weather_data
            return weather_data
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {lat}, {lon}: {e}")
            return {"temperature": 15, "wind_speed": 5, "water_flow": 0, "cloud_cover": 50}
        except Exception as e:
            logger.error(f"Error fetching weather data for {lat}, {lon}: {e}")
            return {"temperature": 15, "wind_speed": 5, "water_flow": 0, "cloud_cover": 50}

    if isinstance(data, dict):  # Single location
        return fetch_single_weather(data.get('y', 0), data.get('x', 0))
    elif isinstance(data, pd.DataFrame):  # Multiple locations
        # Validate required columns
        if 'x' not in data.columns or 'y' not in data.columns:
            raise ValueError("DataFrame must contain 'x' and 'y' columns for coordinates")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            weather_data_list = list(executor.map(
                lambda plant: fetch_single_weather(plant.get('y', 0), plant.get('x', 0)),
                [row[1].to_dict() for row in data.iterrows()]
            ))
        save_cache(cache, cache_file)
        return weather_data_list
    else:
        raise ValueError("Invalid input: data must be a dict (single location) or a DataFrame (multiple locations).")

def estimate_energy_production(plant, weather):
    """
    Estimate energy output based on plant type and weather conditions using updated formulas.
    """
    try:
        capacity = float(plant.get("Capacity_Latest", 0))
        if capacity <= 0:
            return 0
            
        source = plant.get("PriEnergySource", "").upper()

        if source == "SUN":  # Solar power estimation
            panel_efficiency = 0.22
            temp_coeff = -0.004
            age = float(plant.get("Age", 0))
            soiling_loss = 0.05

            cloud_cover = max(0, min(100, weather.get("cloud_cover", 0)))
            irradiance = 1000 * (1 - cloud_cover / 100)

            temperature = weather.get("temperature", 25)
            cell_temp = temperature + irradiance * 0.03
            temp_effect = 1 + temp_coeff * (cell_temp - 25)

            age_effect = max(0.5, 1 - age * 0.005)  # Prevent negative efficiency
            soiling_effect = 1 - soiling_loss

            output = capacity * panel_efficiency * irradiance / 1000 * temp_effect * age_effect * soiling_effect
            return max(0, min(capacity, output))

        elif source in ["WND", "WIND"]:  # Wind power estimation
            turbine_diameter = float(plant.get("TurbineDiameter", 80))
            hub_height = float(plant.get("HubHeight", 100))
            air_density = float(weather.get("air_density", 1.225))

            wind_speed_surface = max(0, weather.get("wind_speed", 0))
            if wind_speed_surface == 0:
                return 0
                
            # Adjust wind speed for hub height
            wind_speed_hub = wind_speed_surface * (hub_height / 10) ** 0.14

            # Wind power curve logic
            if wind_speed_hub < 3:  # Cut-in speed
                return 0
            elif wind_speed_hub > 25:  # Cut-out speed (safety)
                return 0
            elif wind_speed_hub > 15:  # Rated speed
                return capacity
            else:
                swept_area = 3.14159 * (turbine_diameter / 2) ** 2
                wind_power = 0.5 * air_density * swept_area * wind_speed_hub**3 / 1000
                return min(capacity, wind_power * 0.4)

        elif source in ["WAT", "WATER", "HYDRO"]:  # Hydropower estimation
            head = float(plant.get("Head", 50))
            efficiency = min(1.0, max(0.1, float(plant.get("Efficiency", 0.9))))
            
            water_flow_mm = weather.get("water_flow", 0)
            catchment_area = float(plant.get("CatchmentArea", 1e6))
            
            # Convert precipitation to flow rate
            flow_rate = water_flow_mm * (2.78e-7 * catchment_area)
            
            if flow_rate <= 0:
                return capacity * 0.3  # Minimum base flow assumption
                
            g = 9.81
            density = 1000
            
            hydro_power = efficiency * density * flow_rate * g * head / 1000
            return min(capacity, max(0, hydro_power))

        else:
            logger.warning(f"Unknown energy source: {source}")
            return 0
            
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating energy production: {e}")
        return 0

def save_dataset_with_weather(data, weather_data_list, output_file):
    """Add weather data to dataset and save it."""
    try:
        result_data = data.copy()
        
        # Ensure weather_data_list has the same length as data
        if len(weather_data_list) != len(result_data):
            logger.error(f"Mismatch: {len(weather_data_list)} weather records vs {len(result_data)} plants")
            return None, None
        
        result_data["temperature"] = [weather["temperature"] for weather in weather_data_list]
        result_data["wind_speed"] = [weather["wind_speed"] for weather in weather_data_list]
        result_data["water_flow"] = [weather["water_flow"] for weather in weather_data_list]
        result_data["cloud_cover"] = [weather.get("cloud_cover", 0) for weather in weather_data_list]
        
        # Calculate estimated output
        estimated_outputs = []
        for (idx, plant), weather in zip(result_data.iterrows(), weather_data_list):
            try:
                output = estimate_energy_production(plant.to_dict(), weather)
                estimated_outputs.append(output)
            except Exception as e:
                logger.error(f"Error calculating output for plant {idx}: {e}")
                estimated_outputs.append(0)
        
        result_data["estimated_output"] = estimated_outputs
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        result_data.to_csv(output_file, index=False)
        
        logger.info(f"Successfully saved dataset with weather data to {output_file}")
        return output_file, result_data
        
    except Exception as e:
        logger.error(f"Error saving dataset: {e}")
        return None, None

def process_data(input_file, output_file, cache_file, api_key, force_refresh=False):
    """Process the data with weather information."""
    try:
        # Use relative paths if absolute paths don't exist
        if not os.path.exists(input_file):
            # Try relative path
            relative_input = os.path.join("data", os.path.basename(input_file))
            if os.path.exists(relative_input):
                input_file = relative_input
            else:
                raise FileNotFoundError(f"Input file not found: {input_file}")
        
        data = load_data(input_file)
        
        # Validate required columns
        required_columns = ['x', 'y', 'PriEnergySource', 'Capacity_Latest']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Check if we need to fetch new data
        if force_refresh or not os.path.exists(output_file) or not os.path.exists(cache_file):
            logger.info("Fetching new weather data...")
            cache = load_cache(cache_file)
            weather_data_list = fetch_weather_data(data, cache, api_key, cache_file)
            
            result = save_dataset_with_weather(data, weather_data_list, output_file)
            if result[0] is None:
                logger.error("Failed to save dataset")
                return data  # Return original data as fallback
            
            return result[1]
        else:
            logger.info("Using existing weather data...")
            return load_data(output_file)
            
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        # Return a basic dataset as fallback
        try:
            return load_data(input_file)
        except:
            raise Exception(f"Critical error: Could not load any data from {input_file}")