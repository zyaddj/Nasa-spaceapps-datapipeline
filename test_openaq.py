#!/usr/bin/env python3
"""Test OpenAQ data fetcher independently"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_pipeline.fetch_openaq import OpenAQFetcher
from data_pipeline.config import DataConfig
from datetime import datetime, timedelta

def test_openaq():
    """Test OpenAQ data fetcher"""
    config = DataConfig()
    fetcher = OpenAQFetcher()  # No config parameter needed
    
    # Test for smaller region (California) for faster results
    ca_bbox = (-125.0, 32.0, -114.0, 42.0)  # west, south, east, north
    
    # Test recent data (yesterday)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(hours=6)  # 6 hour window
    
    print(f"🔍 Testing OpenAQ data fetcher...")
    print(f"Date range: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"California BBOX: {ca_bbox}")
    
    try:
        # Convert datetime to string format for API
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        result_file = fetcher.fetch_measurements(start_str, end_str, list(ca_bbox))
        
        if result_file:
            print(f"✅ SUCCESS: Saved data to {result_file}")
            # Try to load and display the data
            import pandas as pd
            data = pd.read_parquet(result_file)
            print(f"Columns: {list(data.columns)}")
            print(f"Parameters: {data['parameter'].unique()}")
            print(f"Unique locations: {len(data['location'].unique())}")
            print(f"Total measurements: {len(data)}")
            print("\nSample data:")
            print(data[['location', 'parameter', 'value', 'unit', 'latitude', 'longitude']].head())
            return True
        else:
            print("⚠️  No data file created - this could be normal depending on timing")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_openaq()