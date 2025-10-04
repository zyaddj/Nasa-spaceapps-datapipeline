# 🔑 API Keys & Credentials Setup Guide

This guide will walk you through obtaining all required API credentials for the DustIQ data pipeline.

## 🛰️ NASA Earthdata Login (Required for TEMPO & Weather Data)

### Step 1: Create NASA Earthdata Account
1. Go to [NASA Earthdata Login](https://urs.earthdata.nasa.gov/)
2. Click "Register for a profile"
3. Fill out the registration form with your information
4. Verify your email address
5. Your username and password are now ready to use

### Step 2: Configure Earthdata Credentials
```bash
# Option 1: Environment variables (recommended)
export EARTHDATA_USERNAME="your_username"
export EARTHDATA_PASSWORD="your_password"

# Option 2: Add to your .env file
echo "EARTHDATA_USERNAME=your_username" >> data_pipeline/.env
echo "EARTHDATA_PASSWORD=your_password" >> data_pipeline/.env
```

### Applications to Approve
After creating your account, you may need to approve access to these applications:
- **TEMPO**: Tropospheric Emissions Monitoring of Pollution
- **NLDAS**: North American Land Data Assimilation System  
- **MERRA-2**: Modern-Era Retrospective Analysis for Research and Applications

---

## 🌍 LAADS DAAC Token (Required for VIIRS Data)

### Step 1: Get LAADS DAAC Token
1. Go to [LAADS DAAC](https://ladsweb.modaps.eosdis.nasa.gov/)
2. Log in with your NASA Earthdata credentials (from above)
3. Click on your username in top-right corner
4. Select "Generate Token"
5. Copy the generated token

### Step 2: Configure LAADS Token
```bash
# Add to .env file
echo "LAADS_TOKEN=your_token_here" >> data_pipeline/.env
```

### Testing LAADS Access
You can test your token with:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/AERDB_D3_VIIRS_NOAA20/2025/001/"
```

---

## 🏭 OpenAQ API (No Key Required)

OpenAQ provides free access to ground-based air quality measurements. No API key is required, but rate limiting applies:

- **Rate Limit**: 1 request per second (automatically handled in our code)
- **Documentation**: [OpenAQ API Docs](https://docs.openaq.org/)
- **Base URL**: `https://api.openaq.org/v2`

---

## ⚙️ Complete .env Configuration

Copy the example file and fill in your credentials:

```bash
cd data_pipeline
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# NASA EARTHDATA CREDENTIALS
EARTHDATA_USERNAME=your_nasa_username
EARTHDATA_PASSWORD=your_nasa_password

# LAADS DAAC TOKEN  
LAADS_TOKEN=your_laads_token

# GEOGRAPHIC CONFIGURATION (North America)
BBOX=-130,20,-60,55
START_DATE=2025-09-01
END_DATE=2025-10-05
GRID_RESOLUTION=0.125

# DATA PIPELINE SETTINGS
MAX_MISSING_RATIO=0.3
MIN_RECORDS_PER_DAY=12
OPENAQ_RATE_LIMIT=1.0

# FILE PATHS
DATA_RAW_DIR=data/raw
DATA_PROCESSED_DIR=data/processed
MODELS_DIR=models

# DEVELOPMENT SETTINGS
LOG_LEVEL=INFO
ENABLE_VALIDATION=true
ENABLE_CACHING=true
```

---

## 🧪 Testing Your Setup

### Test 1: Validate Configuration
```bash
cd data_pipeline
python config.py
```
Expected output:
```
✅ Configuration validated successfully
📊 DustIQ Configuration:
   Bounding box: (-130.0, 20.0, -60.0, 55.0)
   Grid resolution: 0.125°
   Date range: ('2025-09-01', '2025-10-05')
   Target columns: 10 variables
```

### Test 2: Test TEMPO Data Access
```bash
cd data_pipeline
python fetch_tempo.py
```
Expected output:
```
✅ Authenticated with NASA Earthdata
🧪 Testing TEMPO NO2 fetch...
🛰️ Fetching TEMPO NO2 data (TEMPO_NO2_L2)
Found X TEMPO NO2 granules
✅ Test successful! Downloaded X NO2 files
```

### Test 3: Test OpenAQ Access
```bash
cd data_pipeline
python fetch_openaq.py
```
Expected output:
```
🏭 Fetching OpenAQ ground measurements
  📊 Fetching PM25 measurements...
     Retrieved X pm25 measurements
✅ Test successful! Generated file with X records
```

---

## 🚨 Troubleshooting

### Common Issues

#### "Authentication failed" for NASA Earthdata
- **Solution**: Double-check username/password
- **Alternative**: Run `earthaccess.login()` interactively to test credentials

#### "Invalid LAADS token"
- **Solution**: Regenerate token at LAADS DAAC website
- **Check**: Ensure token hasn't expired (tokens are typically valid for 1 year)

#### "No TEMPO data found"
- **Possible causes**: 
  - Data may not be available for your date range
  - TEMPO is a newer satellite (operational since 2023)
- **Solution**: Try a more recent date range (2024-2025)

#### "Rate limited" by OpenAQ
- **Solution**: Our code automatically handles rate limiting
- **Check**: Ensure `OPENAQ_RATE_LIMIT=1.0` in your .env

### Getting Help

1. **NASA Earthdata Support**: [https://urs.earthdata.nasa.gov/documentation](https://urs.earthdata.nasa.gov/documentation)
2. **LAADS DAAC Help**: [https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/](https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/)
3. **OpenAQ Documentation**: [https://docs.openaq.org/](https://docs.openaq.org/)

---

## 🔒 Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use environment variables** in production
3. **Regenerate tokens periodically** (every 6-12 months)
4. **Limit token permissions** where possible

---

## ✅ Next Steps

Once your credentials are configured:

1. **Install dependencies**: `pip install -r backend/requirements.txt`
2. **Run data pipeline test**: `python test_pipeline.py`
3. **Start development**: Begin data fetching and processing
4. **Share with team**: Send this guide to your collaborators

Your DustIQ data pipeline is now ready to fetch data from all sources! 🚀