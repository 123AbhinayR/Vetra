from flask import Blueprint, render_template

research_bp = Blueprint('research', __name__, url_prefix='/research')

@research_bp.route('/')
def research_view():
    """Display the research page (empty for now)."""
    return render_template('research.html', title='Research')

@research_bp.route('/analysis')
def analysis_view():
    """Display the analysis page (empty for now)."""
    return render_template('analysis.html', title='Analysis')