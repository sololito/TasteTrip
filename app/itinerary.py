import os
import requests
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("TOGETHER_API_KEY")

def get_flight_estimate(origin, destination, month_year):
    """
    Use Together.ai to estimate a round-trip economy flight price (USD) from origin to destination for a given month/year.
    Returns (price, summary) where price is a float/int and summary is a string.
    """
    prompt = f"""
    Estimate the average round-trip economy flight price in USD from {origin} to {destination} for travel in {month_year}. Respond with just a number (no currency sign, no explanation).
    """
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistralai/Mistral-7B-Instruct-v0.1",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 20,
        "temperature": 0.3
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        price_str = result['choices'][0]['message']['content'].strip().replace('$','')
        price = float(''.join([c for c in price_str if (c.isdigit() or c=='.')]))
        summary = f"Estimated round-trip flight from {origin} to {destination} in {month_year}: ${int(price)} USD (economy)"
        return price, summary
    except Exception as e:
        return None, f"(Flight estimate unavailable: {str(e)})"

def get_flight_estimate_with_sites(origin, destination, month_year):
    """
    Get flight price estimate using Together AI
    """
    try:
        price, summary = get_flight_estimate(origin, destination, month_year)
        if price:
            return f"${int(price)} USD", ["Skyscanner", "Kayak", "Expedia"]
    except Exception as e:
        print(f"Flight estimate error: {e}")
    
    return "Contact travel agent for pricing", ["Skyscanner", "Kayak", "Expedia"]

def generate_itinerary_and_sections(taste_data, weather=None):
    """
    Prompts the AI to return: itinerary (with day activities in morning/afternoon/evening), packing checklist, cultural tips, budget (in USDT), transport tips, safety tags, closing message.
    Returns a dict with keys: itinerary, packing, tips, budget, transport, safety, closing.
    """
    vibe = taste_data.get("vibe", "cultural")
    city = taste_data['city']
    country = taste_data.get('country', '')
    days = taste_data.get('days', '3')
    start_date = taste_data.get('start_date', '')
    end_date = taste_data.get('end_date', '')
    date_str = f"from {start_date} to {end_date}" if start_date and end_date else "(no dates provided)"
    currency = taste_data.get('currency', 'USD')
    themes = taste_data.get('themes', ['','',''])
    venues = taste_data.get('venues', [])
    taste_mapping = taste_data.get('taste_mapping', [])
    
    
    weather_summary = ''
    if weather and isinstance(weather, list) and len(weather) > 0:
        descs = ', '.join([str(day.get('desc','')) for day in weather if 'desc' in day])
        temps = ', '.join([str(day.get('temp','')) for day in weather if 'temp' in day])
        weather_summary = f"Weather forecast: {descs}. Temperatures: {temps}°C."

    # Ensure days is an integer
    try:
        num_days = int(days)
    except (ValueError, TypeError):
        num_days = 3
    
    # For longer trips, create weekly structure
    if num_days > 14:
        itinerary_structure = []
        weeks = num_days // 7
        remaining_days = num_days % 7
        
        for week in range(weeks):
            week_start = week * 7 + 1
            itinerary_structure.extend([f'"Day {i}": {{"morning": "morning activity", "afternoon": "afternoon activity", "evening": "evening activity"}}' for i in range(week_start, week_start + 7)])
        
        if remaining_days > 0:
            final_start = weeks * 7 + 1
            itinerary_structure.extend([f'"Day {i}": {{"morning": "morning activity", "afternoon": "afternoon activity", "evening": "evening activity"}}' for i in range(final_start, final_start + remaining_days)])
        
        itinerary_json = ', '.join(itinerary_structure)
    else:
        itinerary_json = ', '.join([f'"Day {i+1}": {{"morning": "morning activity in {city}", "afternoon": "afternoon activity in {city}", "evening": "evening activity in {city}"}}' for i in range(num_days)])
    
    # Create venue-specific guidance for AI
    venue_guidance = ""
    if venues:
        venue_list = ', '.join(venues[:15])  # Limit to prevent prompt overflow
        venue_guidance = f"\nIMPORTANT: Include these specific venues in your itinerary: {venue_list}. Each venue should connect to the user's cultural preferences."
    
    # Create taste mapping guidance
    taste_guidance = ""
    if taste_mapping:
        taste_details = []
        if isinstance(taste_mapping, dict):
            # Handle new organized format
            if taste_mapping.get('music_experiences'):
                for exp in taste_mapping['music_experiences']:
                    taste_details.append(f"Music preference connects to {exp.get('venue', '')}")
            if taste_mapping.get('film_experiences'):
                for exp in taste_mapping['film_experiences']:
                    taste_details.append(f"Film preference connects to {exp.get('venue', '')}")
            if taste_mapping.get('cuisine_experiences'):
                for exp in taste_mapping['cuisine_experiences']:
                    taste_details.append(f"Cuisine preference connects to {exp.get('venue', '')}")
        else:
            # Handle old format (fallback)
            for mapping in taste_mapping:
                taste_details.append(f"{mapping.get('category', '')} preference connects to {mapping.get('experience', '')}")
        
        if taste_details:
            taste_guidance = f"\nTASTE CONNECTIONS: {'; '.join(taste_details)}. Ensure each day's activities reflect these personal taste connections."
    
    prompt = f'''
    Create a {num_days}-day travel plan for {city}, {country} {date_str} with {vibe} theme.
    {weather_summary}{venue_guidance}{taste_guidance}

    CRITICAL: Generate exactly {num_days} days. Count carefully: Day 1, Day 2, ... Day {num_days}.
    CRITICAL: Each activity must clearly connect to the user's stated preferences. Explain WHY each venue/activity was chosen based on their tastes.

    For the BUDGET section:
    - Provide detailed, line-separated budget estimates for each of the following categories: accommodation, food, and activities.
    - For each category, provide as many relevant lines as possible (up to 12 lines per category) as a list of strings, each with a clear cost value and a short description, e.g.:
        ["Hotel XYZ: $120/night", "Boutique guesthouse: $85/night", ...]
    - Use numbers and currency consistently. If possible, break down costs by type, location, or time period.
    - Do NOT summarize as a single line; use a list of detailed lines for each budget category.

    Return ONLY valid JSON:
    {{
        "packing": {{"Clothing": ["item1", "item2"], "Electronics": ["smartphone", "charger"], "Documents": ["passport"], "Toiletries": ["item1"], "Other": ["item1"]}},
        "tips": ["tip1 for {city}", "tip2 for {city}", "tip3 for {city}"],
        "budget": {{"accommodation": ["Hotel XYZ: $120/night", "Boutique guesthouse: $85/night", ...], "food": ["Lunch at Cafe: $15", ...], "activities": ["Museum entry: $20", ...]}},
        "transport": ["transport1 in {city}", "transport2 in {city}"],
        "safety": ["safety1", "safety2", "safety3"],
        "closing": "personalized message",
        "itinerary": {{
            {itinerary_json}
        }}
    }}
    '''

    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    # Increase max_tokens for longer itineraries with venue details
    base_tokens = 1200
    venue_tokens = len(venues) * 20 if venues else 0
    day_tokens = num_days * 60  # More tokens per day for detailed explanations
    max_tokens = base_tokens + venue_tokens + day_tokens
    if max_tokens > 4000:
        max_tokens = 4000
    
    data = {
        "model": "mistralai/Mistral-7B-Instruct-v0.1",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.6
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        import json
        import re
        content = result['choices'][0]['message']['content'].strip()
        # Try to extract JSON from the response
        try:
            # If the model returns markdown, strip it
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()
            # Extract JSON from mixed text/JSON response
            elif '{' in content:
                start = content.find('{')
                # Find the last complete closing brace
                end = content.rfind('}')
                if end > start:
                    content = content[start:end+1]
                else:
                    content = content[start:]
            
            # Clean invalid control characters
            content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
            
            # Validate JSON completeness by counting braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                # Try to fix incomplete JSON by adding missing closing braces
                missing_braces = open_braces - close_braces
                content += '}' * missing_braces
            
            data = json.loads(content)
            
            # Limit packing items to 8 per category and truncate long text
            if 'packing' in data and isinstance(data['packing'], dict):
                for category, items in data['packing'].items():
                    if isinstance(items, list):
                        # Limit to 8 items and truncate text to 30 characters
                        data['packing'][category] = [item[:30] + '...' if len(item) > 30 else item for item in items[:8]]

            # Parse budget as lists of up to 12 lines for each category
            if 'budget' in data and isinstance(data['budget'], dict):
                for cat in ['accommodation', 'food', 'activities']:
                    val = data['budget'].get(cat, [])
                    if isinstance(val, str):
                        # Split by line or semicolon
                        lines = [line.strip() for line in re.split(r'[\n;]', val) if line.strip()]
                        data['budget'][cat] = lines[:12]
                    elif isinstance(val, list):
                        # Only keep up to 12 lines
                        data['budget'][cat] = [str(item).strip() for item in val[:12] if str(item).strip()]
                    else:
                        data['budget'][cat] = []

            return data
        except Exception as e:
            print(f"JSON parsing error: {e}")
            # fallback: return as text in all fields
            return {k: content for k in ['packing','tips','local_info','budget','transport','safety','closing','itinerary']}
    except Exception as e:
        return {k: f"Error: {str(e)}" for k in ['packing','tips','local_info','budget','transport','safety','closing','itinerary']}
