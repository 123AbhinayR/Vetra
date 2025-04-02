from flask import Blueprint, render_template
import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the home page."""
    current_year = datetime.datetime.now().year
    return render_template('index.html', title='Home', current_year=current_year)