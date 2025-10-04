# DustIQ — North America Dust & AQI Forecast (NASA Space Apps 2025)

## 🌪️ What We're Building

A web application that **forecasts AQI 24–72h ahead** across **North America**, with specialized focus on **dust pollution events**. We integrate **satellite pollutants (TEMPO + VIIRS)**, **weather data (NLDAS/MERRA-2)**, and **ground sensors (OpenAQ)** to provide real-time air quality predictions and health alerts.

## 🛰️ Data Sources & Integration

### Primary Data Sources:
- **TEMPO** (hourly, North America) → Real-time pollutants: NO₂, O₃, HCHO, Aerosol Index
- **VIIRS Deep Blue L3** (daily) → Aerosol Optical Depth for dust detection
- **NLDAS/MERRA-2** (hourly) → Weather: temperature, humidity, wind, precipitation
- **OpenAQ** (real-time) → Ground validation: PM2.5, PM10, NO₂, O₃, SO₂, CO

### Target Output Format:
```
time,PM2.5,PM10,O3,NO2,SO2,CO,temperature,humidity,wind_speed
```

## 📁 Repository Structure

```
/dustiq
  /backend                 # FastAPI server
    api.py                 # API endpoints (/forecast, /latest, /health)
    model_train.py         # ConvLSTM model training
    model_predict.py       # AQI prediction service
    requirements.txt
  /data_pipeline          # Data ingestion (YOUR FOCUS)
    fetch_tempo.py         # TEMPO satellite data
    fetch_viirs.py         # VIIRS aerosol data
    fetch_weather.py       # NLDAS/MERRA-2 weather
    fetch_openaq.py        # OpenAQ ground sensors
    data_unifier.py        # Combine all sources
    config.py              # Configuration management
    .env.example           # API credentials template
  /frontend               # React + mapping
    src/
      components/          # UI components
      pages/               # App pages
      map/                 # Map visualization
    package.json
  /data
    raw/                   # Downloaded data (gitignored)
      tempo/
      viirs/
      weather/
      openaq/
    processed/             # Unified datasets
  /models                 # Trained ML models
  /tests                  # Unit tests
```

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd dustiq
pip install -r backend/requirements.txt
```

### 2. Configure API Keys
```bash
cp data_pipeline/.env.example data_pipeline/.env
# Edit .env with your credentials (see API Setup section)
```

### 3. Test Data Pipeline
```bash
cd data_pipeline
python test_pipeline.py
```

### 4. Run Backend
```bash
cd backend
uvicorn api:app --reload
```

### 5. Run Frontend
```bash
cd frontend
npm install
npm start
```

## 🔑 Required API Credentials

See `API_SETUP.md` for detailed instructions on obtaining:
- NASA Earthdata Login
- LAADS DAAC Token (for VIIRS)
- OpenAQ API (no key required)

## 🎯 NASA Space Apps Challenge Alignment

- ✅ **Real-time TEMPO integration** (primary requirement)
- ✅ **Ground-based validation** (Pandora/OpenAQ requirement)
- ✅ **Weather data integration** (atmospheric context)
- ✅ **Cloud-native processing** (scalable architecture)
- ✅ **Health impact focus** (AQI forecasting + alerts)
- ✅ **User-centric design** (personalized alerts)
- 🌪️ **Dust specialization** (competitive advantage)

## 🏆 Innovation: Dust-Focused AQI Prediction

Our unique contribution combines multiple NASA datasets to specifically forecast dust-driven air quality events, helping vulnerable populations prepare for dust storms and poor air quality days.

## 👥 Team Roles

- **Data Engineer**: Data pipeline, API integration, data processing
- **ML Engineer**: ConvLSTM model, prediction algorithms, validation
- **Frontend Developer**: React app, map visualization, user interface
- **Full-Stack**: API backend, deployment, integration

## 📊 Success Metrics

- Forecast accuracy: >75% for 24-hour AQI predictions
- Data integration: All 4 primary sources successfully merged
- Real-time performance: <30 second API response times
- Geographic coverage: Complete North America (bbox: -130,20,-60,55)

---

Built for **NASA Space Apps Challenge 2025** | "From EarthData to Action"