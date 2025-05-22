import requests
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

class EnergyForecaster:
    """
    Handles predictive energy forecasting based on weather forecast data
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
        
    def get_weather_forecast(self, lat: float, lon: float, days: int = 3) -> Optional[Dict]:
        """
        Fetch weather forecast data for a specific location
        
        Args:
            lat: Latitude
            lon: Longitude 
            days: Number of days to forecast (max 5 for free tier)
            
        Returns:
            Dictionary containing forecast data or None if failed
        """
        try:
            # OpenWeatherMap 5-day forecast endpoint
            url = f"{self.base_url}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day (every 3 hours)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching forecast data: {e}")
            return None
    
    def calculate_solar_forecast(self, forecast_data: Dict, plant_capacity: float) -> List[Dict]:
        """
        Calculate predicted solar energy output based on weather forecast
        
        Args:
            forecast_data: Weather forecast data from API
            plant_capacity: Solar plant capacity in MW
            
        Returns:
            List of dictionaries with timestamp and predicted output
        """
        predictions = []
        
        for item in forecast_data.get('list', []):
            timestamp = datetime.fromtimestamp(item['dt'])
            
            # Extract weather parameters
            temp = item['main']['temp']  # Temperature in Celsius
            humidity = item['main']['humidity']  # Humidity percentage
            clouds = item['clouds']['all']  # Cloud coverage percentage
            
            # Calculate solar irradiance factor (0-1)
            # Base irradiance reduced by cloud coverage
            cloud_factor = max(0, (100 - clouds) / 100)
            
            # Temperature efficiency (solar panels are less efficient when hot)
            # Optimal temperature around 25°C
            temp_factor = max(0.6, 1 - (max(0, temp - 25) * 0.004))
            
            # Time of day factor (assuming peak sun hours)
            hour = timestamp.hour
            if 6 <= hour <= 18:  # Daylight hours
                time_factor = np.sin(np.pi * (hour - 6) / 12)  # Bell curve for sun intensity
            else:
                time_factor = 0
            
            # Combine factors for final prediction
            efficiency = cloud_factor * temp_factor * time_factor
            predicted_output = plant_capacity * efficiency
            
            predictions.append({
                'timestamp': timestamp,
                'predicted_output_mw': round(predicted_output, 2),
                'efficiency_factor': round(efficiency, 3),
                'weather_conditions': {
                    'temperature': temp,
                    'humidity': humidity,
                    'cloud_coverage': clouds
                }
            })
        
        return predictions
    
    def calculate_wind_forecast(self, forecast_data: Dict, plant_capacity: float) -> List[Dict]:
        """
        Calculate predicted wind energy output based on weather forecast
        
        Args:
            forecast_data: Weather forecast data from API
            plant_capacity: Wind plant capacity in MW
            
        Returns:
            List of dictionaries with timestamp and predicted output
        """
        predictions = []
        
        for item in forecast_data.get('list', []):
            timestamp = datetime.fromtimestamp(item['dt'])
            
            # Extract wind parameters
            wind_speed = item['wind']['speed']  # Wind speed in m/s
            
            # Wind power calculation using simplified power curve
            # Typical wind turbine cut-in: 3 m/s, rated: 12-15 m/s, cut-out: 25 m/s
            if wind_speed < 3:
                efficiency = 0
            elif wind_speed > 25:
                efficiency = 0  # Cut-out speed
            elif wind_speed <= 12:
                # Cubic relationship below rated speed
                efficiency = (wind_speed / 12) ** 3
            else:
                # Rated power between 12-25 m/s
                efficiency = 1
            
            predicted_output = plant_capacity * efficiency
            
            predictions.append({
                'timestamp': timestamp,
                'predicted_output_mw': round(predicted_output, 2),
                'efficiency_factor': round(efficiency, 3),
                'weather_conditions': {
                    'wind_speed': wind_speed,
                    'wind_direction': item['wind'].get('deg', 0)
                }
            })
        
        return predictions
    
    def calculate_hydro_forecast(self, forecast_data: Dict, plant_capacity: float) -> List[Dict]:
        """
        Calculate predicted hydro energy output based on weather forecast
        Note: Simplified model - real hydro prediction needs reservoir data
        
        Args:
            forecast_data: Weather forecast data from API
            plant_capacity: Hydro plant capacity in MW
            
        Returns:
            List of dictionaries with timestamp and predicted output
        """
        predictions = []
        
        for item in forecast_data.get('list', []):
            timestamp = datetime.fromtimestamp(item['dt'])
            
            # For hydro, we look at precipitation and temperature
            precipitation = item.get('rain', {}).get('3h', 0)  # 3-hour precipitation
            temp = item['main']['temp']
            
            # Simplified hydro model
            # Base efficiency (hydro plants typically run consistently)
            base_efficiency = 0.7
            
            # Precipitation boost (more water = more power potential)
            precip_boost = min(0.3, precipitation * 0.1)
            
            # Temperature effect (warmer = more snowmelt in mountains)
            temp_boost = max(0, (temp - 10) * 0.01) if temp > 10 else 0
            
            efficiency = min(1.0, base_efficiency + precip_boost + temp_boost)
            predicted_output = plant_capacity * efficiency
            
            predictions.append({
                'timestamp': timestamp,
                'predicted_output_mw': round(predicted_output, 2),
                'efficiency_factor': round(efficiency, 3),
                'weather_conditions': {
                    'precipitation': precipitation,
                    'temperature': temp
                }
            })
        
        return predictions
    
    def forecast_plant_production(self, plant_data: Dict, days: int = 3) -> Dict:
        """
        Generate comprehensive forecast for a single power plant
        
        Args:
            plant_data: Dictionary containing plant information
            days: Number of days to forecast
            
        Returns:
            Dictionary with forecast results
        """
        lat = plant_data.get('latitude')
        lon = plant_data.get('longitude')
        capacity = plant_data.get('total_power_mw', 0)
        energy_source = plant_data.get('energy_source', '').lower()
        
        if not all([lat, lon, capacity]):
            return {'error': 'Missing required plant data'}
        
        # Get weather forecast
        forecast_data = self.get_weather_forecast(lat, lon, days)
        if not forecast_data:
            return {'error': 'Failed to fetch weather forecast'}
        
        # Calculate predictions based on energy source
        if 'solar' in energy_source:
            predictions = self.calculate_solar_forecast(forecast_data, capacity)
        elif 'wind' in energy_source:
            predictions = self.calculate_wind_forecast(forecast_data, capacity)
        elif 'hydro' in energy_source or 'water' in energy_source:
            predictions = self.calculate_hydro_forecast(forecast_data, capacity)
        else:
            return {'error': f'Unsupported energy source: {energy_source}'}
        
        # Calculate daily summaries
        daily_summaries = self._calculate_daily_summaries(predictions)
        
        # Identify high fluctuation periods
        fluctuation_alerts = self._identify_fluctuations(predictions)
        
        return {
            'plant_name': plant_data.get('plant_name', 'Unknown'),
            'energy_source': energy_source,
            'capacity_mw': capacity,
            'forecast_period': f"{days} days",
            'hourly_predictions': predictions,
            'daily_summaries': daily_summaries,
            'fluctuation_alerts': fluctuation_alerts,
            'generated_at': datetime.now().isoformat()
        }
    
    def _calculate_daily_summaries(self, predictions: List[Dict]) -> List[Dict]:
        """Calculate daily summary statistics from hourly predictions"""
        daily_data = {}
        
        for pred in predictions:
            date = pred['timestamp'].date()
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(pred['predicted_output_mw'])
        
        summaries = []
        for date, outputs in daily_data.items():
            summaries.append({
                'date': date.isoformat(),
                'total_output_mwh': round(sum(outputs), 2),
                'average_output_mw': round(np.mean(outputs), 2),
                'peak_output_mw': round(max(outputs), 2),
                'min_output_mw': round(min(outputs), 2),
                'variability': round(np.std(outputs), 2)
            })
        
        return sorted(summaries, key=lambda x: x['date'])
    
    def _identify_fluctuations(self, predictions: List[Dict], threshold: float = 0.3) -> List[Dict]:
        """Identify periods with high output fluctuation"""
        alerts = []
        outputs = [p['predicted_output_mw'] for p in predictions]
        
        # Calculate rolling variability (6-hour windows)
        window_size = 6
        for i in range(len(outputs) - window_size + 1):
            window = outputs[i:i + window_size]
            variability = np.std(window) / (np.mean(window) + 0.1)  # Coefficient of variation
            
            if variability > threshold:
                alerts.append({
                    'start_time': predictions[i]['timestamp'].isoformat(),
                    'end_time': predictions[i + window_size - 1]['timestamp'].isoformat(),
                    'variability_score': round(variability, 3),
                    'severity': 'high' if variability > 0.5 else 'medium',
                    'recommendation': self._get_fluctuation_recommendation(variability)
                })
        
        return alerts
    
    def _get_fluctuation_recommendation(self, variability: float) -> str:
        """Generate recommendations based on fluctuation level"""
        if variability > 0.7:
            return "Consider activating backup power sources and energy storage systems"
        elif variability > 0.5:
            return "Monitor grid stability and prepare load balancing measures"
        else:
            return "Moderate fluctuation expected - standard grid management sufficient"
    
    def forecast_regional_production(self, plants_data: List[Dict], region_name: str, days: int = 3) -> Dict:
        """
        Generate forecast for multiple plants in a region
        
        Args:
            plants_data: List of plant dictionaries
            region_name: Name of the region
            days: Number of days to forecast
            
        Returns:
            Dictionary with regional forecast summary
        """
        regional_forecasts = []
        total_capacity = 0
        
        for plant in plants_data:
            forecast = self.forecast_plant_production(plant, days)
            if 'error' not in forecast:
                regional_forecasts.append(forecast)
                total_capacity += plant.get('total_power_mw', 0)
        
        if not regional_forecasts:
            return {'error': 'No successful forecasts generated'}
        
        # Aggregate regional data
        regional_summary = self._aggregate_regional_data(regional_forecasts, total_capacity)
        
        return {
            'region_name': region_name,
            'total_capacity_mw': total_capacity,
            'plant_count': len(regional_forecasts),
            'forecast_period': f"{days} days",
            'regional_summary': regional_summary,
            'individual_plants': regional_forecasts,
            'generated_at': datetime.now().isoformat()
        }
    
    def _aggregate_regional_data(self, forecasts: List[Dict], total_capacity: float) -> Dict:
        """Aggregate individual plant forecasts into regional summary"""
        # Combine all hourly predictions
        all_timestamps = set()
        for forecast in forecasts:
            for pred in forecast['hourly_predictions']:
                all_timestamps.add(pred['timestamp'])
        
        regional_hourly = []
        for timestamp in sorted(all_timestamps):
            total_output = 0
            plant_count = 0
            
            for forecast in forecasts:
                for pred in forecast['hourly_predictions']:
                    if pred['timestamp'] == timestamp:
                        total_output += pred['predicted_output_mw']
                        plant_count += 1
                        break
            
            regional_hourly.append({
                'timestamp': timestamp,
                'total_output_mw': round(total_output, 2),
                'capacity_utilization': round(total_output / total_capacity * 100, 1) if total_capacity > 0 else 0
            })
        
        # Calculate regional daily summaries
        daily_summaries = self._calculate_regional_daily_summaries(regional_hourly)
        
        return {
            'hourly_regional_output': regional_hourly,
            'daily_summaries': daily_summaries,
            'peak_regional_output': max([h['total_output_mw'] for h in regional_hourly]),
            'average_capacity_utilization': round(np.mean([h['capacity_utilization'] for h in regional_hourly]), 1)
        }
    
    def _calculate_regional_daily_summaries(self, hourly_data: List[Dict]) -> List[Dict]:
        """Calculate daily summaries for regional data"""
        daily_data = {}
        
        for item in hourly_data:
            date = item['timestamp'].date()
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(item['total_output_mw'])
        
        summaries = []
        for date, outputs in daily_data.items():
            summaries.append({
                'date': date.isoformat(),
                'total_production_mwh': round(sum(outputs), 2),
                'average_output_mw': round(np.mean(outputs), 2),
                'peak_output_mw': round(max(outputs), 2)
            })
        
        return sorted(summaries, key=lambda x: x['date'])