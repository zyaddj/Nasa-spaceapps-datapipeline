# Configuration settings for DustIQ data pipeline

import os
from dataclasses import dataclass
from typing import List, Dict, Tuple
from datetime import datetime, timedelta

@dataclass
class DataConfig:
    """Configuration for data pipeline"""
    
    # Geographic bounds (North America)
    BBOX: Tuple[float, float, float, float] = (-130.0, 20.0, -60.0, 55.0)  # west, south, east, north
    
    # Grid resolution for unified dataset
    GRID_RESOLUTION: float = 0.125  # degrees (roughly 12.5km)
    
    # Date ranges
    DEFAULT_START_DATE: str = "2025-09-01"
    DEFAULT_END_DATE: str = "2025-10-05"
    
    # Data source configurations
    TEMPO_COLLECTIONS = {
        "NO2": "TEMPO_NO2_L2",
        "O3": "TEMPO_O3_L2", 
        "HCHO": "TEMPO_HCHO_L2",
        "AEROSOL": "TEMPO_AEROSOL_L2"
    }
    
    WEATHER_COLLECTIONS = {
        "NLDAS": "NLDAS_FORA0125_H",  # Preferred for North America
        "MERRA2": "M2T1NXSLV"         # Backup/global coverage
    }
    
    # OpenAQ parameters to fetch
    OPENAQ_PARAMETERS = ['pm25', 'pm10', 'no2', 'o3', 'so2', 'co']
    
    # Target output columns
    TARGET_COLUMNS = [
        'time', 'PM2.5', 'PM10', 'O3', 'NO2', 'SO2', 'CO',
        'temperature', 'humidity', 'wind_speed'
    ]
    
    # Data quality thresholds
    MAX_MISSING_RATIO = 0.3  # 30% max missing data
    MIN_RECORDS_PER_DAY = 12  # Minimum hourly records per day

@dataclass
class APIConfig:
    """API configuration and credentials"""
    
    # NASA Earthdata
    EARTHDATA_USERNAME: str = os.getenv('EARTHDATA_USERNAME', '')
    EARTHDATA_PASSWORD: str = os.getenv('EARTHDATA_PASSWORD', '')
    
    # LAADS DAAC (for VIIRS)
    LAADS_TOKEN: str = os.getenv('LAADS_TOKEN', '')
    LAADS_BASE_URL: str = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200"
    
    # OpenAQ
    OPENAQ_BASE_URL: str = "https://api.openaq.org/v2"
    OPENAQ_RATE_LIMIT: float = 1.0  # seconds between requests
    
    # File paths
    DATA_RAW_DIR: str = "data/raw"
    DATA_PROCESSED_DIR: str = "data/processed"

def get_date_range_from_env() -> Tuple[str, str]:
    """Get date range from environment variables"""
    start = os.getenv('START_DATE', DataConfig.DEFAULT_START_DATE)
    end = os.getenv('END_DATE', DataConfig.DEFAULT_END_DATE)
    return start, end

def get_bbox_from_env() -> List[float]:
    """Parse bounding box from environment"""
    bbox_str = os.getenv('BBOX', '-130,20,-60,55')
    return [float(x) for x in bbox_str.split(',')]

def validate_config() -> bool:
    """Validate configuration and credentials"""
    api_config = APIConfig()
    
    missing_creds = []
    
    if not api_config.EARTHDATA_USERNAME:
        missing_creds.append('EARTHDATA_USERNAME')
    if not api_config.EARTHDATA_PASSWORD:
        missing_creds.append('EARTHDATA_PASSWORD')
    if not api_config.LAADS_TOKEN:
        missing_creds.append('LAADS_TOKEN')
    
    if missing_creds:
        print(f"❌ Missing required credentials: {', '.join(missing_creds)}")
        print("Please check your .env file")
        return False
    
    print("✅ Configuration validated successfully")
    return True

if __name__ == "__main__":
    # Test configuration
    from dotenv import load_dotenv
    load_dotenv()
    
    config = DataConfig()
    api_config = APIConfig()
    
    print("📊 DustIQ Configuration:")
    print(f"   Bounding box: {config.BBOX}")
    print(f"   Grid resolution: {config.GRID_RESOLUTION}°")
    print(f"   Date range: {get_date_range_from_env()}")
    print(f"   Target columns: {len(config.TARGET_COLUMNS)} variables")
    
    validate_config()