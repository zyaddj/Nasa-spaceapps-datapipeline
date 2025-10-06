"""
Weather Data Fetcher
Downloads NLDAS and MERRA-2 weather data via NASA Earthdata
"""

import os
import earthaccess
import xarray as xr
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .config import DataConfig, APIConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherFetcher:
    """Fetch weather data from NLDAS and MERRA-2 via earthaccess"""
    
    def __init__(self):
        self.config = DataConfig()
        self.api_config = APIConfig()
        self.authenticated = False
        
        # Weather data collections
        self.collections = {
            # NLDAS hourly forcing data (higher resolution for North America)
            "NLDAS": {
                "short_name": "NLDAS_FORA0125_H",
                "variables": ["TMP", "SPFH", "UGRD", "VGRD", "PRES", "DLWRF", "DSWRF", "APCP"],
                "description": "NLDAS Hourly 0.125° North America"
            },
            
            # MERRA-2 (global, good for boundary conditions)
            "MERRA2": {
                "short_name": "M2T1NXSLV",
                "variables": ["T2M", "QV2M", "U10M", "V10M", "PS", "PBLH"],
                "description": "MERRA-2 Hourly Single-Level"
            }
        }
    
    def authenticate(self) -> bool:
        """Authenticate with NASA Earthdata"""
        try:
            earthaccess.login()
            self.authenticated = True
            logger.info("✅ Authenticated with NASA Earthdata for weather data")
            return True
        except Exception as e:
            logger.error(f"❌ Weather data authentication failed: {e}")
            return False
    
    def fetch_weather_data(self, collection: str, start_date: str, end_date: str, bbox: List[float]) -> List[str]:
        """
        Fetch weather data from specified collection
        
        Args:
            collection: 'NLDAS' or 'MERRA2'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bbox: [west, south, east, north]
            
        Returns:
            List of downloaded file paths
        """
        
        if not self.authenticated:
            if not self.authenticate():
                return []
        
        if collection not in self.collections:
            logger.error(f"Unknown weather collection: {collection}")
            return []
        
        collection_info = self.collections[collection]
        short_name = collection_info["short_name"]
        
        logger.info(f"🌬️ Fetching {collection} weather data")
        logger.info(f"   Collection: {short_name}")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Bounding box: {bbox}")
        
        try:
            # Search for granules
            # Ensure bbox is proper tuple (west, south, east, north)
            if len(bbox) != 4:
                raise ValueError(f"Bounding box must have 4 elements, got {bbox}")
            bbox_tuple = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))

            results = earthaccess.search_data(
                short_name=short_name,
                temporal=(start_date, end_date),
                bounding_box=bbox_tuple
            )
            
            logger.info(f"Found {len(results)} {collection} granules")
            
            if not results:
                logger.warning(f"No {collection} data found for specified period")
                return []
            
            # Create output directory
            output_dir = Path(self.api_config.DATA_RAW_DIR) / "weather" / collection.lower()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Cap number of granules to avoid huge downloads (one per 3 hours approx)
            MAX_GRANULES = 60
            if len(results) > MAX_GRANULES:
                logger.info(f"   Capping weather granules {len(results)} → {MAX_GRANULES}")
                results = results[:MAX_GRANULES]

            logger.info(f"Downloading {len(results)} granules to {output_dir}")
            downloaded_files = earthaccess.download(results, local_path=str(output_dir))
            
            # Filter successful downloads
            valid_files = [str(f) for f in downloaded_files if f and os.path.exists(f)]
            
            logger.info(f"✅ Downloaded {len(valid_files)} {collection} files")
            return valid_files
            
        except Exception as e:
            logger.error(f"❌ Error fetching {collection} data: {e}")
            return []
    
    def fetch_nldas_data(self, start_date: str, end_date: str, bbox: List[float]) -> List[str]:
        """Fetch NLDAS hourly forcing data (preferred for North America)"""
        return self.fetch_weather_data("NLDAS", start_date, end_date, bbox)
    
    def fetch_merra2_data(self, start_date: str, end_date: str, bbox: List[float]) -> List[str]:
        """Fetch MERRA-2 hourly data (global coverage)"""
        return self.fetch_weather_data("MERRA2", start_date, end_date, bbox)
    
    def fetch_all_weather_sources(self, start_date: str, end_date: str, bbox: List[float]) -> Dict[str, List[str]]:
        """
        Fetch from multiple weather sources
        
        Returns:
            Dictionary mapping source names to file lists
        """
        
        logger.info("🌍 Starting comprehensive weather data fetch")
        
        all_files = {}
        
        # Try NLDAS first (higher resolution for North America)
        logger.info("\n1️⃣ Fetching NLDAS data...")
        try:
            nldas_files = self.fetch_nldas_data(start_date, end_date, bbox)
            all_files['NLDAS'] = nldas_files
            
            if nldas_files:
                logger.info(f"✅ NLDAS: {len(nldas_files)} files")
            else:
                logger.warning("⚠️ NLDAS: No files downloaded")
                
        except Exception as e:
            logger.error(f"❌ NLDAS fetch failed: {e}")
            all_files['NLDAS'] = []
        
        # Also get MERRA-2 for backup/additional variables
        logger.info("\n2️⃣ Fetching MERRA-2 data...")
        try:
            merra2_files = self.fetch_merra2_data(start_date, end_date, bbox)
            all_files['MERRA2'] = merra2_files
            
            if merra2_files:
                logger.info(f"✅ MERRA-2: {len(merra2_files)} files")
            else:
                logger.warning("⚠️ MERRA-2: No files downloaded")
                
        except Exception as e:
            logger.error(f"❌ MERRA-2 fetch failed: {e}")
            all_files['MERRA2'] = []
        
        total_files = sum(len(files) for files in all_files.values())
        logger.info(f"\n🎯 Weather fetch complete: {total_files} total files")
        
        return all_files
    
    def extract_weather_variables(self, file_path: str) -> Optional[Dict]:
        """
        Extract key weather variables from downloaded file
        
        Returns:
            Dictionary with extracted variables or None if failed
        """
        
        try:
            # Open dataset
            ds = xr.open_dataset(file_path)
            
            extracted = {}
            
            # Temperature (convert from Kelvin if needed)
            temp_vars = ['TMP', 'T2M', 'temperature', 'temp']
            for var_name in temp_vars:
                if var_name in ds.variables:
                    temp_data = ds[var_name]
                    # Convert K to C if values are in Kelvin range
                    if temp_data.values.mean() > 100:  # Likely Kelvin
                        temp_data = temp_data - 273.15
                    extracted['temperature'] = temp_data
                    break
            
            # Humidity
            humidity_vars = ['SPFH', 'QV2M', 'RH2M', 'humidity', 'rh']
            for var_name in humidity_vars:
                if var_name in ds.variables:
                    hum_data = ds[var_name]
                    # Convert to percentage if needed
                    if hum_data.values.max() <= 1:  # Likely fraction
                        hum_data = hum_data * 100
                    extracted['humidity'] = hum_data
                    break
            
            # Wind components
            u_vars = ['UGRD', 'U10M', 'u_wind', 'u10']
            v_vars = ['VGRD', 'V10M', 'v_wind', 'v10']
            
            u_wind = v_wind = None
            
            for var_name in u_vars:
                if var_name in ds.variables:
                    u_wind = ds[var_name]
                    break
                    
            for var_name in v_vars:
                if var_name in ds.variables:
                    v_wind = ds[var_name]
                    break
            
            if u_wind is not None and v_wind is not None:
                # Calculate wind speed
                import numpy as np
                wind_speed = np.sqrt(u_wind**2 + v_wind**2)
                extracted['wind_speed'] = wind_speed
                extracted['wind_u'] = u_wind
                extracted['wind_v'] = v_wind
            
            # Surface pressure
            pressure_vars = ['PRES', 'PS', 'pressure', 'slp']
            for var_name in pressure_vars:
                if var_name in ds.variables:
                    extracted['pressure'] = ds[var_name]
                    break
            
            ds.close()
            return extracted
            
        except Exception as e:
            logger.error(f"❌ Error extracting variables from {file_path}: {e}")
            return None

def main():
    """Test weather fetcher"""
    try:
        # Load environment
        from dotenv import load_dotenv
        load_dotenv()
        
        # Initialize fetcher
        fetcher = WeatherFetcher()
        
        # Test parameters (small sample)
        start_date = "2025-10-01"
        end_date = "2025-10-02"
        bbox = [-125, 35, -105, 45]  # Smaller test area
        
        logger.info("🧪 Testing weather data fetch...")
        
        # Test NLDAS first
        nldas_files = fetcher.fetch_nldas_data(start_date, end_date, bbox)
        
        if nldas_files:
            logger.info(f"✅ Test successful! Downloaded {len(nldas_files)} NLDAS files")
            logger.info(f"   First file: {nldas_files[0]}")
            
            # Test variable extraction
            if nldas_files:
                variables = fetcher.extract_weather_variables(nldas_files[0])
                if variables:
                    logger.info(f"   Extracted variables: {list(variables.keys())}")
        else:
            logger.warning("⚠️ Test completed but no NLDAS files downloaded")
            logger.info("   This may be normal - weather data availability varies")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()