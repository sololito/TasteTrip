import os
import requests

def get_weather_forecast(city_name, api_key=None, days=3):
    """Get daily weather forecast for a city using OpenWeatherMap."""
    api_key = api_key or os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        return []
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&units=metric&appid={api_key}"
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        print("[DEBUG] OpenWeatherMap raw data:", data)
        # Group by day
        forecasts = {}
        for entry in data['list']:
            date = entry['dt_txt'].split(' ')[0]
            if date not in forecasts:
                forecasts[date] = []
            forecasts[date].append(entry)
        # Take the midday forecast for each day
        daily = []
        for i, (date, entries) in enumerate(forecasts.items()):
            if i >= days:
                break
            # Pick the forecast closest to 12:00
            midday = min(entries, key=lambda e: abs(int(e['dt_txt'].split(' ')[1][:2]) - 12))
            desc = midday['weather'][0]['main']
            temp = round(midday['main']['temp'])
            daily.append({'date': date, 'desc': desc, 'temp': temp})
        return daily
    except Exception as e:
        print(f"Weather API error: {e}")
        return []
