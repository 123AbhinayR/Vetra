import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import folium
from folium import plugins
import warnings
warnings.filterwarnings('ignore')

class SmartAgricultureEnergyMapper:
    def __init__(self, api_key: str):
        """
        Initialize the Smart Agriculture Energy Mapper
        
        Args:
            api_key: OpenWeatherMap API key for weather data
        """
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
        self.forecast_url = "http://api.openweathermap.org/data/2.5/forecast"
        
        # Agriculture-energy compatibility matrix
        self.crop_energy_compatibility = {
            'irrigation': {
                'solar': {'min_solar_hours': 6, 'efficiency_factor': 0.85},
                'wind': {'min_wind_speed': 3, 'efficiency_factor': 0.7}
            },
            'greenhouse': {
                'solar': {'min_solar_hours': 4, 'efficiency_factor': 0.9},
                'wind': {'min_wind_speed': 4, 'efficiency_factor': 0.6}
            },
            'crop_drying': {
                'solar': {'min_solar_hours': 7, 'efficiency_factor': 0.95},
                'wind': {'min_wind_speed': 5, 'efficiency_factor': 0.8}
            }
        }
        
    def get_current_weather(self, lat: float, lon: float) -> Dict:
        """Get current weather data for a location"""
        url = f"{self.base_url}/weather"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching weather data: {e}")
            return {}
    
    def get_weather_forecast(self, lat: float, lon: float, days: int = 3) -> List[Dict]:
        """Get weather forecast for next 3 days"""
        url = self.forecast_url
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Filter to get next 3 days (8 forecasts per day, every 3 hours)
            forecasts = data['list'][:days * 8]
            return forecasts
        except requests.RequestException as e:
            print(f"Error fetching forecast data: {e}")
            return []
    
    def calculate_solar_potential(self, weather_data: Dict, capacity_kw: float) -> Dict:
        """Calculate solar energy potential based on weather conditions"""
        if not weather_data:
            return {'potential_kwh': 0, 'efficiency': 0, 'cloud_impact': 0}
        
        # Base calculations
        cloud_coverage = weather_data.get('clouds', {}).get('all', 0) / 100
        visibility = weather_data.get('visibility', 10000) / 10000  # Normalize visibility
        
        # Solar efficiency factors
        cloud_efficiency = 1 - (cloud_coverage * 0.7)  # Clouds reduce efficiency by up to 70%
        visibility_efficiency = min(visibility, 1.0)
        
        # Assume peak sun hours based on cloud coverage
        base_sun_hours = 8  # Average daily sun hours
        effective_sun_hours = base_sun_hours * cloud_efficiency
        
        # Calculate potential daily output
        potential_kwh = capacity_kw * effective_sun_hours * visibility_efficiency
        overall_efficiency = cloud_efficiency * visibility_efficiency
        
        return {
            'potential_kwh': round(potential_kwh, 2),
            'efficiency': round(overall_efficiency * 100, 1),
            'cloud_impact': round(cloud_coverage * 100, 1),
            'effective_sun_hours': round(effective_sun_hours, 1)
        }
    
    def calculate_wind_potential(self, weather_data: Dict, capacity_kw: float) -> Dict:
        """Calculate wind energy potential based on weather conditions"""
        if not weather_data:
            return {'potential_kwh': 0, 'efficiency': 0, 'wind_class': 'Poor'}
        
        wind_speed = weather_data.get('wind', {}).get('speed', 0)  # m/s
        
        # Wind power calculation (simplified)
        # Power = 0.5 * air_density * area * wind_speed^3 * efficiency
        # Simplified: assume efficiency curve based on wind speed
        
        if wind_speed < 3:
            efficiency = 0
            wind_class = 'Poor'
        elif wind_speed < 6:
            efficiency = 0.3
            wind_class = 'Fair'
        elif wind_speed < 10:
            efficiency = 0.7
            wind_class = 'Good'
        elif wind_speed < 15:
            efficiency = 0.9
            wind_class = 'Excellent'
        else:
            efficiency = 0.8  # Reduced due to safety cutoffs
            wind_class = 'High Wind'
        
        # Calculate daily potential (24 hours)
        potential_kwh = capacity_kw * 24 * efficiency
        
        return {
            'potential_kwh': round(potential_kwh, 2),
            'efficiency': round(efficiency * 100, 1),
            'wind_speed': wind_speed,
            'wind_class': wind_class
        }
    
    def assess_agriculture_suitability(self, lat: float, lon: float, 
                                    energy_type: str, use_case: str) -> Dict:
        """Assess suitability for agricultural energy applications"""
        weather = self.get_current_weather(lat, lon)
        
        if not weather:
            return {'suitability': 'Unknown', 'score': 0, 'recommendations': []}
        
        compatibility = self.crop_energy_compatibility.get(use_case, {}).get(energy_type, {})
        
        if energy_type == 'solar':
            # Calculate solar hours from cloud coverage
            cloud_coverage = weather.get('clouds', {}).get('all', 0) / 100
            estimated_solar_hours = 8 * (1 - cloud_coverage * 0.7)
            
            min_required = compatibility.get('min_solar_hours', 6)
            score = min(estimated_solar_hours / min_required, 1.0) * 100
            
        elif energy_type == 'wind':
            wind_speed = weather.get('wind', {}).get('speed', 0)
            min_required = compatibility.get('min_wind_speed', 3)
            score = min(wind_speed / min_required, 1.0) * 100
        
        else:
            score = 0
        
        # Determine suitability level
        if score >= 80:
            suitability = 'Excellent'
        elif score >= 60:
            suitability = 'Good'
        elif score >= 40:
            suitability = 'Fair'
        else:
            suitability = 'Poor'
        
        # Generate recommendations
        recommendations = self._generate_agriculture_recommendations(
            weather, energy_type, use_case, score
        )
        
        return {
            'suitability': suitability,
            'score': round(score, 1),
            'recommendations': recommendations,
            'weather_conditions': {
                'temperature': weather.get('main', {}).get('temp', 0),
                'humidity': weather.get('main', {}).get('humidity', 0),
                'wind_speed': weather.get('wind', {}).get('speed', 0),
                'cloud_coverage': weather.get('clouds', {}).get('all', 0)
            }
        }
    
    def _generate_agriculture_recommendations(self, weather: Dict, 
                                           energy_type: str, use_case: str, 
                                           score: float) -> List[str]:
        """Generate specific recommendations for agricultural energy use"""
        recommendations = []
        
        temp = weather.get('main', {}).get('temp', 20)
        humidity = weather.get('main', {}).get('humidity', 50)
        wind_speed = weather.get('wind', {}).get('speed', 0)
        cloud_coverage = weather.get('clouds', {}).get('all', 0)
        
        if energy_type == 'solar':
            if cloud_coverage > 70:
                recommendations.append("Consider battery storage due to high cloud coverage")
            if use_case == 'irrigation' and temp > 30:
                recommendations.append("Ideal conditions for solar irrigation - high water demand period")
            if use_case == 'greenhouse' and temp < 10:
                recommendations.append("Solar heating most beneficial during cold periods")
                
        elif energy_type == 'wind':
            if wind_speed > 8:
                recommendations.append("Excellent wind conditions for continuous operation")
            if use_case == 'crop_drying' and humidity > 80:
                recommendations.append("Wind power ideal for crop drying in high humidity")
        
        if score > 80:
            recommendations.append("Consider expanding renewable capacity")
        elif score < 40:
            recommendations.append("Consider hybrid renewable system")
            
        return recommendations
    
    def predict_energy_forecast(self, lat: float, lon: float, 
                              capacity_kw: float, energy_type: str) -> List[Dict]:
        """Predict energy output for next 3 days"""
        forecasts = self.get_weather_forecast(lat, lon)
        predictions = []
        
        for forecast in forecasts:
            timestamp = datetime.fromtimestamp(forecast['dt'])
            
            if energy_type == 'solar':
                potential = self.calculate_solar_potential(forecast, capacity_kw)
            elif energy_type == 'wind':
                potential = self.calculate_wind_potential(forecast, capacity_kw)
            else:
                potential = {'potential_kwh': 0, 'efficiency': 0}
            
            predictions.append({
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M'),
                'day': timestamp.strftime('%A'),
                'hour': timestamp.hour,
                **potential,
                'weather': {
                    'temp': forecast.get('main', {}).get('temp'),
                    'description': forecast.get('weather', [{}])[0].get('description', ''),
                    'wind_speed': forecast.get('wind', {}).get('speed', 0),
                    'clouds': forecast.get('clouds', {}).get('all', 0)
                }
            })
        
        return predictions
    
    def create_agriculture_energy_map(self, plants_df: pd.DataFrame) -> folium.Map:
        """Create interactive map with agriculture energy zones"""
        
        # Center map on data
        center_lat = plants_df['latitude'].mean()
        center_lon = plants_df['longitude'].mean()
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8,
            tiles='OpenStreetMap'
        )
        
        # Add custom tile layers
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Create feature groups for different layers
        solar_group = folium.FeatureGroup(name='Solar Plants')
        wind_group = folium.FeatureGroup(name='Wind Plants')
        agriculture_zones = folium.FeatureGroup(name='Agriculture Energy Zones')
        forecast_group = folium.FeatureGroup(name='3-Day Forecast')
        
        # Process each plant
        for idx, plant in plants_df.iterrows():
            lat, lon = plant['latitude'], plant['longitude']
            capacity = plant.get('capacity_kw', plant.get('capacity_mw', 0))
            if 'capacity_mw' in plant:
                capacity *= 1000  # Convert MW to kW
            
            energy_type = self._determine_energy_type(plant)
            
            # Get current conditions and agriculture assessment
            weather = self.get_current_weather(lat, lon)
            
            if energy_type == 'solar':
                potential = self.calculate_solar_potential(weather, capacity)
                color = 'orange'
                icon = 'sun'
            elif energy_type == 'wind':
                potential = self.calculate_wind_potential(weather, capacity)
                color = 'blue'
                icon = 'leaf'
            else:
                potential = {'potential_kwh': 0, 'efficiency': 0}
                color = 'gray'
                icon = 'flash'
            
            # Agriculture suitability assessment
            irrigation_suit = self.assess_agriculture_suitability(lat, lon, energy_type, 'irrigation')
            greenhouse_suit = self.assess_agriculture_suitability(lat, lon, energy_type, 'greenhouse')
            
            # Create detailed popup
            popup_html = f"""
            <div style="width:300px;">
                <h4>{plant.get('owner', 'Unknown')} - {energy_type.title()} Plant</h4>
                <p><b>Capacity:</b> {capacity:,.0f} kW</p>
                <p><b>Status:</b> {plant.get('status', 'Unknown')}</p>
                <p><b>Current Output Potential:</b> {potential['potential_kwh']:,.1f} kWh/day</p>
                <p><b>Efficiency:</b> {potential['efficiency']}%</p>
                
                <hr>
                <h5>🌾 Agriculture Energy Potential</h5>
                <p><b>Irrigation Support:</b> {irrigation_suit['suitability']} ({irrigation_suit['score']}%)</p>
                <p><b>Greenhouse Support:</b> {greenhouse_suit['suitability']} ({greenhouse_suit['score']}%)</p>
                
                <hr>
                <h5>📋 Recommendations</h5>
                <ul>
            """
            
            for rec in irrigation_suit['recommendations'][:3]:  # Limit to 3 recommendations
                popup_html += f"<li>{rec}</li>"
            
            popup_html += """
                </ul>
                <p><small>Click for detailed forecast</small></p>
            </div>
            """
            
            # Main plant marker
            marker = folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{plant.get('owner', 'Plant')} - {potential['potential_kwh']:,.0f} kWh/day",
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            )
            
            if energy_type == 'solar':
                solar_group.add_child(marker)
            elif energy_type == 'wind':
                wind_group.add_child(marker)
            
            # Add agriculture zone circle based on suitability
            max_suitability = max(irrigation_suit['score'], greenhouse_suit['score'])
            if max_suitability > 60:  # Only show zones with good potential
                zone_color = 'green' if max_suitability > 80 else 'yellow'
                folium.Circle(
                    [lat, lon],
                    radius=2000,  # 2km radius
                    popup=f"Agriculture Energy Zone - Score: {max_suitability:.1f}%",
                    color=zone_color,
                    fillColor=zone_color,
                    fillOpacity=0.2,
                    weight=2
                ).add_to(agriculture_zones)
        
        # Add all groups to map
        solar_group.add_to(m)
        wind_group.add_to(m)
        agriculture_zones.add_to(m)
        forecast_group.add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 140px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>Legend</h4>
        <p><i class="fa fa-sun" style="color:orange"></i> Solar Plants</p>
        <p><i class="fa fa-leaf" style="color:blue"></i> Wind Plants</p>
        <p><span style="color:green">●</span> High Agriculture Potential</p>
        <p><span style="color:yellow">●</span> Moderate Agriculture Potential</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def _determine_energy_type(self, plant_row) -> str:
        """Determine energy type from plant data"""
        # This is a simplified version - you might have a specific field for this
        owner = str(plant_row.get('owner', '')).lower()
        if 'solar' in owner or 'sun' in owner:
            return 'solar'
        elif 'wind' in owner:
            return 'wind'
        else:
            # Default to solar if unclear
            return 'solar'
    
    def generate_forecast_report(self, plants_df: pd.DataFrame, 
                               output_file: str = 'energy_forecast_report.html'):
        """Generate comprehensive forecast report"""
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>3-Day Energy Forecast Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .plant-section { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; }
                .forecast-table { width: 100%; border-collapse: collapse; }
                .forecast-table th, .forecast-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                .forecast-table th { background-color: #f2f2f2; }
                .high-output { background-color: #d4edda; }
                .low-output { background-color: #f8d7da; }
                .recommendations { background-color: #e2f3ff; padding: 10px; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>🌾 Smart Agriculture Energy Forecast Report</h1>
            <p>Generated on: """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """</p>
        """
        
        for idx, plant in plants_df.iterrows():
            if idx >= 5:  # Limit to first 5 plants for demo
                break
                
            lat, lon = plant['latitude'], plant['longitude']
            capacity = plant.get('capacity_kw', plant.get('capacity_mw', 0))
            if 'capacity_mw' in plant:
                capacity *= 1000
            
            energy_type = self._determine_energy_type(plant)
            predictions = self.predict_energy_forecast(lat, lon, capacity, energy_type)
            
            html_content += f"""
            <div class="plant-section">
                <h2>{plant.get('owner', 'Unknown Plant')} - {energy_type.title()}</h2>
                <p><strong>Capacity:</strong> {capacity:,.0f} kW | <strong>Location:</strong> {plant.get('county', 'Unknown')}</p>
                
                <table class="forecast-table">
                    <tr>
                        <th>Date/Time</th>
                        <th>Predicted Output (kWh)</th>
                        <th>Efficiency (%)</th>
                        <th>Weather</th>
                        <th>Agriculture Impact</th>
                    </tr>
            """
            
            for pred in predictions[:24]:  # Show first 24 hours
                output_class = 'high-output' if pred.get('efficiency', 0) > 70 else ('low-output' if pred.get('efficiency', 0) < 30 else '')
                
                html_content += f"""
                    <tr class="{output_class}">
                        <td>{pred['timestamp']}</td>
                        <td>{pred.get('potential_kwh', 0):,.1f}</td>
                        <td>{pred.get('efficiency', 0):.1f}%</td>
                        <td>{pred['weather']['description']}</td>
                        <td>{'Excellent for irrigation' if pred.get('efficiency', 0) > 70 else 'Limited capacity'}</td>
                    </tr>
                """
            
            html_content += """
                </table>
                <div class="recommendations">
                    <h4>💡 Agricultural Recommendations:</h4>
                    <ul>
                        <li>Peak output periods ideal for energy-intensive operations</li>
                        <li>Schedule irrigation during high-efficiency hours</li>
                        <li>Consider battery storage for consistent agricultural power</li>
                    </ul>
                </div>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        return output_file

# Example usage function
def main():
    """
    Example usage of the Smart Agriculture Energy Mapper
    """
    # Initialize with your OpenWeatherMap API key
    API_KEY = "your_openweathermap_api_key_here"
    
    mapper = SmartAgricultureEnergyMapper(API_KEY)
    
    # Load your existing plant data
    # plants_df = pd.read_csv('data/california_power_plants.csv')
    
    # Example plant data structure
    sample_plants = pd.DataFrame({
        'latitude': [37.4419, 37.7749, 34.0522],
        'longitude': [-122.1430, -122.4194, -118.2437],
        'capacity_kw': [1000, 2500, 1500],
        'owner': ['Solar Farm A', 'Wind Power Co', 'Green Energy LLC'],
        'status': ['Operating', 'Operating', 'Proposed'],
        'county': ['Santa Clara', 'San Francisco', 'Los Angeles']
    })
    
    # Create agriculture energy map
    agri_map = mapper.create_agriculture_energy_map(sample_plants)
    agri_map.save('smart_agriculture_energy_map.html')
    
    # Generate forecast report
    report_file = mapper.generate_forecast_report(sample_plants)
    
    print(f"Agriculture Energy Map saved as: smart_agriculture_energy_map.html")
    print(f"Forecast Report saved as: {report_file}")
    
    # Example of individual assessments
    lat, lon = 37.4419, -122.1430  # Example coordinates
    
    # Assess agriculture suitability
    irrigation_assessment = mapper.assess_agriculture_suitability(lat, lon, 'solar', 'irrigation')
    print(f"\nIrrigation Suitability: {irrigation_assessment}")
    
    # Get 3-day forecast
    forecast = mapper.predict_energy_forecast(lat, lon, 1000, 'solar')
    print(f"\n3-Day Forecast (first 6 hours):")
    for pred in forecast[:6]:
        print(f"  {pred['timestamp']}: {pred['potential_kwh']:.1f} kWh ({pred['efficiency']:.1f}%)")

if __name__ == "__main__":
    main()