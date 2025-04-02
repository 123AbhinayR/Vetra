from flask import Blueprint, render_template, current_app, send_file, redirect, url_for
import os
from app.utils.data_handler import process_data
from app.utils.map_generator import create_map

map_bp = Blueprint('map', __name__, url_prefix='/map')

@map_bp.route('/')
def map_view():
    """Display the energy map."""
    # Define the output path for the map
    map_path = os.path.join(current_app.static_folder, 'generated', 'california_energy_map.html')
    
    # Make sure the directory exists
    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    
    # If the map doesn't exist, create it
    if not os.path.exists(map_path):
        try:
            data = process_data(
                current_app.config['POWER_PLANTS_FILE'],
                current_app.config['PROCESSED_DATA_FILE'],
                current_app.config['CACHE_FILE'],
                current_app.config['WEATHER_API_KEY']
            )
            create_map(data, map_path)
        except Exception as e:
            return render_template('map.html', title='Energy Map', error=str(e))
    
    return render_template('map.html', title='Energy Map')

@map_bp.route('/refresh')
def refresh_map():
    """Refresh the map data and regenerate the map."""
    try:
        # Define the output path for the map
        map_path = os.path.join(current_app.static_folder, 'generated', 'california_energy_map.html')
        
        # Force refresh the data
        data = process_data(
            current_app.config['POWER_PLANTS_FILE'],
            current_app.config['PROCESSED_DATA_FILE'],
            current_app.config['CACHE_FILE'],
            current_app.config['WEATHER_API_KEY'],
            force_refresh=True
        )
        
        # Regenerate the map
        create_map(data, map_path)
        
        return redirect(url_for('map.map_view'))
    except Exception as e:
        return render_template('map.html', title='Energy Map', error=str(e))