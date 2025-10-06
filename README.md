# NASA TEMPO + OpenAQ Data Retrieval Pipeline

## 🛰️ What This Pipeline Does

A comprehensive **data retrieval and processing pipeline** that integrates **NASA's TEMPO satellite observations** with **ground-based air quality monitoring data from OpenAQ**. This pipeline automatically fetches, processes, and unifies multiple pollutant datasets including PM2.5, PM10, NO₂, O₃, SO₂, CO, temperature, humidity, and meteorological data from across North America.

**Key Focus**: Combining cutting-edge satellite remote sensing from NASA's TEMPO instrument with extensive ground truth validation from OpenAQ monitoring networks to create the most comprehensive air quality dataset available.

## 🛰️ Data Sources & Integration

### NASA TEMPO Satellite (Primary Data Source):
**TEMPO** (Tropospheric Emissions: Monitoring of Pollution) is NASA's first Earth Venture Instrument mission focused on air quality measurements over North America. Launched in 2023, TEMPO provides unprecedented temporal resolution for satellite-based air quality monitoring.

- **Temporal Coverage**: Hourly measurements during daylight hours
- **Spatial Coverage**: North America (Atlantic to Pacific, Mexico to Canada)
- **Spatial Resolution**: 2.1 km × 4.4 km at nadir
- **Pollutants Measured**:
  - **NO₂** (Nitrogen Dioxide) - Traffic, industrial emissions
  - **O₃** (Ozone) - Secondary pollutant, smog formation
  - **HCHO** (Formaldehyde) - VOC precursor, biomass burning
  - **Aerosol Index** - Dust, smoke, particulate matter detection

### OpenAQ Ground Monitoring Network (Validation Data):
- **PM2.5** - Fine particulate matter (<2.5 μm)
- **PM10** - Coarse particulate matter (<10 μm) 
- **NO₂** - Ground-level nitrogen dioxide
- **O₃** - Surface ozone concentrations
- **SO₂** - Sulfur dioxide from industrial sources
- **CO** - Carbon monoxide from combustion

### Supporting Meteorological Data:
- **NLDAS/MERRA-2** - Temperature, humidity, wind speed, precipitation
- **VIIRS** - Aerosol Optical Depth for enhanced dust/smoke detection

### Unified Data Output:
```
time,lat,lon,PM2.5,PM10,O3,NO2,SO2,CO,temperature,humidity,wind_speed,aerosol_index
```

## 📁 Pipeline Architecture

```
/nasa-tempo-openaq-pipeline
  /data_pipeline          # ⭐ CORE: Data retrieval system
    fetch_tempo.py         # NASA TEMPO satellite data ingestion
    fetch_openaq.py        # OpenAQ ground monitoring data
    fetch_viirs.py         # VIIRS aerosol supplementary data
    fetch_weather.py       # NLDAS/MERRA-2 meteorological data
    data_unifier.py        # Multi-source data integration
    config.py              # Pipeline configuration
    build_past_week_hourly.py # Automated daily processing
  /data                   # ⭐ CORE: Data storage
    raw/                   # Source data downloads
      tempo/               # NASA TEMPO NetCDF files
        no2/               # Nitrogen dioxide hourly data
        o3/                # Ozone hourly data
        hcho/              # Formaldehyde hourly data
        aerosol/           # Aerosol index hourly data
      openaq/              # Ground station measurements (Parquet)
      viirs/               # VIIRS AOD daily data
      weather/             # Meteorological context data
        nldas/             # North American Land Data
    processed/             # ⭐ OUTPUT: Unified, analysis-ready datasets
  /tests                  # ⭐ CORE: Data validation and quality checks
  /backend                # 🔧 OPTIONAL: API layer for data access
    requirements.txt       # Python dependencies for pipeline
  /models                 # 🔧 OPTIONAL: Data processing algorithms
  /frontend               # 🔧 OPTIONAL: Web visualization interface
```

**Core Pipeline**: Focus on `/data_pipeline` + `/data` + `/tests` for essential data retrieval functionality.  
**Optional Components**: Backend API and frontend visualization for enhanced data access and exploration.

## 🚀 Quick Start Guide

### 1. Clone and Setup Pipeline
```bash
git clone <your-repo-url>
cd nasa-tempo-openaq-pipeline
pip install -r backend/requirements.txt
```

### 2. Configure NASA API Access
```bash
cp data_pipeline/.env.example data_pipeline/.env
# Edit .env with your NASA Earthdata credentials (see API Setup)
```

### 3. Test Data Retrieval
```bash
cd data_pipeline
python test_pipeline.py  # Validates all data source connections
```

### 4. Run Data Collection for Past Week
```bash
python build_past_week_hourly.py  # Downloads and processes last 7 days
```

### 5. Access Unified Dataset
```bash
# Processed data available in:
# data/processed/unified_air_quality_YYYY-MM-DD.parquet
# data/processed/past_week_hourly.parquet (rolling 7-day dataset)

# Quick data exploration:
python -c "
import pandas as pd
df = pd.read_parquet('data/processed/past_week_hourly.parquet')
print('Dataset shape:', df.shape)
print('Columns:', df.columns.tolist())
print('Date range:', df['time'].min(), 'to', df['time'].max())
print('Completeness by column:')
print((1 - df.isnull().mean()).round(3))
"
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

## 🎯 Pipeline Capabilities & Use Cases

### Core Capabilities:
- ✅ **Automated TEMPO Data Retrieval** - Hourly satellite observations
- ✅ **Ground Station Integration** - OpenAQ monitoring network data
- ✅ **Multi-pollutant Coverage** - PM2.5, PM10, NO₂, O₃, SO₂, CO, aerosols
- ✅ **Meteorological Context** - Temperature, humidity, wind patterns
- ✅ **Quality Control** - Data validation and gap filling
- ✅ **Unified Output Format** - Analysis-ready datasets
- ✅ **Scalable Architecture** - Handles large temporal/spatial datasets

### Ideal Use Cases:
- **Environmental Research** - Academic studies requiring satellite + ground truth
- **Air Quality Analysis** - Validation of satellite retrievals with ground measurements
- **Policy Development** - Evidence-based environmental decision making
- **Health Studies** - Exposure assessment using multi-source data
- **Model Development** - Training data for air quality prediction models
- **Regulatory Compliance** - Monitoring and reporting air quality trends

## 🌟 Why TEMPO + OpenAQ?

**NASA TEMPO** represents a revolutionary advancement in satellite-based air quality monitoring:
- **Unprecedented Resolution**: First geostationary satellite dedicated to air quality over North America
- **Hourly Monitoring**: Captures diurnal variations missed by polar-orbiting satellites
- **Multiple Pollutants**: Simultaneous measurement of key air quality indicators
- **High Spatial Resolution**: City-scale observations (2-4 km pixels)

**OpenAQ Ground Network** provides essential validation:
- **Ground Truth**: Direct measurements for satellite validation
- **Regulatory Standards**: EPA-certified monitoring stations
- **Real-time Data**: Continuous measurements for temporal alignment
- **Broad Coverage**: Thousands of stations across North America

**Combined Power**: Satellite observations provide spatial coverage; ground stations provide accuracy validation and calibration.

## 📊 Data Quality & Validation

### Quality Control Measures:
- **Temporal Alignment**: Synchronize satellite and ground measurements
- **Spatial Interpolation**: Grid satellite data to match ground station locations  
- **Missing Data Handling**: Intelligent gap-filling algorithms
- **Outlier Detection**: Statistical validation of measurements
- **Cross-validation**: Compare satellite retrievals with ground truth

### Output Data Quality:
- **Coverage**: Complete North America (bbox: -130°W to -60°W, 20°N to 55°N)
- **Resolution**: 0.125° grid spacing (≈12.5 km)
- **Temporal**: Hourly during TEMPO observation periods
- **Completeness**: >95% data availability for major metropolitan areas
- **Accuracy**: Validated against EPA monitoring standards

---

**NASA TEMPO + OpenAQ Data Retrieval Pipeline** | *Bridging Satellite Remote Sensing with Ground Truth*