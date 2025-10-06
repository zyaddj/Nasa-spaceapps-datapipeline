"""NASA TEMPO + OpenAQ Data Retrieval Pipeline - Past Week Builder

Produces comprehensive hourly air quality dataset combining:
- NASA TEMPO satellite observations (NO₂, O₃, HCHO, Aerosol Index)
- OpenAQ ground monitoring stations (PM2.5, PM10, NO₂, O₃, SO₂, CO)
- Meteorological context (temperature, humidity, wind_speed)

Output: 168 hourly rows (7 days) with unified pollutant and weather data

Strategy:
 1. Determine past 7-day UTC observation window
 2. Fetch TEMPO satellite data (best-effort retrieval)
 3. Retrieve OpenAQ ground station measurements 
 4. Collect supporting meteorological data (NLDAS/MERRA-2)
 5. Unify all sources into analysis-ready dataset
 6. Export to Parquet + CSV with quality report

Designed for robustness: partial failures in one source won't abort the entire pipeline.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
import pandas as pd

from .config import DataConfig, APIConfig
from .fetch_tempo import TEMPOFetcher
from .fetch_weather import WeatherFetcher
from .fetch_openaq import OpenAQFetcher
from .data_unifier import DustIQDataUnifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("build_past_week")

def past_week_range():
    end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=7)
    return start.date().isoformat(), end.date().isoformat()

def main():
    config = DataConfig()
    api = APIConfig()

    start_date, end_date = past_week_range()
    bbox = list(config.BBOX)

    logger.info("🚀 Building past-week unified hourly dataset")
    logger.info(f"   Date window: {start_date} → {end_date}")
    logger.info(f"   Bounding box: {bbox}")

    # Prepare data_sources structure
    data_sources = { 'GROUND': {}, 'TEMPO': {}, 'WEATHER': {}, 'VIIRS': {} }

    # 1. OpenAQ (ground)
    try:
        openaq_fetcher = OpenAQFetcher()
        openaq_file = openaq_fetcher.fetch_measurements(start_date, end_date, bbox)
        if openaq_file:
            data_sources['GROUND']['OpenAQ'] = openaq_file
    except Exception as e:
        logger.warning(f"OpenAQ fetch failed: {e}")

    # 2. Weather (per-day loop to reduce 403 risk)
    weather_fetcher = WeatherFetcher()
    nldas_accum = []
    merra_accum = []
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        day = start_dt
        while day < end_dt:
            day_start = day.date().isoformat()
            day_end = (day + timedelta(days=1)).date().isoformat()
            daily_files = weather_fetcher.fetch_nldas_data(day_start, day_end, bbox)
            if daily_files:
                nldas_accum.extend(daily_files)
            else:
                # fallback per-day MERRA2
                m_files = weather_fetcher.fetch_merra2_data(day_start, day_end, bbox)
                if m_files:
                    merra_accum.extend(m_files)
            day += timedelta(days=1)
        if nldas_accum:
            data_sources['WEATHER']['NLDAS'] = nldas_accum
        elif merra_accum:
            data_sources['WEATHER']['MERRA2'] = merra_accum
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")

    # 3. TEMPO (per-day to avoid massive search volume)
    tempo_fetcher = TEMPOFetcher()
    tempo_no2 = []
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        day = start_dt
        while day < end_dt:
            d0 = day.date().isoformat()
            d1 = (day + timedelta(days=1)).date().isoformat()
            day_files = tempo_fetcher.fetch_tempo_variable('NO2', d0, d1, bbox)
            if day_files:
                tempo_no2.extend(day_files)
            day += timedelta(days=1)
        if tempo_no2:
            data_sources['TEMPO']['NO2'] = tempo_no2
    except Exception as e:
        logger.warning(f"TEMPO fetch failed: {e}")

    logger.info("📦 Data sources summary:")
    for k,v in data_sources.items():
        logger.info(f"  {k}: {{ {', '.join(f'{subk}:{len(subv)}' for subk,subv in v.items())} }}")

    # 4. Unify
    unifier = DustIQDataUnifier()
    unified = unifier.unify_all_sources(data_sources)

    if unified.empty:
        logger.warning("⚠️ Unified dataset empty (scaffold may have been returned with NaNs)")

    # 5. Save outputs
    out_dir = Path(api.DATA_PROCESSED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / 'past_week_hourly.parquet'
    csv_path = out_dir / 'past_week_hourly.csv'

    # Parquet + CSV with fallback
    wrote_parquet = False
    try:
        unified.to_parquet(parquet_path, index=False)
        wrote_parquet = True
        logger.info(f"✅ Written: {parquet_path} ({len(unified)} rows)")
    except Exception as e:
        logger.warning(f"Parquet write failed ({e}); continuing with CSV only")
    try:
        unified.to_csv(csv_path, index=False)
        logger.info(f"✅ Written: {csv_path} ({len(unified)} rows)")
    except Exception as e:
        logger.error(f"CSV write failed: {e}")

    # Completeness report
    completeness = {}
    for col in DataConfig().TARGET_COLUMNS[1:]:
        if col in unified.columns and len(unified):
            completeness[col] = 100 * (1 - unified[col].isna().sum()/len(unified))
        else:
            completeness[col] = 0.0

    logger.info("📊 Completeness (% non-missing):")
    for k,v in completeness.items():
        logger.info(f"  {k:>12}: {v:5.1f}%")

if __name__ == '__main__':
    main()
