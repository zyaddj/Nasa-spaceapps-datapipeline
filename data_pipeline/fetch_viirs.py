"""
NOAA VIIRS Deep Blue Data Fetcher
Downloads VIIRS AERDB_D3_VIIRS_NOAA20 daily aerosol data from LAADS DAAC
"""

import os
import requests
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .config import DataConfig, APIConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VIIRSFetcher:
    """Download NOAA VIIRS Deep Blue aerosol data from LAADS DAAC"""
    
    def __init__(self):
        self.config = DataConfig()
        self.api_config = APIConfig()
        
        if not self.api_config.LAADS_TOKEN:
            raise ValueError("LAADS_TOKEN not found in environment variables")
            
        # LAADS DAAC URLs
        self.base_url = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200"
        self.collection = "AERDB_D3_VIIRS_NOAA20"  # VIIRS Deep Blue Daily L3
        
    def fetch_viirs_aod(self, start_date: str, end_date: str) -> List[str]:
        """
        Download VIIRS Deep Blue daily AOD data
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of downloaded file paths
        """
        
        logger.info(f"🌍 Fetching VIIRS Deep Blue AOD data")
        logger.info(f"   Date range: {start_date} to {end_date}")
        logger.info(f"   Collection: {self.collection}")
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        downloaded_files = []
        current_date = start_dt
        
        while current_date <= end_dt:
            try:
                daily_files = self._fetch_daily_viirs(current_date)
                downloaded_files.extend(daily_files)
                
            except Exception as e:
                logger.warning(f"❌ Failed to fetch {current_date.strftime('%Y-%m-%d')}: {e}")
                
            current_date += timedelta(days=1)
        
        logger.info(f"✅ Downloaded {len(downloaded_files)} VIIRS files")
        return downloaded_files
    
    def _fetch_daily_viirs(self, date: datetime) -> List[str]:
        """Fetch VIIRS data for a specific day"""
        
        year = date.year
        day_of_year = date.timetuple().tm_yday
        
        # LAADS directory structure: /collection/YYYY/DOY/
        day_url = f"{self.base_url}/{self.collection}/{year}/{day_of_year:03d}/"
        
        logger.info(f"   Fetching {date.strftime('%Y-%m-%d')} (DOY {day_of_year:03d})")
        
        # Create output directory
        output_dir = Path(self.api_config.DATA_RAW_DIR) / "viirs" / str(year) / f"{day_of_year:03d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get file listing
        files = self._get_file_list(day_url)
        
        downloaded_files = []
        for filename in files:
            if self._is_relevant_file(filename):
                file_path = self._download_file(day_url, filename, output_dir)
                if file_path:
                    downloaded_files.append(file_path)
        
        return downloaded_files
    
    def _get_file_list(self, directory_url: str) -> List[str]:
        """Get list of files in LAADS directory"""
        
        headers = {
            'Authorization': f'Bearer {self.api_config.LAADS_TOKEN}',
            'User-Agent': 'DustIQ-NASA-SpaceApps/1.0'
        }
        
        try:
            response = requests.get(directory_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML to extract .nc files
            import re
            file_pattern = r'href="([^"]*\.nc)"'
            files = re.findall(file_pattern, response.text)
            
            return files
            
        except requests.RequestException as e:
            logger.error(f"❌ Failed to get file list from {directory_url}: {e}")
            return []
    
    def _is_relevant_file(self, filename: str) -> bool:
        """Check if file is relevant for our needs"""
        
        # Look for Deep Blue AOD files
        relevant_patterns = [
            'AERDB_D3_VIIRS_NOAA20',  # Main collection
            '.nc'  # NetCDF format
        ]
        
        return all(pattern in filename for pattern in relevant_patterns)
    
    def _download_file(self, base_url: str, filename: str, output_dir: Path) -> Optional[str]:
        """Download a single file"""
        
        file_url = f"{base_url}{filename}"
        local_path = output_dir / filename
        
        # Skip if file already exists
        if local_path.exists():
            logger.info(f"     ⏭️ Skipping existing: {filename}")
            return str(local_path)
        
        headers = {
            'Authorization': f'Bearer {self.api_config.LAADS_TOKEN}',
            'User-Agent': 'DustIQ-NASA-SpaceApps/1.0'
        }
        
        try:
            logger.info(f"     ⬇️ Downloading: {filename}")
            
            response = requests.get(file_url, headers=headers, stream=True, timeout=300)
            response.raise_for_status()
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            
            with open(local_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Simple progress indicator
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Every MB
                                logger.info(f"       Progress: {progress:.1f}%")
            
            logger.info(f"     ✅ Downloaded: {filename} ({downloaded/1024/1024:.1f} MB)")
            return str(local_path)
            
        except requests.RequestException as e:
            logger.error(f"     ❌ Download failed for {filename}: {e}")
            # Clean up partial file
            if local_path.exists():
                local_path.unlink()
            return None
    
    def get_available_dates(self, year: int) -> List[str]:
        """Get list of available dates for a given year"""
        
        year_url = f"{self.base_url}/{self.collection}/{year}/"
        headers = {
            'Authorization': f'Bearer {self.api_config.LAADS_TOKEN}',
            'User-Agent': 'DustIQ-NASA-SpaceApps/1.0'
        }
        
        try:
            response = requests.get(year_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse directory listing for day-of-year folders
            import re
            day_pattern = r'href="(\d{3})/"'
            days = re.findall(day_pattern, response.text)
            
            # Convert DOY to dates
            available_dates = []
            for doy in days:
                try:
                    date = datetime.strptime(f"{year}-{doy}", "%Y-%j")
                    available_dates.append(date.strftime("%Y-%m-%d"))
                except ValueError:
                    continue
            
            return sorted(available_dates)
            
        except requests.RequestException as e:
            logger.error(f"❌ Failed to get available dates for {year}: {e}")
            return []

def main():
    """Test VIIRS fetcher"""
    try:
        # Load environment
        from dotenv import load_dotenv
        load_dotenv()
        
        # Initialize fetcher
        fetcher = VIIRSFetcher()
        
        # Test parameters (small sample)
        start_date = "2025-10-01"
        end_date = "2025-10-02"
        
        logger.info("🧪 Testing VIIRS AOD fetch...")
        files = fetcher.fetch_viirs_aod(start_date, end_date)
        
        if files:
            logger.info(f"✅ Test successful! Downloaded {len(files)} VIIRS files")
            logger.info(f"   First file: {files[0]}")
        else:
            logger.warning("⚠️ Test completed but no files were downloaded")
            logger.info("   This may be normal - VIIRS data availability varies")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()