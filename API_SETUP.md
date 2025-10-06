# API Setup Guide

This guide walks you through obtaining the required API credentials for the NASA TEMPO + OpenAQ data pipeline.

## NASA Earthdata Login (Required)

### Step 1: Create Account
1. Go to [NASA Earthdata Login](https://urs.earthdata.nasa.gov/)
2. Click "Register for a profile"
3. Complete registration and verify your email

### Step 2: Configure Credentials
```bash
# Add to data_pipeline/.env file
EARTHDATA_USERNAME=your_username
EARTHDATA_PASSWORD=your_password
```

## LAADS DAAC Token (Required for VIIRS)

### Step 1: Generate Token
1. Go to [LAADS DAAC](https://ladsweb.modaps.eosdis.nasa.gov/)
2. Log in with your NASA Earthdata credentials
3. Click your username → "Generate Token"
4. Copy the generated token

### Step 2: Configure Token
```bash
# Add to data_pipeline/.env file
LAADS_TOKEN=your_token_here
```

## OpenAQ API (No Setup Required)

OpenAQ provides free access to ground monitoring data with no authentication required. The pipeline automatically handles rate limiting.

## Complete .env Configuration

1. Copy the example file:
```bash
cd data_pipeline
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
# NASA EARTHDATA CREDENTIALS
EARTHDATA_USERNAME=your_nasa_username
EARTHDATA_PASSWORD=your_nasa_password

# LAADS DAAC TOKEN  
LAADS_TOKEN=your_laads_token

# GEOGRAPHIC CONFIGURATION
BBOX=-130,20,-60,55
START_DATE=2025-09-01
END_DATE=2025-10-05
```

## Testing Your Setup

Run the pipeline test to verify all credentials work:
```bash
python test_pipeline.py
```

The test will validate each data source connection and report any credential issues.