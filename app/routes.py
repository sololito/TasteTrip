from flask import Blueprint, render_template, request, send_file
from .geodb_api import get_taste_recommendations, get_city_info
from .qr_utils import generate_place_qr_codes
from .itinerary import generate_itinerary_and_sections
from .unsplash_api import get_image
from .weather_api import get_weather_forecast
from .maps_utils import google_maps_link
from .qr_utils import generate_qr_code
import io
import os
import re
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor

main = Blueprint('main', __name__)

@main.route('/qr')
def qr():
    from flask import request
    data = request.args.get('data')
    if not data:
        return 'Missing data', 400
    return generate_qr_code(data)

@main.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error loading homepage: {str(e)}"

import json


def try_parse_json(val):
    try:
        return json.loads(val)
    except Exception:
        return val

def parse_text_description(description):
    """Parse free text description to extract preferences using AI"""
    
    # Use Together.ai to extract structured data from text
    prompt = f'''
    Extract travel preferences from this description: "{description}"
    
    Be specific and extract actual names/types. Return ONLY valid JSON:
    {{
        "music": "specific artist, genre, or music style mentioned",
        "movie": "specific movie, director, or film genre mentioned", 
        "food": "specific cuisine type or food preference mentioned",
        "vibe": "travel mood: relaxing, adventurous, romantic, party, cultural, luxury, nature, historical"
    }}
    
    Examples:
    - "I love jazz and Italian food" → {{"music": "jazz", "movie": "", "food": "Italian", "vibe": "cultural"}}
    - "Beatles fan wanting French cuisine" → {{"music": "Beatles", "movie": "", "food": "French", "vibe": "cultural"}}
    '''
    
    try:
        import requests
        import os
        api_key = os.getenv('TOGETHER_API_KEY')
        
        response = requests.post(
            'https://api.together.xyz/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                'model': 'mistralai/Mistral-7B-Instruct-v0.1',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 150,
                'temperature': 0.1
            }
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            print(f"DEBUG: AI extracted content: {content}")
            
            # Extract JSON from response
            if '{' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end]
                parsed_data = json.loads(json_str)
                print(f"DEBUG: Parsed preferences: {parsed_data}")
                return parsed_data
    except Exception as e:
        print(f"Text parsing error: {e}")
    
    # Enhanced fallback - try simple keyword extraction
    description_lower = description.lower()
    
    # Simple keyword matching as fallback
    music_keywords = ['jazz', 'rock', 'pop', 'classical', 'beatles', 'elvis', 'mozart', 'hip-hop', 'reggae', 'country']
    movie_keywords = ['godfather', 'titanic', 'amélie', 'fellini', 'tarantino', 'scorsese', 'hitchcock', 'kubrick']
    food_keywords = ['italian', 'french', 'japanese', 'chinese', 'mexican', 'indian', 'thai', 'spanish', 'greek']
    
    extracted_music = next((keyword for keyword in music_keywords if keyword in description_lower), '')
    extracted_movie = next((keyword for keyword in movie_keywords if keyword in description_lower), '')
    extracted_food = next((keyword for keyword in food_keywords if keyword in description_lower), '')
    
    return {
        'music': extracted_music,
        'movie': extracted_movie,
        'food': extracted_food,
        'vibe': ''  # No hardcoded default, let downstream logic handle fallback
    }


@main.route('/itinerary', methods=['POST'])
def itinerary():
    # Step 1: Collect user input
    input_type = request.form.get('input_type', 'structured')
    
    # Calculate days from start and end dates minus 2 travel days
    start_date = request.form.get('start_date', '')
    end_date = request.form.get('end_date', '')
    
    try:
        from datetime import datetime
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        total_days = (end - start).days + 1
        activity_days = max(1, total_days - 2)  # Subtract 2 travel days, minimum 1 day
    except Exception:
        activity_days = 3  # Default fallback
    
    # Parse text description using AI
    trip_description = request.form.get('trip_description', '')
    user_input = parse_text_description(trip_description)
    user_input.update({
        "days": str(activity_days),
        "departure_city": request.form.get('departure_city', ''),
        "start_date": start_date,
        "end_date": end_date
    })

    # Step 2: Get taste-based city recommendation (Qloo -> Together AI)
    taste_data = get_taste_recommendations(user_input)

    # Step 3: Weather forecast (fetch only if journey is within 7 days from today)
    from datetime import datetime, timedelta
    current_date = datetime.now()
    weather = []
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days_until_start = (start - current_date).days
        trip_days = (end - start).days + 1
        forecast_days = min(trip_days, 7)
        # Only fetch weather if journey starts within 7 days from today
        if 0 <= days_until_start < 7:
            weather = get_weather_forecast(taste_data["city"], days=forecast_days)
    except Exception:
        weather = []
    if not weather:
        weather = []
    # Step 4: Generate AI-powered itinerary and sections with weather
    # Ensure days parameter and venues are passed to AI generation
    taste_data_with_days = taste_data.copy()
    taste_data_with_days['days'] = str(activity_days)
    taste_data_with_days['venues'] = taste_data.get('venues', [])
    taste_data_with_days['taste_mapping'] = taste_data.get('taste_mapping', [])
    ai_sections = generate_itinerary_and_sections(taste_data_with_days, weather=weather)

    # Step 5: Get city image (Unsplash)
    city_image = get_image(taste_data["city"])
    # print(f"Image URL for {taste_data['city']}: {city_image}")

    # Step 6: Additional info and summary - use venues from taste data for consistency
    city_info = get_city_info(taste_data["city"], taste_data.get('venues', []))
    taste_summary = f"You love {user_input.get('music', 'various')} music, movies like {user_input.get('movie', 'various genres')}, and delicious {user_input.get('food', 'cuisine')} food."

    # Step 7: Get places and generate QR codes for navigation
    places = city_info.get('places', []) if city_info else []
    maps_links = [google_maps_link(place, taste_data["city"]) for place in places]
    
    # Generate QR codes as URLs instead of BytesIO objects
    place_qr_codes = {place: f"/qr?data={google_maps_link(place, taste_data['city'])}" for place in places}

    # Packing checklist is now provided by the AI and always includes all electronics and is categorized by season.

    # All cultural data now comes from AI - no hardcoded fallbacks

    # Remove all static fallback blocks (budget, transport, safety, closing) after AI integration.
    # The following block is now obsolete and causes indentation/syntax errors. All values are now from ai_sections.
    # --- END OF FUNCTION ---
    # --- Packing List Normalization ---
    import json
    def robust_json_parse(val):
        tries = 0
        while isinstance(val, str) and tries < 2:
            try:
                val = json.loads(val)
            except Exception:
                break
            tries += 1
        return val

    def categorize_flat_packing(flat_list):
        # Simple categorization based on keywords with text cleaning
        def clean_packing_item(item):
            if not isinstance(item, str):
                return str(item)
            fixes = {'rncoat': 'raincoat', 'rn jacket': 'rain jacket', 'chrgr': 'charger'}
            for wrong, correct in fixes.items():
                item = item.replace(wrong, correct)
            return re.sub(r'\s+', ' ', item).strip()
        
        categories = {
            'Clothing': [],
            'Accessories': [],
            'Toiletries': [],
            'Electronics': [],
            'Documents': [],
            'Other': []
        }
        for item in flat_list:
            clean_item = clean_packing_item(item)
            lower = clean_item.lower()
            if any(word in lower for word in ['shirt', 'short', 'dress', 'jacket', 'shoes', 'pants', 'swim', 'sock', 'clothing']):
                categories['Clothing'].append(clean_item)
            elif any(word in lower for word in ['hat', 'sunglass', 'belt', 'scarf', 'glove', 'accessor']):
                categories['Accessories'].append(clean_item)
            elif any(word in lower for word in ['tooth', 'shampoo', 'soap', 'toiletr', 'deodorant', 'sunscreen']):
                categories['Toiletries'].append(clean_item)
            elif any(word in lower for word in ['charger', 'adapter', 'phone', 'camera', 'electronic', 'laptop', 'tablet']):
                categories['Electronics'].append(clean_item)
            elif any(word in lower for word in ['passport', 'visa', 'document', 'id', 'insurance']):
                categories['Documents'].append(clean_item)
            else:
                categories['Other'].append(clean_item)
        return {cat: items for cat, items in categories.items() if items}

    packing_section = ai_sections.get('packing', {})
    packing_list = robust_json_parse(packing_section)
    # If the AI returns a dict with a single 'packing' key, extract its value
    if isinstance(packing_list, dict) and set(packing_list.keys()) == {'packing'}:
        packing_list = packing_list['packing']
    if not isinstance(packing_list, (dict, list)):
        packing_list = []
    # If packing_list is a flat list, categorize it
    if isinstance(packing_list, list):
        packing_list = categorize_flat_packing(packing_list)

    # --- Normalize packing, tips, budget, transport for template ---
    def normalize_json_section(section):
        if isinstance(section, str):
            parsed = try_parse_json(section)
            return parsed if isinstance(parsed, (dict, list)) else section
        return section

    packing_list = normalize_json_section(ai_sections.get('packing', {}))
    tips = normalize_json_section(ai_sections.get('tips', {}))
    budget = normalize_json_section(ai_sections.get('budget', {}))
    transport = normalize_json_section(ai_sections.get('transport', {}))

    def categorize_flat_packing(flat_list):
        # Simple categorization based on keywords
        categories = {
            'Clothing': [],
            'Accessories': [],
            'Toiletries': [],
            'Electronics': [],
            'Documents': [],
            'Other': []
        }
        for item in flat_list:
            lower = item.lower()
            if any(word in lower for word in ['shirt', 'short', 'dress', 'jacket', 'shoes', 'pants', 'swim', 'sock', 'clothing']):
                categories['Clothing'].append(item)
            elif any(word in lower for word in ['hat', 'sunglass', 'belt', 'scarf', 'glove', 'accessor']):
                categories['Accessories'].append(item)
            elif any(word in lower for word in ['tooth', 'shampoo', 'soap', 'toiletr', 'deodorant', 'sunscreen']):
                categories['Toiletries'].append(item)
            elif any(word in lower for word in ['charger', 'adapter', 'phone', 'camera', 'electronic', 'laptop', 'tablet']):
                categories['Electronics'].append(item)
            elif any(word in lower for word in ['passport', 'visa', 'document', 'id', 'insurance']):
                categories['Documents'].append(item)
            else:
                categories['Other'].append(item)
        # Remove empty categories
        return {cat: items for cat, items in categories.items() if items}

    # If packing_list is a flat list, categorize it
    if isinstance(packing_list, list):
        packing_list = categorize_flat_packing(packing_list)

    # Ensure itinerary is always a dict for the template
    itinerary_data = ai_sections.get('itinerary', {})
    if isinstance(itinerary_data, str):
        try:
            itinerary_data = json.loads(itinerary_data)
        except Exception:
            itinerary_data = {}
    # If itinerary_data is a dict with a single 'itinerary' key, extract its value
    if isinstance(itinerary_data, dict) and set(itinerary_data.keys()) == {'itinerary'}:
        itinerary_data = itinerary_data['itinerary']
    if not isinstance(itinerary_data, dict):
        itinerary_data = {}

    def robust_json_parse(val):
        tries = 0
        while isinstance(val, str) and tries < 3:
            try:
                val = json.loads(val)
            except Exception:
                break
            tries += 1
        return val

    # Recursively robustly parse all AI sections
    sections = {}
    for key in ['packing','tips','budget','transport','safety','closing','itinerary']:
        sections[key] = robust_json_parse(ai_sections.get(key, {}))

    # Get packing data directly from sections
    packing = sections.get('packing', {})

    # Special handling for itinerary: if list, convert to dict
    itinerary_data = sections['itinerary']
    if isinstance(itinerary_data, list):
        itinerary_data = {f"Day {i+1}": v for i, v in enumerate(itinerary_data)}
    elif isinstance(itinerary_data, dict) and set(itinerary_data.keys()) == {'itinerary'}:
        itinerary_data = itinerary_data['itinerary']
    if not isinstance(itinerary_data, dict):
        itinerary_data = {}

    # Clean itinerary structure with text cleaning
    def clean_text_content(text):
        """Clean text content to prevent parsing issues"""
        if not isinstance(text, str):
            return str(text)
        # Apply same cleaning as clean_section but lighter
        word_fixes = {
            'rncoat': 'raincoat', 'rn ': 'rain ', 'ecnomy': 'economy', 'ecnomic': 'economic',
            'trvl': 'travel', 'trvel': 'travel', 'accomodation': 'accommodation',
            'restarant': 'restaurant', 'resturant': 'restaurant', 'transprt': 'transport'
        }
        for wrong, correct in word_fixes.items():
            text = text.replace(wrong, correct)
        return re.sub(r'\s+', ' ', text).strip()
    
    cleaned_itinerary = {}
    for day, schedule in itinerary_data.items():
        if isinstance(schedule, dict):
            valid_schedule = {}
            for period in ['morning', 'afternoon', 'evening']:
                if period in schedule and schedule[period]:
                    valid_schedule[period] = clean_text_content(schedule[period])
            cleaned_itinerary[day] = valid_schedule if valid_schedule else {'all_day': 'No activities planned'}
        else:
            cleaned_itinerary[day] = {'all_day': clean_text_content(schedule) if schedule else 'No activities planned'}

    # Debug packing data
    print(f"Raw packing from AI: {packing}")
    print(f"Type of packing: {type(packing)}")
    
    # Use robustly parsed sections for all template variables
    packing_list = packing
    tips = sections['tips']
    budget = sections['budget']
    transport = sections['transport']
    tags = sections['safety']
    closing = sections['closing']
    
    print(f"Final packing_list: {packing_list}")
    print(f"Type of packing_list: {type(packing_list)}")
    
    # Debug safety tags
    print(f"Raw safety from AI: {sections.get('safety', 'MISSING')}")
    print(f"Final tags: {tags}")
    print(f"Type of tags: {type(tags)}")

    # Get Qloo branding info
    from .qloo_api import get_qloo_branding_info
    qloo_info = get_qloo_branding_info()
    
    # Enhanced places list - use venues from Qloo if available, otherwise use city_info places
    enhanced_places = taste_data.get('venues', places) if taste_data.get('venues') else places
    enhanced_maps_links = [google_maps_link(place, taste_data["city"]) for place in enhanced_places]
    enhanced_qr_codes = {place: f"/qr?data={google_maps_link(place, taste_data['city'])}" for place in enhanced_places}
    
    # Debug output for verification
    print(f"Enhanced places from Qloo venues: {len(enhanced_places)} venues")
    print(f"Taste mapping data: {len(taste_data.get('taste_mapping', []))} mappings")
    print(f"Taste mapping content: {taste_data.get('taste_mapping', [])}")
    print(f"Template will receive taste_mapping: {taste_data.get('taste_mapping', [])}")
    
    return render_template(
        "itinerary.html",
        city_info=city_info,
        reason=taste_data.get("reason", ""),
        summary=taste_summary,
        image=city_image,
        places=enhanced_places,
        maps_links=enhanced_maps_links,
        place_qr_codes=enhanced_qr_codes,
        packing_list=packing_list,
        tips=tips,
        budget=budget,
        transport=transport,
        tags=tags,
        closing=str(closing)[:500] if closing else '',
        itinerary=itinerary_data,
        weather=weather,

        start_date=user_input["start_date"],
        end_date=user_input["end_date"],
        qloo_info=qloo_info,
        qloo_powered=taste_data.get('qloo_powered', True),
        taste_mapping=taste_data.get('taste_mapping', []),
        venues_count=len(enhanced_places),
        user_preferences={
            'music': user_input.get('music', ''),
            'movie': user_input.get('movie', ''),
            'food': user_input.get('food', ''),
            'days': user_input.get('days', '3')
        }
    )

@main.route('/get_flight_estimate', methods=['POST'])
def get_flight_estimate_api():
    data = request.get_json()
    departure = data.get('departure', 'Nairobi')
    destination = data.get('destination', 'Barcelona')
    month = data.get('month', '')
    
    from .itinerary import get_flight_estimate_with_sites
    price, sites = get_flight_estimate_with_sites(departure, destination, month)
    
    return {'price': price, 'sites': sites}

@main.route('/download_pdf', methods=['POST'])
def download_pdf():
    content = request.form.get('content', '')
    image_url = request.form.get('image_url', '')
    city_name = request.form.get('city_name', 'Destination')
    departure_city = request.form.get('departure_city', '')
    user_name = request.form.get('user_name', 'Traveler')
    start_date = request.form.get('start_date', '')
    end_date = request.form.get('end_date', '')

    # Clean and prepare text
    import re
    def clean_section(text):
        if not isinstance(text, str):
            return text
        # Remove asterisks, markdown headers, and 'AI' markers
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#\s*', '', text)
        text = text.replace('AI', '').replace('ai', '')
        # Remove AI translation artifacts
        text = re.sub(r'"[^"]*"\s*,\s*[^"]*"[^"]*"', '', text)  # Remove quoted translations
        text = re.sub(r'The English translation of "[^"]*" is "([^"]*)"\.?', r'\1', text)  # Extract translation
        text = re.sub(r'"([^"]*)",\s*[^"]*"[^"]*"', r'\1', text)  # Clean quoted names
        text = re.sub(r'"([^"]*)"\.', r'\1', text)  # Remove quotes and periods
        
        # Fix common word parsing errors
        word_fixes = {
            'rncoat': 'raincoat', 'rn ': 'rain ', 'ecnomy': 'economy', 'ecnomic': 'economic',
            'trvl': 'travel', 'trvel': 'travel', 'accomodation': 'accommodation',
            'restarant': 'restaurant', 'resturant': 'restaurant', 'transprt': 'transport',
            'airprt': 'airport', 'htl': 'hotel', 'bkng': 'booking', 'flght': 'flight'
        }
        for wrong, correct in word_fixes.items():
            text = text.replace(wrong, correct)
        
        # Fix common word breaks and spacing issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # camelCase to spaced
        text = re.sub(r'([a-z])(\d)', r'\1 \2', text)  # letter+number
        text = re.sub(r'(\d)([a-z])', r'\1 \2', text)  # number+letter
        
        # Fix broken words at line boundaries
        text = re.sub(r'([a-z])\s+([a-z]{1,3})\s+([a-z])', lambda m: 
                     m.group(1) + m.group(2) + m.group(3) if len(m.group(2)) <= 2 else m.group(0), text)
        
        return text.strip()
    clean_content = clean_section(content)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Enhanced color scheme
    primary_color = HexColor('#008080')  # Teal
    accent_color = HexColor('#FFCC00')   # Golden yellow
    text_color = HexColor('#333333')     # Dark gray
    secondary_text = HexColor('#666666') # Light gray
    background_gray = HexColor('#F8F9FA') # Light background
    header_color = primary_color         # Use primary color for headers
    
    y = height - 40
    
    # Register fonts for better typography
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        # Use built-in fonts with better styling
        pdf.setFont("Helvetica", 12)  # Default font
    except Exception:
        pass

    # --- ENHANCED COVER PAGE ---
    # Background accent bar
    pdf.setFillColor(background_gray)
    pdf.rect(0, height - 100, width, 100, fill=1)
    
    # Project logo + Qloo logo in upper right
    try:
        logo_path = os.path.join(os.path.dirname(__file__), '../static/images/logo.png')
        logo_reader = ImageReader(logo_path)
        logo_width = 80
        logo_height = 80
        pdf.drawImage(logo_reader, width - 120, y - logo_height + 20, width=logo_width, height=logo_height, mask='auto')
    except Exception as e:
        print(f"Failed to load logo for PDF: {e}")
    
    # Main title with modern typography
    pdf.setFont("Helvetica-Bold", 32)
    pdf.setFillColor(primary_color)
    pdf.drawCentredString(width // 2, y, f"Your Trip to {city_name}")
    y -= 45
    
    # Subtitle
    pdf.setFont("Helvetica", 16)
    pdf.setFillColor(secondary_text)
    pdf.drawCentredString(width // 2, y, "Curated by Taste AI · Powered by Qloo")
    y -= 35
    
    # Enhanced Qloo branding
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(accent_color)
    pdf.drawCentredString(width // 2, y, "🧠 Advanced Cultural Intelligence")
    y -= 20
    pdf.setFont("Helvetica-Oblique", 11)
    pdf.setFillColor(text_color)
    pdf.drawCentredString(width // 2, y, "Connecting your personal tastes to perfect travel destinations")
    y -= 40
    
    # City name
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(accent_color)
    pdf.drawCentredString(width // 2, y, city_name)
    y -= 30
    
    # User info
    pdf.setFont("Helvetica", 14)
    pdf.setFillColor(text_color)
    pdf.drawCentredString(width // 2, y, f"Prepared for: {user_name}")
    y -= 22
    if start_date and end_date:
        pdf.setFont("Helvetica-Oblique", 12)
        pdf.setFillColor(text_color)
        pdf.drawCentredString(width // 2, y, f"Trip Dates: {start_date} to {end_date}")
        y -= 18
    # Insert city hero image (large and visually dominant)
    if image_url and not image_url.endswith("logo.png"):
        try:
            img_response = requests.get(image_url)
            if img_response.status_code == 200:
                img_reader = ImageReader(io.BytesIO(img_response.content))
                image_height = 320
                image_width = width - 80
                pdf.drawImage(img_reader, 40, y - image_height, width=image_width, height=image_height, preserveAspectRatio=True)
                y -= image_height + 30
        except Exception as e:
            print(f"Failed to load image for PDF: {e}")
    pdf.setFont("Helvetica-Oblique", 13)
    pdf.setFillColor(accent_color)
    pdf.drawCentredString(width // 2, y, "Your personalized cultural adventure awaits!")
    y -= 30
    pdf.showPage()
    y = height - 40

    # --- FEATURE SECTIONS ---
    from .maps_utils import google_maps_link
    # Get all data from form with better handling
    import json
    try:
        places_raw = request.form.get('places', '[]')
        places = json.loads(places_raw) if places_raw and places_raw != '[]' else []
        
        description = request.form.get('city_description', '') or f"{city_name} is a vibrant cultural destination."
        
        weather_data_raw = request.form.get('weather', '[]')
        weather_data = json.loads(weather_data_raw) if weather_data_raw and weather_data_raw != '[]' else []
        
        summary = request.form.get('summary', '') or "Your cultural preferences have been carefully analyzed for this personalized recommendation."
        
        print(f"PDF Debug - Places: {len(places)}, Weather: {len(weather_data)}, Summary: {len(summary)}")
    except Exception as e:
        print(f"PDF Data parsing error: {e}")
        places = []
        description = f"{city_name} is a vibrant cultural destination."
        weather_data = []
        summary = "Your cultural preferences have been carefully analyzed for this personalized recommendation."

    # Improved text wrapping function with better alignment
    def wrap_text(text, max_width, font_size=11):
        pdf.setFont("Helvetica", font_size)
        words = str(text).split()
        lines = []
        current_line = ""
        
        for word in words:
            # Handle long words that exceed max width
            if pdf.stringWidth(word) > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                # Break long word
                while len(word) > 0:
                    char_count = 0
                    temp_word = ""
                    for char in word:
                        if pdf.stringWidth(temp_word + char) <= max_width:
                            temp_word += char
                            char_count += 1
                        else:
                            break
                    lines.append(temp_word)
                    word = word[char_count:]
            else:
                test_line = current_line + (" " if current_line else "") + word
                if pdf.stringWidth(test_line) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
        if current_line:
            lines.append(current_line)
        return lines
    
    # --- ENHANCED DESTINATION OVERVIEW ---
    # Section header with icon
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(primary_color)
    pdf.drawString(40, y, f"🌍 Destination Overview: {city_name}")
    y -= 25
    
    # 2-column layout: Left - description, Right - image space
    col_width = (width - 120) // 2
    
    if description:
        desc_lines = wrap_text(description, col_width - 20)
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        for line in desc_lines[:5]:  # Max 5 lines
            pdf.drawString(60, y, line)
            y -= 13
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, f"{city_name} is a vibrant cultural destination.")
        y -= 13
    
    # "Why This City?" highlight box with reason content
    reason_text = request.form.get('reason', '')
    if reason_text:
        box_y = y - 10
        pdf.setFillColor(primary_color)
        pdf.rect(40, box_y - 25, width - 80, 30, fill=1)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(HexColor('#FFFFFF'))
        pdf.drawString(50, box_y - 15, "Why This City?")
        y = box_y - 35
        
        # Clean and wrap reason text
        clean_reason = re.sub(r'\s+', ' ', reason_text.replace('\n', ' ')).strip()
        reason_lines = wrap_text(clean_reason, width - 120, 10)
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for line in reason_lines[:6]:  # Max 6 lines for reason
            pdf.drawString(60, y, line)
            y -= 12
        y -= 15
    
    # --- ENHANCED CULTURAL PREFERENCES SECTION ---
    taste_mapping_raw = request.form.get('taste_mapping', '[]')
    try:
        taste_mapping = json.loads(taste_mapping_raw) if taste_mapping_raw else []
    except Exception:
        taste_mapping = []
    
    if taste_mapping and isinstance(taste_mapping, list):
        pdf.setFont("Helvetica-Bold", 16)
        pdf.setFillColor(primary_color)
        pdf.drawString(40, y, u"\U0001F3B5 Your Cultural DNA")
        y -= 25
        
        # Add preference icons and headers
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(accent_color)
        pdf.drawString(50, y, u"\U0001F3B5 Music \u2022 \U0001F3AC Film \u2022 \U0001F37D Cuisine \u2022 \U0001F9ED Travel Vibe")
        y -= 20
        
        # Table headers with better spacing
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(header_color)
        pdf.drawString(50, y, "Category")
        pdf.drawString(120, y, "Preference")
        pdf.drawString(220, y, "Cultural Path")
        pdf.drawString(400, y, "Experience")
        y -= 16
        
        # Table rows with proper text wrapping to ensure alignment
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(text_color)
        for mapping in taste_mapping[:3]:
            row_start_y = y
            
            # Category (emoji + text)
            category = str(mapping.get('category', ''))
            pdf.drawString(50, y, category[:15])
            
            # Preference with wrapping
            preference = str(mapping.get('preference', '')).replace('AI', '').replace('ai', '').strip()
            pref_lines = wrap_text(preference, 90, 9)
            for i, line in enumerate(pref_lines[:2]):
                pdf.drawString(120, y - (i * 12), line)
            
            # Cultural Path with wrapping
            cultural_path = str(mapping.get('cultural_path', '')).replace('AI', '').replace('ai', '').strip()
            path_lines = wrap_text(cultural_path, 170, 9)
            for i, line in enumerate(path_lines[:2]):
                pdf.drawString(220, y - (i * 12), line)
            
            # Experience with wrapping
            experience = str(mapping.get('experience', '')).replace('AI', '').replace('ai', '').strip()
            exp_lines = wrap_text(experience, 140, 9)
            for i, line in enumerate(exp_lines[:2]):
                pdf.drawString(400, y - (i * 12), line)
            
            # Calculate row height based on max lines
            max_lines = max(len(pref_lines[:2]), len(path_lines[:2]), len(exp_lines[:2]))
            y -= (max_lines * 12) + 8
        
        y -= 10

    # Weather Forecast section
    if y < 100:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\u2600 Weather Forecast:")
    y -= 18
    
    if weather_data and len(weather_data) > 0:
        # Weather table header
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(header_color)
        pdf.drawString(60, y, "Date")
        pdf.drawString(150, y, "Condition")
        pdf.drawString(280, y, "Temperature")
        y -= 16
        
        # Weather data rows
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for day in weather_data[:7]:  # Show up to 7 days
            pdf.drawString(60, y, str(day.get('date', 'N/A')))
            pdf.drawString(150, y, str(day.get('desc', 'N/A'))[:18])
            pdf.drawString(280, y, f"{day.get('temp', 'N/A')}°C")
            y -= 13
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, f"Weather forecast for {city_name} will be available closer to your travel dates.")
        y -= 14
    y -= 20
    
    # Your Taste Summary section
    if y < 80:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\U0001F3B5 Your Taste Summary:")
    y -= 18
    
    summary_lines = wrap_text(summary, width - 100, 11)
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    for line in summary_lines[:3]:  # Max 3 lines
        pdf.drawString(60, y, line)
        y -= 14
    y -= 15

    # Packing checklist (AI) - Enhanced formatting
    if y < 150:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(accent_color)
    pdf.drawString(40, y, u"\U0001F392 Packing Checklist:")
    y -= 16
    
    packing_list_raw = request.form.get('packing_list', '{}')
    try:
        packing_list = json.loads(packing_list_raw) if isinstance(packing_list_raw, str) else packing_list_raw
    except Exception:
        packing_list = {}
    
    if isinstance(packing_list, dict) and packing_list:
        for category, items in packing_list.items():
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColor(header_color)
            pdf.drawString(50, y, f"{category}:")
            y -= 14
            
            if isinstance(items, list):
                pdf.setFont("Helvetica", 10)
                pdf.setFillColor(text_color)
                for item in items[:8]:  # More items per category
                    item_text = clean_section(str(item))
                    # Additional cleaning for packing items
                    item_text = item_text.replace('rn ', 'rain ').replace('ecnomy', 'economy')
                    # Wrap long items
                    if len(item_text) > 60:
                        item_lines = wrap_text(item_text, width - 140, 10)
                        for line in item_lines[:2]:  # Max 2 lines per item
                            pdf.drawString(70, y, f"• {line}" if line == item_lines[0] else f"  {line}")
                            y -= 11
                    else:
                        pdf.drawString(70, y, f"• {item_text}")
                        y -= 11
            y -= 8
    elif isinstance(packing_list, list) and packing_list:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for item in packing_list[:20]:  # More items
            pdf.drawString(60, y, f"• {clean_section(str(item))}")
            y -= 11
    y -= 15



    # Budget section (AI)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\U0001F4B0 Budget Estimates (Daily):")
    y -= 16
    budget_raw = request.form.get('budget', '{}')
    try:
        budget = json.loads(budget_raw) if isinstance(budget_raw, str) else budget_raw
    except Exception:
        budget = {}
    
    if isinstance(budget, dict) and budget:
        # Create budget table
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(header_color)
        pdf.drawString(60, y, "Category")
        pdf.drawString(160, y, "Estimate")
        y -= 14
        
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        for category, amount in budget.items():
            pdf.drawString(60, y, category.capitalize())
            pdf.drawString(160, y, clean_section(str(amount)))
            y -= 13
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, "Budget estimates unavailable.")
        y -= 13
    y -= 10


    # Flight Estimates section
    if y < 120:
        pdf.showPage()
        y = height - 40
    from datetime import datetime
    from .itinerary import get_flight_estimate
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(accent_color)
    pdf.drawString(40, y, u"\u2708 Flight Estimates:")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    
    if start_date:
        try:
            dt_obj = datetime.strptime(start_date, "%Y-%m-%d")
            month_year = dt_obj.strftime('%B %Y')
        except Exception:
            month_year = datetime.now().strftime('%B %Y')
    else:
        month_year = datetime.now().strftime('%B %Y')
    
    # Get flight estimate from webpage data or generate new one
    flight_estimate_raw = request.form.get('flight_estimate', '')
    try:
        if flight_estimate_raw:
            flight_data = json.loads(flight_estimate_raw)
            price = flight_data.get('price', 'Contact travel agent for pricing')
            sites = flight_data.get('sites', ['Skyscanner', 'Kayak', 'Expedia'])
        else:
            from .itinerary import get_flight_estimate
            flight_price, flight_summary = get_flight_estimate(departure_city, city_name, month_year)
            if flight_price:
                price = f"${int(flight_price)} USD"
            else:
                price = "Contact travel agent for pricing"
            sites = ["Skyscanner", "Kayak", "Expedia"]
    except Exception as e:
        print(f"Flight estimate error in PDF: {e}")
        price = "Contact travel agent for pricing"
        sites = ["Skyscanner", "Kayak", "Expedia"]
    
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(text_color)
    pdf.drawString(60, y, f"Estimated Round-trip Cost: {price}")
    y -= 16
    
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(text_color)
    pdf.drawString(60, y, "Best Booking Sites:")
    y -= 12
    
    for site in sites[:3]:
        pdf.drawString(70, y, f"• {site}")
        y -= 11
    
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColor(text_color)
    pdf.drawString(60, y, "Tip: Book 2-3 months in advance for best prices.")
    y -= 20

    # Travel Essentials Section
    if y < 150:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\U0001F9F3 Travel Essentials:")
    y -= 20
    
    # Tips
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"\U0001F4A1 Travel Tips:")
    y -= 14
    
    tips_raw = request.form.get('tips', '[]')
    try:
        tips = json.loads(tips_raw) if isinstance(tips_raw, str) else tips_raw
    except Exception:
        tips = []
    
    if isinstance(tips, list) and tips:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for tip in tips[:8]:
            tip_text = clean_section(str(tip))
            tip_lines = wrap_text(tip_text, width - 140, 10)
            
            for i, line in enumerate(tip_lines[:3]):
                prefix = "• " if i == 0 else "  "
                pdf.drawString(70, y, f"{prefix}{line}")
                y -= 11
            y -= 3
    y -= 10
    
    # Transport Options
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"\U0001F698 Transport Options:")
    y -= 14
    
    transport_raw = request.form.get('transport', '[]')
    try:
        transport = json.loads(transport_raw) if isinstance(transport_raw, str) else transport_raw
    except Exception:
        transport = []
    
    if isinstance(transport, list) and transport:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for option in transport[:8]:
            option_text = clean_section(str(option))
            option_lines = wrap_text(option_text, width - 140, 10)
            
            for i, line in enumerate(option_lines[:2]):
                prefix = "• " if i == 0 else "  "
                pdf.drawString(70, y, f"{prefix}{line}")
                y -= 11
            y -= 3
    y -= 10
    
    # Safety & Accessibility
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"\U0001F6E1 Safety & Accessibility:")
    y -= 14
    
    tags_raw = request.form.get('tags', '[]')
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except Exception:
        tags = []
    
    if isinstance(tags, list) and tags:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        for tag in tags[:8]:
            tag_text = clean_section(str(tag))
            tag_lines = wrap_text(tag_text, width - 140, 10)
            
            for i, line in enumerate(tag_lines[:2]):
                prefix = "• " if i == 0 else "  "
                pdf.drawString(70, y, f"{prefix}{line}")
                y -= 11
            y -= 3
    y -= 15

    # Closing message
    closing = clean_section(request.form.get('closing', ''))
    if closing:
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(accent_color)
        pdf.drawString(40, y, u"\U0001F680 Final Message:")
        y -= 16
        
        closing_lines = wrap_text(closing, width - 100, 11)
        pdf.setFont("Helvetica-Oblique", 11)
        pdf.setFillColor(text_color)
        for line in closing_lines[:4]:
            pdf.drawString(60, y, line)
            y -= 13
        y -= 15
    
    # Recommended Places to Visit section
    if y < 150:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\U0001F4CD Recommended Places to Visit:")
    y -= 20
    
    if places and len(places) > 0 and any(str(place).strip() for place in places):
        for i, place in enumerate(places[:8]):
            place_start_y = y
            
            pdf.setFont("Helvetica", 11)
            pdf.setFillColor(text_color)
            place_text = f"{i+1}. {str(place)}"
            
            place_lines = wrap_text(place_text, width - 120, 11)
            for line in place_lines[:2]:
                pdf.drawString(60, y, line)
                y -= 13
            
            try:
                from .maps_utils import google_maps_link
                from .qr_utils import generate_qr_image_data
                
                link = google_maps_link(place, city_name)
                qr_buf = generate_qr_image_data(link)
                img_reader = ImageReader(qr_buf)
                
                qr_x = width - 70
                qr_y = place_start_y - 35
                pdf.drawImage(img_reader, qr_x, qr_y, width=35, height=35, preserveAspectRatio=True, mask='auto')
                
                pdf.setFont("Helvetica", 7)
                pdf.setFillColor(accent_color)
                pdf.drawString(qr_x + 8, qr_y - 10, "Scan")
                
            except Exception as e:
                print(f"QR code error for {place}: {e}")
            
            y -= 10
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, "No recommended places available for this destination.")
        y -= 14
    
    y -= 20

    # Itinerary section
    if y < 200:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColor(primary_color)
    pdf.drawCentredString(width // 2, y, u"\U0001F4C5 Your Day-by-Day Itinerary")
    y -= 35
    
    itinerary_raw = request.form.get('itinerary', '{}')
    try:
        itinerary = json.loads(itinerary_raw) if isinstance(itinerary_raw, str) else itinerary_raw
    except Exception:
        itinerary = {}
    
    if isinstance(itinerary, dict) and itinerary:
        sorted_days = sorted(itinerary.items(), key=lambda x: int(x[0].split()[-1]) if x[0].startswith('Day') and x[0].split()[-1].isdigit() else 999)
        
        for day, schedule in sorted_days:
            if y < 120:
                pdf.showPage()
                y = height - 40
            
            pdf.setFillColor(accent_color)
            pdf.rect(35, y - 5, width - 70, 25, fill=1)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.setFillColor(HexColor('#000000'))
            pdf.drawString(45, y, f"{day}")
            y -= 30
            
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(text_color)
            
            if isinstance(schedule, dict):
                period_order = ['morning', 'afternoon', 'evening']
                for period in period_order:
                    if period in schedule and schedule[period] and str(schedule[period]).strip():
                        if y < 80:
                            pdf.showPage()
                            y = height - 40
                        
                        pdf.setFont("Helvetica-Bold", 10)
                        pdf.setFillColor(accent_color)
                        pdf.drawString(50, y, f"{period.capitalize()}:")
                        y -= 12
                        
                        activity_text = clean_section(str(schedule[period]))
                        activity_lines = wrap_text(activity_text, width - 140, 10)
                        
                        pdf.setFont("Helvetica", 10)
                        pdf.setFillColor(text_color)
                        for line in activity_lines[:3]:
                            if y < 60:
                                pdf.showPage()
                                y = height - 40
                            pdf.drawString(70, y, line)
                            y -= 11
                        y -= 5
            else:
                pdf.drawString(50, y, clean_section(str(schedule)))
                y -= 13
            y -= 15
    else:
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(text_color)
        pdf.drawString(50, y, "No detailed itinerary available.")
        y -= 20
    
    # Final Note
    killer_note = request.form.get('killer_note', '').replace('{{ city_info.name }}', city_name)
    if killer_note:
        if y < 120:
            pdf.showPage()
            y = height - 40
        
        pdf.setFont("Helvetica-Bold", 14)
        pdf.setFillColor(accent_color)
        pdf.drawString(40, y, u"\U0001F31F Your Cultural Journey Awaits")
        y -= 18
        
        killer_lines = wrap_text(killer_note, width - 100, 11)
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        for line in killer_lines[:6]:
            if y < 60:
                pdf.showPage()
                y = height - 40
            pdf.drawString(60, y, line)
            y -= 14
        y -= 20
    
    # Final message
    if y < 120:
        pdf.showPage()
        y = height - 40
    
    pdf.setFont("Helvetica-Oblique", 13)
    pdf.setFillColor(accent_color)
    pdf.drawString(40, y, u"\U0001F680 Safe travels and enjoy your adventure!")
    y -= 50

    # Attribution
    pdf.setFillColor(background_gray)
    pdf.rect(40, y - 80, width - 80, 100, fill=1)
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(primary_color)
    pdf.drawString(60, y - 25, u"\U0001F3AF Powered by Qloo's Taste AI\u2122")
    
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    attribution_text = "This personalized itinerary was created using Qloo's advanced cultural intelligence that connects your unique taste profile to perfect travel destinations and experiences."
    attribution_lines = wrap_text(attribution_text, width - 120, 11)
    
    current_y = y - 45
    for line in attribution_lines[:4]:
        pdf.drawString(60, current_y, line)
        current_y -= 14
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="taste_trip_itinerary.pdf", mimetype='application/pdf')
