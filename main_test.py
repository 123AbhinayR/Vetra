import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests
from concurrent.futures import ThreadPoolExecutor
import os
import json
import uuid
from typing import Union, List  # Add this import for type annotations

# Load dataset
def load_data(filepath):
    """Load the filtered dataset of renewable energy plants."""
    return pd.read_csv(filepath)

# Cache file for storing previously fetched weather data
CACHE_FILE = "weather_cache.json"
API_KEY = ""  # Replace with your actual API key

# Load cache if available
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            return json.load(file)
    return {}

# Save cache to file
def save_cache(cache):
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file)

# Consolidated function for fetching weather data
def fetch_weather_data(data: Union[dict, pd.DataFrame], cache, max_workers=50):
    """
    Fetch weather data for a single location or multiple locations using OpenWeatherMap API with caching.
    
    Args:
        data (dict or pd.DataFrame): A single plant's data (dict) or a DataFrame of multiple plants.
        cache (dict): Cache for storing previously fetched weather data.
        max_workers (int): Maximum number of threads for multi-threading (used for multiple locations).
    
    Returns:
        dict or list: Weather data for a single location (dict) or a list of weather data for multiple locations.
    """
    def fetch_single_weather(lat, lon):
        """Fetch weather data for a single location."""
        cache_key = f"{lat},{lon}"
        if cache_key in cache:
            return cache[cache_key]
        
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
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
        save_cache(cache)
        return weather_data_list
    else:
        raise ValueError("Invalid input: data must be a dict (single location) or a DataFrame (multiple locations).")

# Energy production estimation
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

# Save dataset with weather data
def save_dataset_with_weather(data, weather_data_list):
    """Add weather data to dataset and save it."""
    data["temperature"] = [weather["temperature"] for weather in weather_data_list]
    data["wind_speed"] = [weather["wind_speed"] for weather in weather_data_list]
    data["water_flow"] = [weather["water_flow"] for weather in weather_data_list]
    
    # Safely get cloud_cover, default to 0 if not present
    data["cloud_cover"] = [weather.get("cloud_cover", 0) for weather in weather_data_list]
    
    data["estimated_output"] = [estimate_energy_production(row[1], weather) for row, weather in zip(data.iterrows(), weather_data_list)]
    output_file = "california_power_plants_with_weather.csv"
    data.to_csv(output_file, index=False)
    return output_file

# Create search control for the map
def create_search_control(data, energy_map):
    """Create a collapsible search control with clickable plant list."""
    with open("search_control.html", "r") as file:
        search_html = file.read()
    
    # Generate list items for each plant
    for i, (_, plant) in enumerate(data.iterrows()):
        plant_name = str(plant['PlantName'])
        source = plant['PriEnergySource']
        output = plant['estimated_output']
        lat = plant['y']
        lon = plant['x']
        
        search_html += f"""
        <li class="plant-item source-{source}" 
            onclick="zoomToPlant({lat}, {lon})" 
            data-name="{plant_name.lower()}" 
            data-source="{source}">
            {plant_name} ({source}) - {output:.1f} MW
        </li>
        """
    
    # Add JavaScript for collapsible functionality and search
    with open("search_control_script.js", "r") as script_file:
        search_script = script_file.read()
    search_html += """
        </ul>
    </div>
    <div class="search-toggle" id="searchToggle">☰</div>
    <script>
    """ + search_script + """
    </script>
    """
    
    # Add the search control to the map
    energy_map.get_root().html.add_child(folium.Element(search_html))

# Map generation with a search feature
def create_map(data):
    """Generate an interactive map with power plants in California using overlays and search feature."""
    # Initialize the map
    energy_map = folium.Map(location=[37.5, -119.5], zoom_start=6, control_scale=True, tiles="cartodbpositron")
    
    # Create feature groups for each power source type
    wind_group = folium.FeatureGroup(name="Wind Power", show=True).add_to(energy_map)
    solar_group = folium.FeatureGroup(name="Solar Power", show=True).add_to(energy_map)
    water_group = folium.FeatureGroup(name="Water Power", show=True).add_to(energy_map)
    
    # Add markers to the map with custom formatting
    for i, (_, plant) in enumerate(data.iterrows()):
        lat, lon = plant['y'], plant['x']
        energy_output = plant['estimated_output']
        plant_name = str(plant['PlantName'])  # Convert to string here as well
        
        weather_info = f"""
            <b>{plant_name}</b><br>
            Source: {plant['PriEnergySource']}<br>
            Estimated Output: {energy_output:.2f} MW<br>
            Capacity: {plant['Capacity_Latest']} MW<br>
            Wind Speed: {plant['wind_speed']} m/s<br>
            Water Flow: {plant['water_flow']} mm/h<br>
            Cloud Cover: {plant['cloud_cover']}%<br>
        """
        
        # Define marker color and opacity based on energy source
        color = "yellow" if plant["PriEnergySource"] == "SUN" else \
                "red" if plant["PriEnergySource"] == "WND" else "blue"
        opacity = 0.8
        
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=6,  # Marker size
            color="black",  # Border color
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            popup=weather_info,
            tooltip=plant_name  # Add tooltip for easier identification
        )
        
        # Add marker to the appropriate feature group
        if plant["PriEnergySource"] == "WND":
            marker.add_to(wind_group)
        elif plant["PriEnergySource"] == "SUN":
            marker.add_to(solar_group)
        elif plant["PriEnergySource"] == "WAT":
            marker.add_to(water_group)
    
    # Add search control to the map
    create_search_control(data, energy_map)
    
    # Add layer control with overlays only
    folium.LayerControl(collapsed=False).add_to(energy_map)
    
    # Use custom JavaScript to fix map reference issue
    map_fix_script = """
    <script>
    // Make map accessible to our zoom function
    document.addEventListener('DOMContentLoaded', function() {
        // Wait for Leaflet to initialize
        setTimeout(function() {
            // Find the map object and store it in window scope
            window.energyMap = Object.values(window).find(function(item) {
                return item && item._container && item._container.classList && 
                       item._container.classList.contains('leaflet-container');
            });
        }, 1000);
    });
    </script>
    """
    
    energy_map.get_root().html.add_child(folium.Element(map_fix_script))
    
    # Save the map
    energy_map.save("california_energy_map.html")
    print("Map saved as 'california_energy_map.html'")

# Main function
if __name__ == "__main__":
    filepath = "california_power_plants.csv"
    data = load_data(filepath)
    
    # Only fetch new weather data if no cache file exists
    if not os.path.exists(CACHE_FILE):
        print("No cache file found. Fetching new weather data...")
        cache = load_cache()
        weather_data_list = fetch_weather_data(data, cache)
        updated_filepath = save_dataset_with_weather(data, weather_data_list)
        updated_data = load_data(updated_filepath)
    else:
        print("Using existing weather data from cache...")
        # If we have cache but no processed data file, process the data
        if not os.path.exists("california_power_plants_with_weather.csv"):
            cache = load_cache()
            weather_data_list = [cache.get(f"{row[1]['y']},{row[1]['x']}", 
                                        {"temperature": 0, "wind_speed": 0, "water_flow": 0, "cloud_cover": 0}) 
                                for row in data.iterrows()]
            updated_filepath = save_dataset_with_weather(data, weather_data_list)
            updated_data = load_data(updated_filepath)
        else:
            print("Loading previously processed data...")
            updated_data = load_data("california_power_plants_with_weather.csv")
    
    if {'PlantName', 'y', 'x', 'PriEnergySource', 'Capacity_Latest'}.issubset(data.columns):
        create_map(updated_data)
    else:
        print("Error: Missing required columns in dataset.")