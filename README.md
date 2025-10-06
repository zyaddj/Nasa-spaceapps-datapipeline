# NASA TEMPO + OpenAQ Data Pipeline

## Overview

A comprehensive data pipeline that integrates **NASA's TEMPO satellite observations** with **ground-based air quality monitoring data from OpenAQ**. This system automatically fetches, processes, and unifies multiple pollutant datasets including PM2.5, PM10, NO₂, O₃, SO₂, CO, and meteorological data across North America.

**Key Value**: Combines cutting-edge satellite remote sensing with ground truth validation to create comprehensive air quality datasets for research and analysis.

## Data Sources

### NASA TEMPO Satellite
**TEMPO** (Tropospheric Emissions: Monitoring of Pollution) is NASA's first Earth Venture Instrument mission focused on air quality measurements over North America.

- **Coverage**: Hourly measurements during daylight hours across North America
- **Resolution**: 2.1 km × 4.4 km at nadir
- **Pollutants**: NO₂, O₃, HCHO, Aerosol Index

### OpenAQ Ground Monitoring Network
- **Coverage**: Thousands of EPA-certified monitoring stations
- **Pollutants**: PM2.5, PM10, NO₂, O₃, SO₂, CO
- **Advantage**: Real-time ground truth data for satellite validation

### Meteorological Data
- **Sources**: NLDAS/MERRA-2
- **Parameters**: Temperature, humidity, wind speed, precipitation
- **Purpose**: Environmental context for air quality analysis

### Output Format
```
time,lat,lon,PM2.5,PM10,O3,NO2,SO2,CO,temperature,humidity,wind_speed,aerosol_index
```

## Project Structure

```
/nasa-tempo-openaq-pipeline
  /data_pipeline/          # Core data retrieval system
    fetch_tempo.py         # NASA TEMPO satellite data ingestion
    fetch_openaq.py        # OpenAQ ground monitoring data
    fetch_viirs.py         # VIIRS aerosol supplementary data
    fetch_weather.py       # NLDAS/MERRA-2 meteorological data
    data_unifier.py        # Multi-source data integration
    config.py              # Pipeline configuration
    build_past_week_hourly.py # Automated daily processing
  /backend/                # API layer for data access
    requirements.txt       # Python dependencies
  test_pipeline.py         # Complete system validation
  test_openaq.py          # OpenAQ-specific testing
```

## Quick Start

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd nasa-tempo-openaq-pipeline
pip install -r backend/requirements.txt
```

### 2. Configure API Access
```bash
cp data_pipeline/.env.example data_pipeline/.env
# Edit .env with your NASA Earthdata credentials (see API_SETUP.md)
```

### 3. Test the Pipeline
```bash
cd data_pipeline
python ../test_pipeline.py  # Validates all data source connections
```

### 4. Run Data Collection
```bash
python build_past_week_hourly.py  # Downloads and processes last 7 days
```

### 5. Access Processed Data
```bash
# Processed data available in: data/processed/
python -c "
import pandas as pd
df = pd.read_parquet('data/processed/past_week_hourly.parquet')
print('Dataset shape:', df.shape)
print('Columns:', df.columns.tolist())
"
```
```bash
## API Requirements

### NASA Earthdata Login (Required)
- **Purpose**: TEMPO satellite data + meteorological data
- **Setup**: Create account at [NASA Earthdata](https://urs.earthdata.nasa.gov/)
- **Cost**: Free

### LAADS DAAC Token (Required for VIIRS)
- **Purpose**: VIIRS aerosol data
- **Setup**: Generate token at [LAADS DAAC](https://ladsweb.modaps.eosdis.nasa.gov/)
- **Cost**: Free (requires NASA Earthdata login)

### OpenAQ API (No Authentication Required)
- **Purpose**: Ground monitoring station data
- **Setup**: None required - uses public API
- **Cost**: Free

For detailed setup instructions, see `API_SETUP.md`.
```

### 6. Optional: Start API Server for Programmatic Access
```bash
cd backend
uvicorn api:app --reload  # RESTful endpoints for data access
# Access data via: http://localhost:8000/latest, /forecast, /health
```

## 🔑 Required API Credentials

### NASA Earthdata Access (Required)
TEMPO data requires authentication through NASA's Earthdata Login:
1. Create account at: https://urs.earthdata.nasa.gov/
2. Add applications: **LAADS DAAC** and **EarthDATA Search**
3. Set credentials in `.env` file

### OpenAQ API (No Authentication Required)
- OpenAQ provides free access to ground monitoring data
- No API key needed - pipeline uses public REST endpoints
- Rate limited to reasonable usage patterns

See `API_SETUP.md` for detailed setup instructions.

## Use Cases

- **Environmental Research**: Academic studies requiring satellite + ground truth validation
- **Air Quality Analysis**: Comprehensive pollutant monitoring and trend analysis  
- **Policy Development**: Evidence-based environmental decision making
- **Health Studies**: Exposure assessment using multi-source data
- **Model Development**: Training data for air quality prediction models

## Features

- ✅ Automated TEMPO satellite data retrieval (hourly observations)
- ✅ Ground station integration (OpenAQ monitoring network)
- ✅ Multi-pollutant coverage (PM2.5, PM10, NO₂, O₃, SO₂, CO, aerosols)
- ✅ Meteorological context (temperature, humidity, wind patterns)
- ✅ Quality control and data validation
- ✅ Unified analysis-ready output format
- ✅ Scalable architecture for large datasets

## Data Quality

- **Coverage**: Complete North America (-130°W to -60°W, 20°N to 55°N)
- **Resolution**: 0.125° grid spacing (~12.5 km)
- **Temporal**: Hourly during TEMPO observation periods
- **Validation**: Cross-validated against EPA monitoring standards

---

**NASA TEMPO + OpenAQ Data Pipeline** - Bridging satellite remote sensing with ground truth validation for comprehensive air quality analysis.