import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Data directories
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "app" / "static"
GENERATED_DIR = STATIC_DIR / "generated"
IMG_DIR = STATIC_DIR / "img"

# Data files
CALIFORNIA_PLANTS_FILE = DATA_DIR / "california_power_plants.csv"
CALIFORNIA_PLANTS_WITH_WEATHER_FILE = DATA_DIR / "california_power_plants_with_weather.csv"
WEATHER_CACHE_FILE = DATA_DIR / "cache" / "weather_cache.json"

# API Configuration
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_api_key_here')

# Map Configuration
MAP_OUTPUT_FILE = GENERATED_DIR / "california_energy_map.html"

# Application Configuration
DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "cache").mkdir(exist_ok=True)

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'default',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['default']
    }
}