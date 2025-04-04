import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    WEATHER_API_KEY = "2ccf2e0f94a8c0e9ea2aa1042"
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    CACHE_FILE = os.path.join(DATA_DIR, 'weather_cache.json')
    POWER_PLANTS_FILE = os.path.join(DATA_DIR, 'california_power_plants.csv')
    PROCESSED_DATA_FILE = os.path.join(DATA_DIR, 'california_power_plants_with_weather.csv')