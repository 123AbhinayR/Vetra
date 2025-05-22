from flask import Blueprint, render_template, request, jsonify
from app.utils.data_handler import load_power_plants_data
from app.utils.energy_forecasting import EnergyForecaster
from config import Config
import logging

forecast_bp = Blueprint('forecast', __name__)

@forecast_bp.route('/forecast')
def forecast_dashboard():
    """Render the energy forecasting dashboard"""
    try:
        # Load power plants data for the dropdown
        plants_df = load_power_plants_data()
        
        # Get unique regions/counties for regional forecasting
        regions = sorted(plants_df['county'].unique()) if 'county' in plants_df.columns else []
        
        # Get sample plants for individual forecasting
        sample_plants = plants_df.head(50).to_dict('records') if not plants_df.empty else []
        
        return render_template('forecast.html', 
                             regions=regions, 
                             sample_plants=sample_plants)
    except Exception as e:
        logging.error(f"Error loading forecast dashboard: {e}")
        return render_template('error.html', error="Failed to load forecasting dashboard")

@forecast_bp.route('/api/forecast/plant', methods=['POST'])
def forecast_single_plant():
    """Generate forecast for a single power plant"""
    try:
        data = request.get_json()
        plant_id = data.get('plant_id')
        days = min(int(data.get('days', 3)), 5)  # Limit to 5 days max
        
        if not plant_id:
            return jsonify({'error': 'Plant ID is required'}), 400
        
        # Load plants data and find the specific plant
        plants_df = load_power_plants_data()
        plant_data = plants_df[plants_df.index == int(plant_id)].to_dict('records')
        
        if not plant_data:
            return jsonify({'error': 'Plant not found'}), 404
        
        # Initialize forecaster
        forecaster = EnergyForecaster(Config.OPENWEATHER_API_KEY)
        
        # Generate forecast
        forecast_result = forecaster.forecast_plant_production(plant_data[0], days)
        
        return jsonify(forecast_result)
        
    except ValueError as e:
        return jsonify({'error': 'Invalid input parameters'}), 400
    except Exception as e:
        logging.error(f"Error generating plant forecast: {e}")
        return jsonify({'error': 'Failed to generate forecast'}), 500

@forecast_bp.route('/api/forecast/region', methods=['POST'])
def forecast_regional():
    """Generate forecast for all plants in a region"""
    try:
        data = request.get_json()
        region_name = data.get('region')
        days = min(int(data.get('days', 3)), 5)
        max_plants = int(data.get('max_plants', 20))  # Limit for API quotas
        
        if not region_name:
            return jsonify({'error': 'Region name is required'}), 400
        
        # Load plants data and filter by region
        plants_df = load_power_plants_data()
        
        if 'county' in plants_df.columns:
            regional_plants = plants_df[plants_df['county'] == region_name]
        else:
            return jsonify({'error': 'County data not available'}), 400
        
        if regional_plants.empty:
            return jsonify({'error': f'No plants found in region: {region_name}'}), 404
        
        # Limit number of plants to avoid API quota issues
        if len(regional_plants) > max_plants:
            regional_plants = regional_plants.head(max_plants)
        
        plants_data = regional_plants.to_dict('records')
        
        # Initialize forecaster
        forecaster = EnergyForecaster(Config.OPENWEATHER_API_KEY)
        
        # Generate regional forecast
        forecast_result = forecaster.forecast_regional_production(plants_data, region_name, days)
        
        return jsonify(forecast_result)
        
    except ValueError as e:
        return jsonify({'error': 'Invalid input parameters'}), 400
    except Exception as e:
        logging.error(f"Error generating regional forecast: {e}")
        return jsonify({'error': 'Failed to generate regional forecast'}), 500

@forecast_bp.route('/api/forecast/fluctuation-alerts')
def get_fluctuation_alerts():
    """Get current fluctuation alerts for all active forecasts"""
    try:
        # This could be expanded to store and retrieve active forecasts
        # For now, return sample structure
        alerts = {
            'high_priority': [],
            'medium_priority': [],
            'last_updated': None
        }
        
        return jsonify(alerts)
        
    except Exception as e:
        logging.error(f"Error retrieving fluctuation alerts: {e}")
        return jsonify({'error': 'Failed to retrieve alerts'}), 500

@forecast_bp.route('/api/forecast/recommendations', methods=['POST'])
def get_energy_recommendations():
    """Get energy management recommendations based on forecast data"""
    try:
        data = request.get_json()
        forecast_data = data.get('forecast_data')
        
        if not forecast_data:
            return jsonify({'error': 'Forecast data is required'}), 400
        
        recommendations = []
        
        # Analyze forecast data and generate recommendations
        daily_summaries = forecast_data.get('daily_summaries', [])
        
        for day_summary in daily_summaries:
            variability = day_summary.get('variability', 0)
            peak_output = day_summary.get('peak_output_mw', 0)
            avg_output = day_summary.get('average_output_mw', 0)
            
            day_recommendations = []
            
            # High production day
            if peak_output > avg_output * 1.5:
                day_recommendations.append({
                    'type': 'high_production',
                    'message': 'Excellent conditions for energy production. Consider energy-intensive operations.',
                    'priority': 'medium'
                })
            
            # High variability
            if variability > avg_output * 0.3:
                day_recommendations.append({
                    'type': 'high_variability',
                    'message': 'High fluctuation expected. Ensure backup systems are ready.',
                    'priority': 'high'
                })
            
            # Low production
            if peak_output < avg_output * 0.7:
                day_recommendations.append({
                    'type': 'low_production',
                    'message': 'Lower than average production expected. Plan accordingly.',
                    'priority': 'medium'
                })
            
            if day_recommendations:
                recommendations.append({
                    'date': day_summary.get('date'),
                    'recommendations': day_recommendations
                })
        
        return jsonify({
            'recommendations': recommendations,
            'generated_at': forecast_data.get('generated_at')
        })
        
    except Exception as e:
        logging.error(f"Error generating recommendations: {e}")
        return jsonify({'error': 'Failed to generate recommendations'}), 500