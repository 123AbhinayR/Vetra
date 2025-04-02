from flask import Flask
from config import Config
import datetime

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register blueprints
    from app.routes.main_routes import main_bp
    from app.routes.data_routes import data_bp
    from app.routes.map_routes import map_bp
    from app.routes.research_routes import research_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(research_bp)
    
    # Add context processor for current year
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.datetime.now().year}
    
    return app