"""
DustIQ Data Unification Pipeline
Combines TEMPO, VIIRS, Weather, and Ground data into unified format:
time,PM2.5,PM10,O3,NO2,SO2,CO,temperature,humidity,wind_speed
"""

import pandas as pd
import xarray as xr
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple
import os

from .config import DataConfig, APIConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DustIQDataUnifier:
    """Unify all data sources into target format"""
    
    def __init__(self):
        self.config = DataConfig()
        self.api_config = APIConfig()
        
    def unify_all_sources(self, data_sources: Dict) -> pd.DataFrame:
        """
        Main function: Combine all data sources into unified DataFrame
        
        Args:
            data_sources: Dictionary with keys 'TEMPO', 'VIIRS', 'WEATHER', 'GROUND'
                         containing file paths from data fetchers
            
        Returns:
            DataFrame with columns: time,PM2.5,PM10,O3,NO2,SO2,CO,temperature,humidity,wind_speed
        """
        
        logger.info("🔄 Starting data unification process...")
        logger.info(f"   Target format: {self.config.TARGET_COLUMNS}")
        
        # Process each data source
        ground_data = self._process_ground_data(data_sources.get('GROUND', {}))
        tempo_data = self._process_tempo_data(data_sources.get('TEMPO', {}))
        weather_data = self._process_weather_data(data_sources.get('WEATHER', {}))
        viirs_data = self._process_viirs_data(data_sources.get('VIIRS', {}))
        
        # Merge all sources (grid-level)
        unified_grid = self._merge_all_sources(ground_data, tempo_data, weather_data, viirs_data)

        # Build continuous hourly scaffold for past week (UTC)
        scaffold = self._build_hourly_scaffold()

        if unified_grid.empty:
            logger.warning("⚠️ No grid-level data merged; returning scaffold with NaNs")
            return scaffold

        # Aggregate spatial grid cells → single hourly mean
        aggregated = self._aggregate_spatial(unified_grid)

        # Join scaffold to guarantee continuity
        aggregated_full = scaffold.merge(aggregated, on='time', how='left')

        # Final processing
        final_data = self._finalize_dataset(aggregated_full, already_aggregated=True)
        
        logger.info(f"✅ Unification complete: {len(final_data)} records")
        return final_data
    
    def _process_ground_data(self, ground_files: Dict) -> pd.DataFrame:
        """Process OpenAQ ground measurements"""
        
        logger.info("📍 Processing ground sensor data...")
        
        openaq_file = ground_files.get('OpenAQ')
        if not openaq_file or not Path(openaq_file).exists():
            logger.warning("⚠️ No OpenAQ data file found")
            return pd.DataFrame()
        
        try:
            # Load OpenAQ data
            df = pd.read_parquet(openaq_file)
            logger.info(f"   Loaded {len(df)} OpenAQ measurements")
            
            # Pivot pollutants to columns
            ground_pivot = df.pivot_table(
                index=['datetime', 'lat_grid', 'lon_grid'],
                columns='parameter',
                values='value',
                aggfunc='mean'  # Average multiple sensors in same grid cell
            ).reset_index()
            
            # Rename to match target format
            column_mapping = {
                'datetime': 'time',
                'PM2.5': 'PM2.5',
                'PM10': 'PM10',
                'O3': 'O3', 
                'NO2': 'NO2',
                'SO2': 'SO2',
                'CO': 'CO'
            }
            
            ground_pivot = ground_pivot.rename(columns=column_mapping)
            ground_pivot['data_source'] = 'ground'
            
            logger.info(f"   Processed to {len(ground_pivot)} grid-time records")
            return ground_pivot
            
        except Exception as e:
            logger.error(f"❌ Error processing ground data: {e}")
            return pd.DataFrame()
    
    def _process_tempo_data(self, tempo_files: Dict) -> pd.DataFrame:
        """Process TEMPO satellite data"""
        
        logger.info("🛰️ Processing TEMPO satellite data...")
        
        if not tempo_files:
            logger.warning("⚠️ No TEMPO files found")
            return pd.DataFrame()
        
        tempo_data = []
        
        for variable, files in tempo_files.items():
            if not files:
                continue
                
            logger.info(f"   Processing TEMPO {variable}...")
            
            for file_path in files:
                if not Path(file_path).exists():
                    continue
                # Skip obviously tiny/corrupt files (<5 KB)
                try:
                    if os.path.getsize(file_path) < 5_000:
                        logger.warning(f"   Skipping tiny file {file_path}")
                        continue
                except OSError:
                    continue
                ds = self._open_dataset_resilient(file_path)
                if ds is None:
                    continue
                try:
                    var_data = self._extract_tempo_variable(ds, variable)
                    if var_data is not None:
                        df_temp = self._netcdf_to_dataframe(var_data, variable)
                        if not df_temp.empty:
                            tempo_data.append(df_temp)
                except Exception as e:
                    logger.warning(f"   ⚠️ Processing failed {file_path}: {e}")
                finally:
                    try:
                        ds.close()
                    except Exception:
                        pass
        
        if tempo_data:
            # Combine all TEMPO data
            tempo_df = pd.concat(tempo_data, ignore_index=True)
            
            # Regrid to common grid
            tempo_df = self._regrid_to_common_grid(tempo_df)
            
            # Pivot variables to columns
            tempo_pivot = tempo_df.pivot_table(
                index=['time', 'lat_grid', 'lon_grid'],
                columns='variable',
                values='value',
                aggfunc='mean'
            ).reset_index()
            
            tempo_pivot['data_source'] = 'tempo'
            
            logger.info(f"   Processed {len(tempo_pivot)} TEMPO grid-time records")
            return tempo_pivot
        
        return pd.DataFrame()
    
    def _process_weather_data(self, weather_files: Dict) -> pd.DataFrame:
        """Process weather data (NLDAS/MERRA-2)"""
        
        logger.info("🌬️ Processing weather data...")
        
        if not weather_files:
            logger.warning("⚠️ No weather files found")
            return pd.DataFrame()
        
        weather_data = []
        
        # Process NLDAS first (preferred for North America)
        nldas_files = weather_files.get('NLDAS', [])
        merra2_files = weather_files.get('MERRA2', [])
        
        all_weather_files = nldas_files + merra2_files
        
        for file_path in all_weather_files:
            if not Path(file_path).exists():
                continue
            ds = self._open_dataset_resilient(file_path)
            if ds is None:
                continue
            try:
                weather_vars = self._extract_weather_variables(ds)
                for var_name, var_data in weather_vars.items():
                    if var_data is not None:
                        df_temp = self._netcdf_to_dataframe(var_data, var_name)
                        if not df_temp.empty:
                            weather_data.append(df_temp)
            except Exception as e:
                logger.warning(f"   ⚠️ Could not process weather file: {e}")
            finally:
                try:
                    ds.close()
                except Exception:
                    pass
        
        if weather_data:
            # Combine weather data
            weather_df = pd.concat(weather_data, ignore_index=True)
            
            # Regrid to common grid
            weather_df = self._regrid_to_common_grid(weather_df)
            
            # Pivot variables to columns
            weather_pivot = weather_df.pivot_table(
                index=['time', 'lat_grid', 'lon_grid'],
                columns='variable',
                values='value',
                aggfunc='mean'
            ).reset_index()
            
            weather_pivot['data_source'] = 'weather'
            
            logger.info(f"   Processed {len(weather_pivot)} weather grid-time records")
            return weather_pivot
        
        return pd.DataFrame()
    
    def _process_viirs_data(self, viirs_files: Dict) -> pd.DataFrame:
        """Process VIIRS AOD data for PM estimation"""
        
        logger.info("🌍 Processing VIIRS AOD data...")
        
        aod_files = viirs_files.get('AOD', [])
        if not aod_files:
            logger.warning("⚠️ No VIIRS AOD files found")
            return pd.DataFrame()
        
        viirs_data = []
        
        for file_path in aod_files:
            if not Path(file_path).exists():
                continue
                
            try:
                ds = xr.open_dataset(file_path)
                
                # Extract AOD (variable names may vary)
                aod_var = self._extract_viirs_aod(ds)
                
                if aod_var is not None:
                    # Convert AOD to estimated PM (empirical relationships)
                    pm25_est = aod_var * 35  # Empirical conversion factor
                    pm10_est = aod_var * 60  # Empirical conversion factor
                    
                    # Convert to DataFrames
                    df_pm25 = self._netcdf_to_dataframe(pm25_est, 'PM2.5_satellite')
                    df_pm10 = self._netcdf_to_dataframe(pm10_est, 'PM10_satellite')
                    
                    if not df_pm25.empty:
                        viirs_data.append(df_pm25)
                    if not df_pm10.empty:
                        viirs_data.append(df_pm10)
                
                ds.close()
                
            except Exception as e:
                logger.warning(f"   ⚠️ Could not process VIIRS file: {e}")
                continue
        
        if viirs_data:
            viirs_df = pd.concat(viirs_data, ignore_index=True)
            viirs_df = self._regrid_to_common_grid(viirs_df)
            
            # Pivot estimates to columns
            viirs_pivot = viirs_df.pivot_table(
                index=['time', 'lat_grid', 'lon_grid'],
                columns='variable',
                values='value',
                aggfunc='mean'
            ).reset_index()
            
            viirs_pivot['data_source'] = 'viirs'
            
            logger.info(f"   Processed {len(viirs_pivot)} VIIRS grid-time records")
            return viirs_pivot
        
        return pd.DataFrame()
    
    def _extract_tempo_variable(self, ds: xr.Dataset, variable: str) -> Optional[xr.DataArray]:
        """Extract variable from TEMPO dataset"""
        
        # Common TEMPO variable names (may need adjustment based on actual data)
        variable_maps = {
            'NO2': ['NO2', 'nitrogen_dioxide_tropospheric_column', 'tropospheric_NO2_column'],
            'O3': ['O3', 'ozone_tropospheric_column', 'tropospheric_O3_column'],
            'HCHO': ['HCHO', 'formaldehyde_tropospheric_column'],
            'AEROSOL': ['AI', 'aerosol_index', 'uvai']
        }
        
        possible_names = variable_maps.get(variable, [variable])
        
        for name in possible_names:
            if name in ds.variables:
                return ds[name]

        # Fallback heuristic: choose first float DataArray with 2+ dims containing lat/lon-like dims
        for var_name, da in ds.data_vars.items():
            try:
                if da.dtype.kind in {'f','i'} and len(da.dims) >= 2:
                    dim_names = [d.lower() for d in da.dims]
                    if any('lat' in d for d in dim_names) and any('lon' in d or 'long' in d for d in dim_names):
                        logger.warning(f"   Fallback: using {var_name} for {variable} (heuristic)")
                        return da
            except Exception:
                continue

        logger.warning(f"   Could not find {variable} in dataset variables (tried {possible_names}); available: {list(ds.variables.keys())}")
        return None
    
    def _extract_weather_variables(self, ds: xr.Dataset) -> Dict[str, Optional[xr.DataArray]]:
        """Extract weather variables from dataset"""
        
        weather_vars = {}
        
        # Temperature (convert from Kelvin if needed)
        temp_vars = ['TMP', 'T2M', 'temperature', 'temp']
        for var_name in temp_vars:
            if var_name in ds.variables:
                temp_data = ds[var_name]
                # Convert K to C if values are in Kelvin range
                if temp_data.values.mean() > 100:  # Likely Kelvin
                    temp_data = temp_data - 273.15
                weather_vars['temperature'] = temp_data
                break
        
        # Humidity
        humidity_vars = ['SPFH', 'QV2M', 'RH2M', 'humidity', 'rh']
        for var_name in humidity_vars:
            if var_name in ds.variables:
                hum_data = ds[var_name]
                # Convert to percentage if needed
                if hum_data.values.max() <= 1:  # Likely fraction
                    hum_data = hum_data * 100
                weather_vars['humidity'] = hum_data
                break
        
        # Wind speed (calculate from components if available)
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
            wind_speed = np.sqrt(u_wind**2 + v_wind**2)
            weather_vars['wind_speed'] = wind_speed
        
        return weather_vars
    
    def _extract_viirs_aod(self, ds: xr.Dataset) -> Optional[xr.DataArray]:
        """Extract AOD from VIIRS dataset"""
        
        aod_vars = ['AOD_550', 'Aerosol_Optical_Depth_550', 'AOT_550', 'aod']
        
        for var_name in aod_vars:
            if var_name in ds.variables:
                return ds[var_name]
        
        logger.warning(f"   Could not find AOD variable in: {list(ds.variables.keys())}")
        return None
    
    def _netcdf_to_dataframe(self, data_array: xr.DataArray, variable_name: str) -> pd.DataFrame:
        """Convert xarray DataArray to DataFrame"""
        
        try:
            # Convert to DataFrame
            df = data_array.to_dataframe().reset_index()
            
            # Standardize column names
            coord_mapping = {
                'lat': 'latitude', 'latitude': 'latitude',
                'lon': 'longitude', 'longitude': 'longitude', 'long': 'longitude',
                'time': 'time', 'datetime': 'time'
            }
            
            for old_name, new_name in coord_mapping.items():
                if old_name in df.columns:
                    df = df.rename(columns={old_name: new_name})
            
            # Get the value column (should be the variable name)
            value_cols = [col for col in df.columns if col not in ['latitude', 'longitude', 'time']]
            if value_cols:
                df = df.rename(columns={value_cols[0]: 'value'})
                df['variable'] = variable_name
            
            # Remove invalid values
            df = df.dropna(subset=['value'])
            df = df[df['value'] != -999]  # Common fill value
            
            return df
            
        except Exception as e:
            logger.warning(f"   Error converting {variable_name} to DataFrame: {e}")
            return pd.DataFrame()
    
    def _regrid_to_common_grid(self, df: pd.DataFrame) -> pd.DataFrame:
        """Regrid data to common grid resolution"""
        
        if 'latitude' in df.columns and 'longitude' in df.columns:
            df['lat_grid'] = (df['latitude'] / self.config.GRID_RESOLUTION).round() * self.config.GRID_RESOLUTION
            df['lon_grid'] = (df['longitude'] / self.config.GRID_RESOLUTION).round() * self.config.GRID_RESOLUTION
        
        return df
    
    def _merge_all_sources(self, ground_data: pd.DataFrame, tempo_data: pd.DataFrame,
                          weather_data: pd.DataFrame, viirs_data: pd.DataFrame) -> pd.DataFrame:
        """Merge all data sources on time and location"""
        
        logger.info("🔗 Merging all data sources...")
        
        # Start with ground data as base (most reliable)
        if not ground_data.empty:
            merged = ground_data.copy()
            logger.info(f"   Base: {len(merged)} ground records")
        else:
            # Fallback to TEMPO if no ground data
            merged = tempo_data.copy() if not tempo_data.empty else pd.DataFrame()
            logger.info(f"   Base: {len(merged)} TEMPO records")
        
        if merged.empty:
            logger.warning("❌ No base data to merge")
            return pd.DataFrame()
        
        # Merge weather data
        if not weather_data.empty:
            pre_count = len(merged)
            merged = merged.merge(
                weather_data,
                on=['time', 'lat_grid', 'lon_grid'],
                how='left',
                suffixes=('', '_weather')
            )
            logger.info(f"   Added weather: {pre_count} → {len(merged)} records")
        
        # Merge TEMPO data (for satellite pollutants)
        if not tempo_data.empty and 'tempo' not in merged.get('data_source', ''):
            pre_count = len(merged)
            merged = merged.merge(
                tempo_data,
                on=['time', 'lat_grid', 'lon_grid'],
                how='left',
                suffixes=('', '_satellite')
            )
            logger.info(f"   Added TEMPO: {pre_count} → {len(merged)} records")
        
        # Merge VIIRS estimates
        if not viirs_data.empty:
            pre_count = len(merged)
            merged = merged.merge(
                viirs_data,
                on=['time', 'lat_grid', 'lon_grid'],
                how='left',
                suffixes=('', '_viirs')
            )
            logger.info(f"   Added VIIRS: {pre_count} → {len(merged)} records")
        
        return merged
    
    def _finalize_dataset(self, merged_data: pd.DataFrame, already_aggregated: bool=False) -> pd.DataFrame:
        """Final processing and formatting"""
        
        logger.info("🎯 Finalizing dataset...")
        
        if merged_data.empty:
            return pd.DataFrame(columns=self.config.TARGET_COLUMNS)

        # Ensure time is datetime and sorted
        if 'time' in merged_data.columns:
            merged_data['time'] = pd.to_datetime(merged_data['time'], errors='coerce')
            merged_data = merged_data.sort_values('time')
        
        # Fill missing values using satellite estimates (only if not already aggregated)
        if not already_aggregated:
            self._fill_missing_values(merged_data)
        else:
            self._fill_missing_values(merged_data)
        
        # Select target columns
        final_data = pd.DataFrame()
        for col in self.config.TARGET_COLUMNS:
            if col in merged_data.columns:
                final_data[col] = merged_data[col]
            else:
                final_data[col] = np.nan
        
        # Preserve all hours even if pollutants all NaN (continuity requirement)
        # Optionally future: flag rows with no data
        if 'time' in final_data.columns:
            final_data['no_data_flag'] = final_data[['PM2.5','PM10','O3','NO2','SO2','CO']].isna().all(axis=1)
        
        # Sort by time
        final_data = final_data.sort_values('time').reset_index(drop=True)
        
        logger.info(f"   Final dataset: {len(final_data)} records")
        self._print_final_summary(final_data)
        
        return final_data
    
    def _fill_missing_values(self, df: pd.DataFrame):
        """Fill missing values using satellite estimates"""
        
        # Fill PM values with satellite estimates
        if 'PM2.5_satellite' in df.columns:
            df['PM2.5'] = df['PM2.5'].fillna(df['PM2.5_satellite'])
        if 'PM10_satellite' in df.columns:
            df['PM10'] = df['PM10'].fillna(df['PM10_satellite'])
        
        # Fill pollutants with satellite values
        satellite_mapping = {
            'O3': 'O3_satellite',
            'NO2': 'NO2_satellite'
        }
        
        for ground_col, sat_col in satellite_mapping.items():
            if sat_col in df.columns:
                df[ground_col] = df[ground_col].fillna(df[sat_col])
    
    def _print_final_summary(self, df: pd.DataFrame):
        """Print summary of final dataset"""
        
        logger.info("📊 Final Dataset Summary:")
        logger.info(f"   Total records: {len(df):,}")
        
        if len(df) > 0:
            logger.info(f"   Time range: {df['time'].min()} to {df['time'].max()}")
            
            # Data completeness
            for col in self.config.TARGET_COLUMNS[1:]:  # Skip 'time'
                if col in df.columns:
                    completeness = (1 - df[col].isna().sum() / len(df)) * 100
                    logger.info(f"     {col}: {completeness:.1f}% complete")

            expected_hours = ((df['time'].max() - df['time'].min()).days + 1) * 24
            logger.info(f"   Expected hours (approx): {expected_hours}; Actual rows: {len(df)}")

    # --- Newly Added Helpers ---
    def _build_hourly_scaffold(self) -> pd.DataFrame:
        """Create continuous hourly dataframe for past 7 full days (UTC)."""
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        hours = pd.date_range(start=start, end=end - timedelta(hours=1), freq='H')
        scaffold = pd.DataFrame({'time': hours})
        for col in self.config.TARGET_COLUMNS[1:]:
            scaffold[col] = np.nan
        return scaffold

    def _aggregate_spatial(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate grid-cell level data into single mean per hour for target pollutants & weather."""
        if df.empty:
            return pd.DataFrame()

        # Ensure time column exists
        if 'time' not in df.columns:
            return pd.DataFrame()
        # Standardize time
        df['time'] = pd.to_datetime(df['time'], errors='coerce')
        df = df.dropna(subset=['time'])

        # Candidate columns present
        available = [c for c in self.config.TARGET_COLUMNS[1:] if c in df.columns]
        if not available:
            # Attempt mapping from variable-style columns
            rename_map = {}
            for pollutant in ['NO2','O3','CO','SO2']:
                if pollutant in df.columns:
                    rename_map[pollutant] = pollutant
            # PM estimates maybe in satellite columns
            for sat_col, dest in [('PM2.5_satellite','PM2.5'), ('PM10_satellite','PM10')]:
                if sat_col in df.columns:
                    rename_map[sat_col] = dest
            df = df.rename(columns=rename_map)
            available = [c for c in self.config.TARGET_COLUMNS[1:] if c in df.columns]

        group_cols = ['time']
        agg_dict = {col: 'mean' for col in available}
        aggregated = df.groupby(group_cols).agg(agg_dict).reset_index()
        return aggregated

    def _open_dataset_resilient(self, path: str) -> Optional[xr.Dataset]:
        """Attempt to open a NetCDF/HDF file with multiple engines and fallbacks."""
        engines = ['netcdf4', 'h5netcdf']
        for eng in engines:
            try:
                ds = xr.open_dataset(path, engine=eng)
                return ds
            except Exception as e:
                continue
        # Final fallback: inspect with h5py for debugging (not raising)
        try:
            import h5py
            with h5py.File(path, 'r') as h5f:
                logger.warning(f"   h5py fallback listing groups for {path}: {list(h5f.keys())}")
        except Exception:
            pass
        logger.warning(f"   ⚠️ All open attempts failed for {path}")
        return None

def main():
    """Test data unification"""
    # This would be called after data fetching is complete
    logger.info("🧪 Testing data unification (placeholder)")
    
    # Example usage:
    # unifier = DustIQDataUnifier()
    # data_sources = {
    #     'GROUND': {'OpenAQ': 'path/to/openaq.parquet'},
    #     'TEMPO': {'NO2': ['path/to/tempo_no2.nc']},
    #     'WEATHER': {'NLDAS': ['path/to/nldas.nc']},
    #     'VIIRS': {'AOD': ['path/to/viirs.nc']}
    # }
    # unified_data = unifier.unify_all_sources(data_sources)

if __name__ == "__main__":
    main()