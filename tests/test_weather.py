#!/usr/bin/env python3
"""
Standalone weather API test script
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_weather_api(city_name="London"):
    api_key = os.getenv('OPENWEATHER_API_KEY')
    print(f"API Key present: {bool(api_key)}")
    
    if not api_key:
        print("❌ No OPENWEATHER_API_KEY found in .env file")
        return
    
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&units=metric&appid={api_key}"
    print(f"Testing URL: {url}")
    
    try:
        resp = requests.get(url)
        print(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"❌ API Error: {resp.text}")
            return
            
        data = resp.json()
        print(f"✅ API Success! Got {len(data['list'])} forecast entries")
        
        # Process like the main app
        forecasts = {}
        for entry in data['list']:
            date = entry['dt_txt'].split(' ')[0]
            if date not in forecasts:
                forecasts[date] = []
            forecasts[date].append(entry)
        
        daily = []
        for i, (date, entries) in enumerate(forecasts.items()):
            if i >= 7:  # Max 7 days
                break
            midday = min(entries, key=lambda e: abs(int(e['dt_txt'].split(' ')[1][:2]) - 12))
            desc = midday['weather'][0]['main']
            temp = round(midday['main']['temp'])
            daily.append({'date': date, 'desc': desc, 'temp': temp})
            print(f"  {date}: {desc}, {temp}°C")
        
        print(f"✅ Processed {len(daily)} daily forecasts")
        return daily
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    print("=== Weather API Test ===")
    test_weather_api("New York")