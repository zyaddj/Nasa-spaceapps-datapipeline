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

from config import DataConfig, APIConfig

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
        Fetch OpenAQ measurements for all parameters
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bbox: [west, south, east, north]
            
        Returns:
            Path to saved Parquet file, or None if failed
        """
        
        logger.info("🏭 Fetching OpenAQ ground measurements")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Bounding box: {bbox}")
        logger.info(f"   Parameters: {self.config.OPENAQ_PARAMETERS}")
        
        all_measurements = []
        
        for parameter in self.config.OPENAQ_PARAMETERS:
            logger.info(f"  📊 Fetching {parameter.upper()} measurements...")
            
            try:
                measurements = self._fetch_parameter_data(parameter, start_date, end_date, bbox)
                all_measurements.extend(measurements)
                
                # Rate limiting
                time.sleep(self.api_config.OPENAQ_RATE_LIMIT)
                
                logger.info(f"     Retrieved {len(measurements)} {parameter} measurements")
                
            except Exception as e:
                logger.error(f"❌ Error fetching {parameter}: {e}")
        
        if not all_measurements:
            logger.warning("⚠️ No OpenAQ measurements retrieved")
            return None
        
        # Process and save data
        return self._process_and_save(all_measurements, start_date, end_date)
    
    def _fetch_parameter_data(self, parameter: str, start_date: str, end_date: str, bbox: List[float]) -> List[Dict]:
        """Fetch measurements for a specific parameter"""
        
        measurements = []
        page = 1
        limit = 10000
        max_pages = 10  # Prevent infinite loops
        
        while page <= max_pages:
            params = {
                'date_from': start_date,
                'date_to': end_date,
                'parameter': parameter,
                'coordinates': f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}",  # S,W,N,E format
                'limit': limit,
                'page': page,
                'sort': 'desc',
                'order_by': 'datetime'
            }
            
            try:
                response = requests.get(
                    f"{self.api_config.OPENAQ_BASE_URL}/measurements",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    break
                
                # Extract and standardize data
                for result in results:
                    try:
                        measurement = {
                            'datetime': result['date']['utc'],
                            'parameter': result['parameter'],
                            'value': float(result['value']),
                            'unit': result['unit'],
                            'latitude': float(result['coordinates']['latitude']),
                            'longitude': float(result['coordinates']['longitude']),
                            'location': result['location'],
                            'city': result.get('city', ''),
                            'country': result['country'],
                            'source_name': result.get('sourceName', ''),
                            'sensor_type': result.get('sensorType', 'reference'),
                            'data_source': 'OpenAQ'
                        }
                        measurements.append(measurement)
                        
                    except (ValueError, KeyError) as e:
                        # Skip invalid measurements
                        continue
                
                # Check pagination
                meta = data.get('meta', {})
                if page >= meta.get('pages', 1):
                    break
                    
                page += 1
                
            except requests.RequestException as e:
                logger.error(f"❌ API request failed for {parameter}, page {page}: {e}")
                break
        
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