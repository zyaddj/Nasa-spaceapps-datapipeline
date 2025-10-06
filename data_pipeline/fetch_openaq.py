"""
OpenAQ Ground-Based Air Quality Data Fetcher
Downloads real-time ground sensor measurements for validation
"""

import os
import requests
import pandas as pd
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .config import DataConfig, APIConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAQFetcher:
    """Fetch ground-based air quality measurements from OpenAQ"""
    
    def __init__(self):
        self.config = DataConfig()
        self.api_config = APIConfig()
        
    def fetch_measurements(self, start_date: str, end_date: str, bbox: List[float]) -> Optional[str]:
        """
        Fetch OpenAQ measurements using v3 sensor-based approach
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bbox: [west, south, east, north]
            
        Returns:
            Path to saved Parquet file, or None if failed
        """
        
        logger.info("🏭 Fetching OpenAQ ground measurements (v3 sensor approach)")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Bounding box: {bbox}")
        
        # Step 1: Find locations in bounding box
        locations = self._fetch_locations_in_bbox(bbox)
        if not locations:
            logger.warning("⚠️ No OpenAQ locations found in bounding box")
            return None
        
        logger.info(f"   Found {len(locations)} locations")
        
        # Step 2: Extract sensors and fetch hourly data
        all_measurements = []
        for location in locations:
            location_measurements = self._fetch_location_sensors_data(location, start_date, end_date)
            all_measurements.extend(location_measurements)
            time.sleep(self.api_config.OPENAQ_RATE_LIMIT)
        
        if not all_measurements:
            logger.warning("⚠️ No OpenAQ measurements retrieved")
            return None
        
        logger.info(f"   Retrieved {len(all_measurements)} total measurements")
        
        # Process and save data
        return self._process_and_save(all_measurements, start_date, end_date)
    
    def _fetch_locations_in_bbox(self, bbox: List[float]) -> List[Dict]:
        """Fetch locations within bounding box using v3 API"""
        
        try:
            params = {
                'bbox': f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",  # west,south,east,north
                'limit': 100,  # Get more locations
                'page': 1
            }
            
            headers = {'X-API-Key': self.api_config.OPENAQ_API_KEY} if self.api_config.OPENAQ_API_KEY else {}
            
            response = requests.get(
                f"{self.api_config.OPENAQ_BASE_URL}/locations",
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            locations = data.get('results', [])
            
            # Filter for locations with sensors we want
            target_params = set(self.config.OPENAQ_PARAMETERS)
            filtered_locations = []
            
            for location in locations:
                sensors = location.get('sensors', [])
                location_params = set()
                for sensor in sensors:
                    param_name = sensor.get('parameter', {}).get('name', '')
                    if param_name in target_params:
                        location_params.add(param_name)
                
                if location_params:  # Has at least one parameter we want
                    location['target_sensors'] = [
                        s for s in sensors 
                        if s.get('parameter', {}).get('name', '') in target_params
                    ]
                    filtered_locations.append(location)
            
            logger.info(f"   Filtered to {len(filtered_locations)} locations with target parameters")
            return filtered_locations
            
        except Exception as e:
            logger.error(f"❌ Error fetching locations: {e}")
            return []
    
    def _fetch_location_sensors_data(self, location: Dict, start_date: str, end_date: str) -> List[Dict]:
        """Fetch hourly data for all target sensors at a location"""
        
        measurements = []
        location_name = location.get('name', 'Unknown')
        coords = location.get('coordinates', {})
        lat = coords.get('latitude')
        lon = coords.get('longitude')
        
        # Convert dates to ISO format with timezone
        start_iso = f"{start_date}T00:00:00Z"
        end_iso = f"{end_date}T23:59:59Z"
        
        for sensor in location.get('target_sensors', []):
            sensor_id = sensor.get('id')
            param_info = sensor.get('parameter', {})
            param_name = param_info.get('name', '')
            
            if not sensor_id:
                continue
                
            try:
                # Fetch hourly data for this sensor
                params = {
                    'datetime_from': start_iso,
                    'datetime_to': end_iso,
                    'limit': 500  # Get many hours
                }
                
                headers = {'X-API-Key': self.api_config.OPENAQ_API_KEY} if self.api_config.OPENAQ_API_KEY else {}
                
                response = requests.get(
                    f"{self.api_config.OPENAQ_BASE_URL}/sensors/{sensor_id}/hours",
                    params=params,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning(f"   Sensor {sensor_id} ({param_name}) HTTP {response.status_code}")
                    continue
                
                data = response.json()
                hourly_results = data.get('results', [])
                
                # Convert to our format
                for result in hourly_results:
                    try:
                        period = result.get('period', {})
                        datetime_from = period.get('datetimeFrom', {}).get('utc')
                        
                        measurement = {
                            'datetime': datetime_from,
                            'parameter': param_name,
                            'value': float(result.get('value', 0)),
                            'unit': param_info.get('units', ''),
                            'latitude': lat,
                            'longitude': lon,
                            'location': location_name,
                            'city': location.get('locality', ''),
                            'country': location.get('country', {}).get('name', ''),
                            'source_name': 'OpenAQ_v3',
                            'sensor_type': 'reference',
                            'data_source': 'OpenAQ',
                            'sensor_id': sensor_id
                        }
                        measurements.append(measurement)
                        
                    except (ValueError, KeyError) as e:
                        continue
                
                logger.info(f"     {location_name} {param_name}: {len(hourly_results)} hours")
                
            except Exception as e:
                logger.warning(f"   Error fetching sensor {sensor_id}: {e}")
                continue
        
        return measurements
        
        return measurements
    
    def _process_and_save(self, measurements: List[Dict], start_date: str, end_date: str) -> str:
        """Process measurements and save to Parquet"""
        
        logger.info(f"📊 Processing {len(measurements)} total measurements")
        
        # Convert to DataFrame
        df = pd.DataFrame(measurements)
        
        if df.empty:
            logger.warning("⚠️ No valid measurements to process")
            return None
        
        # Data cleaning and standardization
        df = self._clean_measurements(df)
        
        # Create output directory
        output_dir = Path(self.api_config.DATA_RAW_DIR) / "openaq"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as Parquet
        output_file = output_dir / f"openaq_{start_date}_to_{end_date}.parquet"
        df.to_parquet(output_file, engine='pyarrow', index=False)
        
        logger.info(f"✅ Saved {len(df)} cleaned measurements to {output_file}")
        
        # Print summary statistics
        self._print_summary(df)
        
        return str(output_file)
    
    def _clean_measurements(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize OpenAQ measurements"""
        
        logger.info("🧹 Cleaning measurement data...")
        
        initial_count = len(df)
        
        # Convert datetime
        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        df = df.dropna(subset=['datetime'])
        
        # Remove invalid values
        df = df[df['value'] >= 0]
        df = df[df['value'].notna()]
        
        # Remove extreme outliers (simple method)
        for param in df['parameter'].unique():
            param_mask = df['parameter'] == param
            param_data = df[param_mask]['value']
            
            # Remove values beyond 99.9th percentile (likely errors)
            upper_threshold = param_data.quantile(0.999)
            df = df[~(param_mask & (df['value'] > upper_threshold))]
        
        # Standardize parameter names
        parameter_mapping = {
            'pm25': 'PM2.5',
            'pm10': 'PM10',
            'no2': 'NO2',
            'o3': 'O3',
            'so2': 'SO2',
            'co': 'CO'
        }
        df['parameter'] = df['parameter'].map(parameter_mapping).fillna(df['parameter'])
        
        # Add grid cell assignment for spatial joining
        df['lat_grid'] = (df['latitude'] / self.config.GRID_RESOLUTION).round() * self.config.GRID_RESOLUTION
        df['lon_grid'] = (df['longitude'] / self.config.GRID_RESOLUTION).round() * self.config.GRID_RESOLUTION
        
        # Add date partition column
        df['date'] = df['datetime'].dt.date
        
        final_count = len(df)
        logger.info(f"   Cleaned data: {initial_count} → {final_count} measurements ({final_count/initial_count*100:.1f}% retained)")
        
        return df
    
    def _print_summary(self, df: pd.DataFrame):
        """Print summary statistics"""
        
        logger.info("📈 OpenAQ Data Summary:")
        logger.info(f"   Total measurements: {len(df):,}")
        logger.info(f"   Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        logger.info(f"   Parameters: {list(df['parameter'].unique())}")
        logger.info(f"   Unique locations: {df['location'].nunique()}")
        logger.info(f"   Countries: {list(df['country'].unique())}")
        
        # Parameter counts
        param_counts = df['parameter'].value_counts()
        for param, count in param_counts.items():
            logger.info(f"     {param}: {count:,} measurements")

def main():
    """Test OpenAQ fetcher"""
    try:
        # Initialize fetcher
        fetcher = OpenAQFetcher()
        
        # Test parameters (small sample)
        start_date = "2025-10-01"
        end_date = "2025-10-03"
        bbox = [-125, 35, -105, 45]  # Smaller test area
        
        # Fetch data
        output_file = fetcher.fetch_measurements(start_date, end_date, bbox)
        
        if output_file:
            # Load and inspect results
            df = pd.read_parquet(output_file)
            logger.info(f"✅ Test successful! Generated file with {len(df)} records")
            logger.info(f"   File location: {output_file}")
            
            # Show sample data
            print("\n📋 Sample data:")
            print(df.head())
            
        else:
            logger.error("❌ Test failed - no data retrieved")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()