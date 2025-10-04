"""
TEMPO Satellite Data Fetcher
Downloads TEMPO L2 hourly data for NO2, O3, HCHO, and Aerosol Index
"""

import os
import earthaccess
from typing import List, Dict
from datetime import datetime, timedelta
from pathlib import Path
import logging

from config import DataConfig, APIConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TEMPOFetcher:
    """Download TEMPO L2 hourly data using earthaccess"""
    
    def __init__(self):
        self.config = DataConfig()
        self.api_config = APIConfig()
        self.authenticated = False
        
    def authenticate(self) -> bool:
        """Authenticate with NASA Earthdata"""
        try:
            earthaccess.login()
            self.authenticated = True
            logger.info("✅ Authenticated with NASA Earthdata")
            return True
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def fetch_tempo_variable(self, variable: str, start_date: str, end_date: str, bbox: List[float]) -> List[str]:
        """
        Download TEMPO data for a specific variable
        
        Args:
            variable: One of ['NO2', 'O3', 'HCHO', 'AEROSOL']
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bbox: [west, south, east, north]
            
        Returns:
            List of downloaded file paths
        """
        
        if not self.authenticated:
            if not self.authenticate():
                return []
        
        if variable not in self.config.TEMPO_COLLECTIONS:
            logger.error(f"Unknown TEMPO variable: {variable}")
            return []
        
        collection_name = self.config.TEMPO_COLLECTIONS[variable]
        logger.info(f"🛰️ Fetching TEMPO {variable} data ({collection_name})")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Bounding box: {bbox}")
        
        try:
            # Search for granules
            results = earthaccess.search_data(
                short_name=collection_name,
                temporal=(start_date, end_date),
                bounding_box=bbox
            )
            
            logger.info(f"Found {len(results)} TEMPO {variable} granules")
            
            if not results:
                logger.warning(f"No TEMPO {variable} data found for specified period")
                return []
            
            # Create output directory
            output_dir = Path(self.api_config.DATA_RAW_DIR) / "tempo" / variable.lower()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Download files
            logger.info(f"Downloading to {output_dir}")
            downloaded_files = earthaccess.download(
                results,
                local_path=str(output_dir),
                provider="LARC"  # TEMPO is hosted at LaRC
            )
            
            # Filter successful downloads
            valid_files = [str(f) for f in downloaded_files if f and os.path.exists(f)]
            
            logger.info(f"✅ Downloaded {len(valid_files)} TEMPO {variable} files")
            return valid_files
            
        except Exception as e:
            logger.error(f"❌ Error fetching TEMPO {variable}: {e}")
            return []
    
    def fetch_all_tempo_variables(self, start_date: str, end_date: str, bbox: List[float]) -> Dict[str, List[str]]:
        """
        Fetch all TEMPO variables for the specified period
        
        Returns:
            Dictionary mapping variable names to file lists
        """
        
        logger.info("🌟 Starting comprehensive TEMPO data fetch")
        
        all_files = {}
        
        for variable in self.config.TEMPO_COLLECTIONS.keys():
            try:
                files = self.fetch_tempo_variable(variable, start_date, end_date, bbox)
                all_files[variable] = files
                
                if files:
                    logger.info(f"✅ {variable}: {len(files)} files")
                else:
                    logger.warning(f"⚠️ {variable}: No files downloaded")
                    
            except Exception as e:
                logger.error(f"❌ Failed to fetch {variable}: {e}")
                all_files[variable] = []
        
        total_files = sum(len(files) for files in all_files.values())
        logger.info(f"🎯 TEMPO fetch complete: {total_files} total files")
        
        return all_files

def main():
    """Test TEMPO fetcher"""
    try:
        # Load environment
        from dotenv import load_dotenv
        load_dotenv()
        
        # Initialize fetcher
        fetcher = TEMPOFetcher()
        
        # Test parameters (small sample)
        start_date = "2025-10-01"
        end_date = "2025-10-02"
        bbox = [-125, 35, -105, 45]  # Smaller test area
        
        # Test single variable first
        logger.info("🧪 Testing TEMPO NO2 fetch...")
        no2_files = fetcher.fetch_tempo_variable("NO2", start_date, end_date, bbox)
        
        if no2_files:
            logger.info(f"✅ Test successful! Downloaded {len(no2_files)} NO2 files")
            logger.info(f"   First file: {no2_files[0]}")
        else:
            logger.error("❌ Test failed - no files downloaded")
            
    except ImportError:
        logger.error("❌ Missing python-dotenv. Install with: pip install python-dotenv")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()