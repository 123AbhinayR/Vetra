from flask import Blueprint, render_template, current_app
import pandas as pd
from app.utils.data_handler import load_data

data_bp = Blueprint('data', __name__, url_prefix='/data')

@data_bp.route('/')
def data_view():
    """Display the power plant data in a table."""
    try:
        # Load the processed data file if it exists, otherwise load the original
        try:
            data = load_data(current_app.config['PROCESSED_DATA_FILE'])
        except:
            data = load_data(current_app.config['POWER_PLANTS_FILE'])
        
        # Convert the DataFrame to HTML for displaying in the template
        # Add responsive table classes and ensure no index is shown
        html_table = data.to_html(
            classes=['table', 'table-striped', 'table-hover'], 
            border=0, 
            index=False, 
            table_id='data-table',
            justify='left'
        )
        
        return render_template('data.html', title='Data', 
                               table=html_table)
    except Exception as e:
        return render_template('data.html', title='Data', 
                               error=f"Error loading data: {str(e)}")