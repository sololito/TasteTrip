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
    city = taste_data.get('city', '')

    # Step 3: Weather forecast (fetch only if journey is within 7 days from today)
    from datetime import datetime, timedelta
    current_date = datetime.now()
    weather = []
    if city and start_date:
        today = datetime.now().date()
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            if (start - today).days > 7:
                # Out of range: show empty or N/A
                weather = []
            else:
                forecast = get_weather_forecast(city, days=7)
                # Build 6-day weather starting from start_date
                weather_by_date = {d.get('date', ''): d for d in forecast}
                weather = []
                for i in range(6):
                    day_str = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                    day_data = weather_by_date.get(day_str)
                    if day_data:
                        weather.append(day_data)
                    else:
                        weather.append({'date': day_str, 'desc': 'N/A', 'temp': 'N/A'})
        except Exception as e:
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

    # Packing List Normalization
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
            for wrong, right in fixes.items():
                item = item.replace(wrong, right)
            return item
        
        categories = {
            'Clothing': [],
            'Electronics': [],
            'Documents': [],
            'Personal Care': [],
            'Other': []
        }
        
        for item in flat_list:
            item = clean_packing_item(item)
            item_lower = item.lower()
            
            if any(word in item_lower for word in ['shirt', 'pants', 'dress', 'jacket', 'coat', 'shoes', 'socks', 'underwear', 'hat', 'scarf']):
                categories['Clothing'].append(item)
            elif any(word in item_lower for word in ['phone', 'charger', 'camera', 'laptop', 'tablet', 'headphones', 'adapter']):
                categories['Electronics'].append(item)
            elif any(word in item_lower for word in ['passport', 'visa', 'ticket', 'id', 'license', 'insurance']):
                categories['Documents'].append(item)
            elif any(word in item_lower for word in ['toothbrush', 'shampoo', 'soap', 'medicine', 'sunscreen', 'lotion']):
                categories['Personal Care'].append(item)
            else:
                categories['Other'].append(item)
        
        return {k: v for k, v in categories.items() if v}

    # Process packing list
    packing_raw = ai_sections.get('packing', [])
    packing_parsed = robust_json_parse(packing_raw)
    
    if isinstance(packing_parsed, list):
        packing_list = categorize_flat_packing(packing_parsed)
    elif isinstance(packing_parsed, dict):
        packing_list = packing_parsed
    else:
        packing_list = {'Other': [str(packing_raw)]}

    # Process AI sections for template rendering
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

    # Use robustly parsed sections for all template variables
    packing_list = packing
    tips = sections['tips']
    budget = sections['budget']
    transport = sections['transport']
    tags = sections['safety']
    closing = sections['closing']
    
    # Get Qloo branding info
    from .qloo_api import get_qloo_branding_info
    qloo_info = get_qloo_branding_info()
    
    # Enhanced places list - use venues from Qloo if available, otherwise use city_info places
    enhanced_places = taste_data.get('venues', places) if taste_data.get('venues') else places
    enhanced_maps_links = [google_maps_link(place, taste_data["city"]) for place in enhanced_places]
    enhanced_qr_codes = {place: f"/qr?data={google_maps_link(place, taste_data['city'])}" for place in enhanced_places}
    
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
        },
        user_prompt=trip_description
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
        text = re.sub(r'"[^"]"\s,\s*[^"]"[^"]"', '', text)  # Remove quoted translations
        text = re.sub(r'The English translation of "[^"]" is "([^"])"\.?', r'\1', text)  # Extract translation
        text = re.sub(r'"([^"])",\s[^"]"[^"]"', r'\1', text)  # Clean quoted names
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
        
        # Handle budget data specifically
        if 'Budget Estimates' in text:
            # Split into sections
            sections = text.split('Budget Estimates')
            cleaned_sections = []
            for section in sections:
                # Clean each section
                section = section.strip()
                if not section:
                    continue
                # Remove continuation marks
                section = re.sub(r'\\', '', section)  # Remove backslashes
                section = re.sub(r'\s*•\s*', '• ', section)  # Normalize bullet points
                cleaned_sections.append(section)
            text = 'Budget Estimates'.join(cleaned_sections)
        
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

    # --- Text wrapping utility (must be defined before use) ---
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
                    if temp_word:
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

    # --- Add user prompt to cover page (before showPage) ---
    prompt_text = request.form.get('trip_description', '').strip()
    if prompt_text:
        # Draw a visually distinct box for the prompt
        box_width = width - 120
        box_height = 36 + 14 * len(wrap_text(prompt_text, box_width - 20, 11))
        y_box_top = max(50, y - 60 - box_height)
        pdf.setFillColor(HexColor('#f5f7fa'))  # Light background
        pdf.roundRect(60, y_box_top, box_width, box_height, 10, fill=1, stroke=0)
        pdf.setStrokeColor(HexColor('#008080'))  # Teal border
        pdf.setLineWidth(2)
        pdf.roundRect(60, y_box_top, box_width, box_height, 10, fill=0, stroke=1)
        # Draw the title
        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(HexColor('#008080'))
        pdf.drawCentredString(width // 2, y_box_top + box_height - 18, "Your Trip Preferences:")
        # Draw the prompt text
        pdf.setFont("Helvetica-Oblique", 11)
        pdf.setFillColor(secondary_text)
        prompt_lines = wrap_text(prompt_text, box_width - 20, 11)
        y_prompt = y_box_top + box_height - 36
        for line in prompt_lines:
            pdf.drawCentredString(width // 2, y_prompt, line)
            y_prompt -= 14

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
    
    # Improved layout: description as a wide, well-aligned paragraph
    para_width = width - 120  # Use nearly the full page width
    if description:
        desc_lines = wrap_text(description, para_width, 12)
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(text_color)
        for line in desc_lines:
            pdf.drawString(60, y, line)
            y -= 16
        y -= 10  # Extra space after paragraph
    else:
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, f"{city_name} is a vibrant cultural destination.")
        y -= 16
        y -= 10
    
    # "Why This City?" highlight box with reason content
    reason_text = request.form.get('reason', '')
    if reason_text:
        # Draw a rounded, colored box for the section
        reason_box_width = width - 100
        reason_box_height = 44 + 15 * len(wrap_text(reason_text, reason_box_width - 30, 11))
        box_y = y - 10
        pdf.setFillColor(primary_color)
        pdf.roundRect(50, box_y - reason_box_height, reason_box_width, reason_box_height, 10, fill=1, stroke=0)
        # Draw the section title
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(HexColor('#FFFFFF'))
        pdf.drawString(65, box_y - 22, "Why This City?")
        # Prepare and draw the reason text
        clean_reason = re.sub(r'\s+', ' ', reason_text.replace('\n', ' ')).strip()
        reason_lines = wrap_text(clean_reason, reason_box_width - 30, 11)
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(HexColor('#FFFFFF'))
        y_reason = box_y - 38
        for line in reason_lines:
            pdf.drawString(65, y_reason, line)
            y_reason -= 15
        y = box_y - reason_box_height - 18
    
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
        y -= 20  # Extra space after taste summary description
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

    y -= 20  # Extra space after Taste Summary table
    y -= 20  # Extra space before Weather Forecast section
    # Weather Forecast section
    if y < 100:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"\u2600 Weather Forecast:")
    y -= 18
    
    if weather_data and len(weather_data) > 0:
        from datetime import datetime, timedelta
        start_date_str = request.form.get('start_date', '')
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except Exception:
            start_date = None
        today = datetime.now().date()
        if not start_date or (start_date.date() - today).days > 7:
            pdf.setFont("Helvetica", 11)
            pdf.setFillColor(text_color)
            pdf.drawString(60, y, "Weather forecast is only available for trips starting within the next 7 days.")
            y -= 20
        else:
            # Build a date-indexed dict for fast lookup
            weather_by_date = {d.get('date', ''): d for d in weather_data}
            forecast_days = 6
            forecast_rows = []
            for i in range(forecast_days):
                day_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
                day_data = weather_by_date.get(day_str, None)
                if day_data:
                    forecast_rows.append(day_data)
                else:
                    forecast_rows.append({'date': day_str, 'desc': 'N/A', 'temp': 'N/A'})
            # Table layout parameters
            table_x = 60
            table_width = width - 120
            col_date = table_x
            col_cond = col_date + 100
            col_temp = col_cond + 220
            row_height = 20
            n_rows = forecast_days + 1  # +1 for header
            table_height = row_height * n_rows + 20
            # Draw table box
            pdf.setFillColor(HexColor('#f5f7fa'))
            pdf.roundRect(table_x - 10, y - table_height + 10, table_width, table_height, 8, fill=1, stroke=0)
            pdf.setStrokeColor(header_color)
            pdf.setLineWidth(1)
            pdf.roundRect(table_x - 10, y - table_height + 10, table_width, table_height, 8, fill=0, stroke=1)
            # Draw header row
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColor(header_color)
            pdf.drawString(col_date, y, "Date")
            pdf.drawString(col_cond, y, "Condition")
            pdf.drawString(col_temp, y, "Temperature")
            # Draw divider lines
            pdf.setStrokeColor(header_color)
            pdf.setLineWidth(0.5)
            pdf.line(col_cond - 10, y + 5, col_cond - 10, y - table_height + row_height + 20)
            pdf.line(col_temp - 10, y + 5, col_temp - 10, y - table_height + row_height + 20)
            y -= row_height
            # Draw weather rows
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(text_color)
            for day in forecast_rows:
                pdf.drawString(col_date, y, str(day.get('date', 'N/A')))
                pdf.drawString(col_cond, y, str(day.get('desc', 'N/A'))[:30])
                pdf.drawString(col_temp, y, f"{day.get('temp', 'N/A')}°C")
                y -= row_height
            y -= 8
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
    y -= 35  # Increased space between Taste Summary and Weather Forecast
    
    # --- Redesigned Packing Checklist Section ---
    if y < 180:
        pdf.showPage()
        y = height - 40
    box_left = 40
    box_width = width - 80
    # Estimate box height: header + (categories * (cat header + items * line height + spacing))
    packing_list_raw = request.form.get('packing_list', '{}')
    try:
        packing_list = json.loads(packing_list_raw) if isinstance(packing_list_raw, str) else packing_list_raw
    except Exception:
        packing_list = {}
    # Calculate lines for all items to estimate box height
    def count_lines(items, col_width):
        total = 0
        for item in items:
            lines = wrap_text(clean_section(str(item)), col_width, 10)
            total += len(lines)
        return total
    box_height = 38  # header
    col_width = (box_width - 40) // 2
    min_cat_height = 22
    # Ensure 'Others' section exists
    if isinstance(packing_list, dict) and packing_list:
        if 'Others' not in packing_list:
            packing_list['Others'] = []
        for cat, items in packing_list.items():
            n = count_lines(items, col_width)
            box_height += max(min_cat_height, n * 13) + 16
    elif isinstance(packing_list, list) and packing_list:
        box_height += count_lines(packing_list, box_width - 40) * 13 + 22
    else:
        box_height += 40
    if y - box_height < 60:
        pdf.showPage()
        y = height - 40
    box_y = y - box_height + 10
    pdf.setFillColor(HexColor('#f5f7fa'))
    pdf.roundRect(box_left, box_y, box_width, box_height, 10, fill=1, stroke=0)
    pdf.setStrokeColor(accent_color)
    pdf.setLineWidth(2)
    pdf.roundRect(box_left, box_y, box_width, box_height, 10, fill=0, stroke=1)
    # Section header
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(accent_color)
    pdf.drawString(box_left + 20, y - 18, u"🎒 Packing Checklist")
    y -= 38
    # Render items in two columns if possible
    col1_x = box_left + 32
    col2_x = box_left + 32 + col_width + 32
    col_y_start = y
    if isinstance(packing_list, dict) and packing_list:
        for idx, (category, items) in enumerate(packing_list.items()):
            if y < box_y + 40:
                break
            # Category header
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColor(header_color)
            pdf.drawString(col1_x, y, f"{category}:")
            y -= 15
            # Split items into two columns for long lists
            if len(items) > 6:
                mid = (len(items) + 1) // 2
                col1_items = items[:mid]
                col2_items = items[mid:]
            else:
                col1_items = items
                col2_items = []
            max_rows = max(len(col1_items), len(col2_items))
            pdf.setFont("Helvetica", 12)
            pdf.setFillColor(text_color)
            row_y = y
            for i in range(max_rows):
                if i < len(col1_items):
                    item_text = clean_section(str(col1_items[i]))
                    lines = wrap_text(item_text, col_width, 12)
                    for lidx, line in enumerate(lines):
                        bullet = "• " if lidx == 0 else "  "
                        pdf.drawString(col1_x, row_y, f"{bullet}{line}")
                        row_y -= 16
                if i < len(col2_items):
                    item_text = clean_section(str(col2_items[i]))
                    lines = wrap_text(item_text, col_width, 12)
                    for lidx, line in enumerate(lines):
                        bullet = "• " if lidx == 0 else "  "
                        pdf.drawString(col2_x, y, f"{bullet}{line}")
                        y -= 16
            y = min(row_y, y) - 10
            # Divider between categories
            if idx < len(packing_list) - 1:
                pdf.setStrokeColor(HexColor('#cccccc'))
                pdf.setLineWidth(1)
                pdf.line(box_left + 24, y + 5, box_left + box_width - 24, y + 5)
                y -= 8
    elif isinstance(packing_list, list) and packing_list:
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(text_color)
        for item in packing_list:
            item_text = clean_section(str(item))
            lines = wrap_text(item_text, box_width - 40, 12)
            for lidx, line in enumerate(lines):
                bullet = "• " if lidx == 0 else "  "
                pdf.drawString(col1_x, y, f"{bullet}{line}")
                y -= 16
        y -= 10
    else:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(text_color)
        pdf.drawString(col1_x, y, "Packing list unavailable.")
        y -= 14
    y = box_y - 16
    y -= 20  # Extra space before Budget Estimates



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
        # Render as a visually distinct rounded table box
        box_width = width - 80
        col1_x = 60  # Category col
        col2_x = 180 # Accommodation
        col3_x = 320 # Food
        col4_x = 440 # Activities
        col_widths = [col2_x-col1_x, col3_x-col2_x, col4_x-col3_x, box_width-col4_x+40]
        # Extract values
        def clean_budget_line(line):
            """
            Clean a single budget line: remove brackets, quotes, and extraneous marks, and apply phrase cleaning.
            Also formats the line into a more readable format.
            """
            import re
            # Remove leading/trailing brackets, quotes
            line = line.strip()
            # Remove leading brackets/quotes
            line = re.sub(r'^[\[\]\(\)\{\}\'\"]+', '', line)
            # Remove trailing brackets/quotes
            line = re.sub(r'[\[\]\(\)\{\}\'\"]+$', '', line)
            line = re.sub(r"^[,\s]+|[,\s]+$", '', line)
            # Remove repeated/unwanted phrases
            for phrase in [
                'cost for', 'expecttospend', 'expect to spend', 'around', 'approximately', 'per activities', 'per activity',
                'per meals', 'per meal', 'per day for meals', 'per day on', 'per day', 'per activities', 'per activity',
                'per person', 'for', ':', ' - ', '--', '  '
            ]:
                line = line.replace(phrase, '')
            # Remove double spaces
            line = ' '.join(line.split())
            # Format price with proper currency symbol and spacing
            price_match = re.search(r'\$(\d+(?:\.\d{1,2})?/night|\$\d+)', line)
            if price_match:
                price = price_match.group(0)
                # Remove price from description
                desc = line.replace(price, '').strip()
                # Format with proper spacing
                line = f"{desc} {price}"
            # Handle specific cases
            if 'cafe du monde' in line.lower():
                line = line.replace('cafe du monde', 'Cafe du Monde')
            if 'beignet cafe' in line.lower():
                line = line.replace('beignet cafe', 'Beignet Cafe')
            if 'morial convention center' in line.lower():
                line = line.replace('morial convention center', 'Ernest N. Morial Convention Center')
            # Capitalize first letter
            if line:
                line = line[0].upper() + line[1:]
            return line.strip()
            # Capitalize first letter
            if line:
                line = line[0].upper() + line[1:]
            return line.strip()

        def parse_budget_category(val):
            """
            Parse budget category value into both list and sentence formats.
            Returns a tuple of (cleaned_list, formatted_sentence)
            """
            import re
            cleaned_list = []
            formatted_sentence = []
            
            def clean_item(item):
                """Clean a single item by removing brackets and quotes"""
                item = str(item).strip()
                # Remove any surrounding brackets, quotes, or parentheses
                item = re.sub(r'^[\[\]\(\)\{\}\'\"]+', '', item)
                item = re.sub(r'[\[\]\(\)\{\}\'\"]+$', '', item)
                return item.strip()
            
            def format_sentence(desc, price):
                """Format budget item as a sentence with proper spacing"""
                return f"{desc} (${price})" if price else desc
            
            if isinstance(val, list):
                # Clean and group related items
                for item in val:
                    item = clean_item(item)
                    if not item:
                        continue
                    cleaned = clean_budget_line(item)
                    
                    # Extract price (including /night)
                    price_match = re.search(r'\$(\d+(?:\.\d{1,2})?/night|\$\d+)', cleaned)
                    price = price_match.group(0) if price_match else ''
                    
                    # Format and add to lists
                    cleaned_list.append(cleaned)
                    formatted_sentence.append(format_sentence(cleaned, price))
            
            elif isinstance(val, str):
                # Clean the string first
                val = clean_item(val)
                # Split by common delimiters
                raw_lines = re.split(r'[\n;\,]', val)
                
                for line in raw_lines:
                    line = clean_item(line)
                    if not line.strip():
                        continue
                    
                    cleaned = clean_budget_line(line)
                    
                    # Extract price (including /night)
                    price_match = re.search(r'\$(\d+(?:\.\d{1,2})?/night|\$\d+)', cleaned)
                    price = price_match.group(0) if price_match else ''
                    
                    # Format and add to lists
                    cleaned_list.append(cleaned)
                    formatted_sentence.append(format_sentence(cleaned, price))
                    cleaned = clean_budget_line(line)
                    cleaned_list.append(cleaned)
                    # Format for sentence
                    if '$' in cleaned:
                        parts = cleaned.split('$')
                        if len(parts) == 2:
                            desc = parts[0].strip()
                            price = parts[1].strip()
                            formatted_sentence.append(f"{desc} (${price})")
                    else:
                        formatted_sentence.append(cleaned)
            
            # Remove duplicates and empty items
            cleaned_list = list(dict.fromkeys(cleaned_list))
            formatted_sentence = list(dict.fromkeys(formatted_sentence))
            
            # Log the formats
            print(f"Budget Parsing - List Format: {cleaned_list}")
            print(f"Budget Parsing - Sentence Format: {formatted_sentence}")
            
            # Return both formats
            return cleaned_list[:12], formatted_sentence[:12]

        # Parse and clean budget categories robustly
        accommodation_lines, accommodation_sentence = parse_budget_category(budget.get('accommodation', []))
        food_lines, food_sentence = parse_budget_category(budget.get('food', []))
        activities_lines, activities_sentence = parse_budget_category(budget.get('activities', []))

        # Match packing list dimensions
        box_left = 40
        box_width = width - 80  # Same as packing list
        
        # Calculate column widths based on available space
        total_col_width = box_width - 80  # 40px padding on each side
        col_padding = 20  # Reduced padding between columns
        
        # Calculate column widths proportionally
        category_width = int(total_col_width * 0.15)  # 15% for Category
        acc_width = int(total_col_width * 0.25)  # 25% for Accommodation
        food_width = int(total_col_width * 0.25)  # 25% for Food
        act_width = int(total_col_width * 0.30)  # 30% for Activities
        
        # Calculate column positions
        col1_x = box_left + 40  # 40px left padding
        col2_x = col1_x + category_width + col_padding
        col3_x = col2_x + acc_width + col_padding
        col4_x = col3_x + food_width + col_padding
        
        # Wrap text for each cell with precise column widths
        # Use sentence format for better readability
        acc_lines = []
        for line in accommodation_sentence:
            # Subtract padding and extra space for bullet points
            acc_lines.extend(wrap_text(line, acc_width - col_padding - 15, 11))
        acc_lines = acc_lines[:12]
        
        food_lines_wrapped = []
        for line in food_sentence:
            # Subtract padding and extra space for bullet points
            food_lines_wrapped.extend(wrap_text(line, food_width - col_padding - 15, 11))
        food_lines_wrapped = food_lines_wrapped[:12]
        
        act_lines_wrapped = []
        for line in activities_sentence:
            # Subtract padding and extra space for bullet points
            act_lines_wrapped.extend(wrap_text(line, act_width - col_padding - 15, 11))
        act_lines_wrapped = act_lines_wrapped[:12]
        
        max_lines = max(len(acc_lines), len(food_lines_wrapped), len(act_lines_wrapped))
        box_height = 60 + 16 * max_lines
        
        # Ensure we have enough space for the table
        if y - box_height < 60:
            pdf.showPage()
            y = height - 40
        
        box_y = y - box_height + 10
        
        # Draw main table container with subtle background
        pdf.setFillColor(HexColor('#f5f7fa'))
        pdf.roundRect(40, box_y, box_width, box_height, 10, fill=1, stroke=0)
        
        # Draw table header with bold styling
        pdf.setStrokeColor(header_color)
        pdf.setLineWidth(2)
        pdf.roundRect(40, box_y, box_width, box_height, 10, fill=0, stroke=1)
        
        # Section title
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(header_color)
        pdf.drawString(60, y - 18, "Budget Estimates")
        
        # Draw table headers with improved spacing
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(col1_x, y - 38, "Category")
        pdf.drawString(col2_x, y - 38, "Accommodation")
        pdf.drawString(col3_x, y - 38, "Food")
        pdf.drawString(col4_x, y - 38, "Activities")
        
        # Draw vertical dividers with improved appearance
        divider_top = y - 42
        divider_bottom = box_y + 10
        pdf.setStrokeColor(header_color)
        pdf.setLineWidth(1)
        
        # Draw lighter dividers for a cleaner look
        pdf.setStrokeColor(HexColor('#cccccc'))
        pdf.setLineWidth(0.5)
        pdf.line(col2_x - col_padding//2, divider_top, col2_x - col_padding//2, divider_bottom)
        pdf.line(col3_x - col_padding//2, divider_top, col3_x - col_padding//2, divider_bottom)
        pdf.line(col4_x - col_padding//2, divider_top, col4_x - col_padding//2, divider_bottom)
        
        # Draw daily row label with improved alignment
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(text_color)
        row_y = y - 58
        pdf.drawString(col1_x, row_y, "Daily")
        
        # Draw each row with improved text alignment and spacing
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        for i in range(max_lines):
            acc = acc_lines[i] if i < len(acc_lines) else ""
            food_val = food_lines_wrapped[i] if i < len(food_lines_wrapped) else ""
            act_val = act_lines_wrapped[i] if i < len(act_lines_wrapped) else ""
            
            # Draw text with improved alignment and bullet points
            if acc:
                pdf.drawString(col2_x, row_y, "• " + acc)
            if food_val:
                pdf.drawString(col3_x, row_y, "• " + food_val)
            if act_val:
                pdf.drawString(col4_x, row_y, "• " + act_val)
            
            # Add a subtle horizontal divider between rows
            if i < max_lines - 1:
                pdf.setStrokeColor(HexColor('#f0f0f0'))
                pdf.setLineWidth(0.5)
                pdf.line(col1_x, row_y - 8, col4_x + act_width, row_y - 8)
            
            row_y -= 16
        
        y = box_y - 16
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, "Budget estimates unavailable.")
        y -= 13
    y -= 10

    # Flight Estimates section
    y -= 20  # Extra space after Budget Estimates
    if y < 120:
        pdf.showPage()
        y = height - 40
    # Section header with icon OUTSIDE the table
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(accent_color)
    pdf.drawString(40, y, u"✈ Flight Estimates")
    y -= 18
    from datetime import datetime
    from .itinerary import get_flight_estimate
    # --- Redesigned Flight Estimates Section ---
    # Match Budget Estimates table size and style
    table_left = 40
    table_right = width - 40
    box_width = table_right - table_left
    box_height = 110  # Increased to fit all content and tip
    if y - box_height < 60:
        pdf.showPage()
        y = height - 40
    box_y = y - box_height + 10
    pdf.setFillColor(HexColor('#f5f7fa'))
    pdf.roundRect(table_left, box_y, box_width, box_height, 10, fill=1, stroke=0)
    pdf.setStrokeColor(accent_color)
    pdf.setLineWidth(2)
    pdf.roundRect(table_left, box_y, box_width, box_height, 10, fill=0, stroke=1)
    # Flight price
    # Always use web-supplied flight_estimate if present
    flight_estimate_raw = request.form.get('flight_estimate', '')
    price = "N/A"
    sites = ["Skyscanner", "Kayak", "Expedia"]
    try:
        if flight_estimate_raw:
            flight_data = json.loads(flight_estimate_raw)
            price = flight_data.get('price', 'N/A')
            sites = flight_data.get('sites', ["Skyscanner", "Kayak", "Expedia"])
        else:
            price = "N/A"
    except Exception as e:
        print(f"Flight estimate parse error in PDF: {e}")
        price = "N/A"
        sites = ["Skyscanner", "Kayak", "Expedia"]
    print(f"[DEBUG] Flight PDF price: {price}, sites: {sites}")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(header_color)
    pdf.drawString(table_left + 40, y - 38, "Estimated Round-trip Cost:")
    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(text_color)
    pdf.drawString(table_left + 240, y - 38, str(price))
    # Booking sites with icons
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(header_color)
    pdf.drawString(table_left + 40, y - 58, "Best Booking Sites:")
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    icon_map = {"Skyscanner": u"🌐", "Kayak": u"🛶", "Expedia": u"🧳"}
    site_x = table_left + 190
    for i, site in enumerate(sites[:3]):
        icon = icon_map.get(site, u"🔗")
        pdf.drawString(site_x + i*90, y - 58, f"{icon} {site}")
    # Booking tip inside the table at the bottom
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColor(HexColor('#555555'))
    pdf.drawString(table_left + 40, box_y + 18, "Tip: Book 2-3 months in advance for best prices.")
    y = box_y - 16

    # --- Redesigned Travel Essentials Section as Subheadings ---
    # Section header
    if y < 180:
        pdf.showPage()
        y = height - 40
    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(header_color)
    pdf.drawString(40, y, u"🧳 Travel Essentials")
    y -= 25

    # Tips
    tips_raw = request.form.get('tips', '[]')
    try:
        tips = json.loads(tips_raw) if isinstance(tips_raw, str) else tips_raw
    except Exception:
        tips = []
    tips = tips if isinstance(tips, list) else []
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"💡 Tips:")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    for tip in tips:
        lines = wrap_text(str(tip), width - 120, 11)
        for line in lines:
            pdf.drawString(70, y, f"• {line}")
            y -= 14
    y -= 8

    # Transport Options
    transport_raw = request.form.get('transport', '[]')
    try:
        transport = json.loads(transport_raw) if isinstance(transport_raw, str) else transport_raw
    except Exception:
        transport = []
    transport = transport if isinstance(transport, list) else []
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"🚗 Transport Options:")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    for option in transport:
        lines = wrap_text(str(option), width - 120, 11)
        for line in lines:
            pdf.drawString(70, y, f"• {line}")
            y -= 14
    y -= 8

    # Safety & Accessibility
    tags_raw = request.form.get('tags', '[]')
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except Exception:
        tags = []
    tags = tags if isinstance(tags, list) else []
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(accent_color)
    pdf.drawString(50, y, u"🦺 Safety & Accessibility:")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(text_color)
    for tag in tags:
        lines = wrap_text(str(tag), width - 120, 11)
        for line in lines:
            pdf.drawString(70, y, f"• {line}")
            y -= 14
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
            # Prepare place text lines
            pdf.setFont("Helvetica", 11)
            pdf.setFillColor(text_color)
            place_text = f"{i+1}. {str(place)}"
            place_lines = wrap_text(place_text, width - 120, 11)
            place_block_height = len(place_lines) * 13 + 35 + 20  # text + QR + spacing
            # If not enough space for both text and QR code, move to next page
            if y - place_block_height < 60:
                pdf.showPage()
                y = height - 40
            place_start_y = y
            # Draw place text
            for line in place_lines:
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
            y -= 35  # QR code height
            y -= 10  # Extra spacing after each place
    else:
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(text_color)
        pdf.drawString(60, y, "No recommended places available for this destination.")
        y -= 14

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
                        
                        # Enhanced cleaning for itinerary activities
                        def clean_itinerary_activity(text):
                            if not isinstance(text, str):
                                return text
                            import re
                            text = text.replace('AI', '').replace('ai', '')
                            text = re.sub(r'\*+', '', text)
                            text = re.sub(r'#\s*', '', text)
                            text = re.sub(r'\s+', ' ', text)
                            text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
                            text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
                            text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
                            text = re.sub(r'([a-z])\s+([a-z]{1,2})\s+([a-z])', lambda m: m.group(1) + m.group(2) + m.group(3) if len(m.group(2)) <= 2 else m.group(0), text)
                            text = re.sub(r'([\.,;:!?])([A-Za-z])', r'\1 \2', text)  # Ensure space after punctuation
                            text = re.sub(r'([a-zA-Z])([\.,;:!?])', r'\1\2', text)  # Remove space before punctuation
                            text = re.sub(r'\s+([\.,;:!?])', r'\1', text)  # Remove space before punctuation
                            text = text.strip()
                            return text
                        activity_text = clean_itinerary_activity(str(schedule[period]))
                        activity_lines = wrap_text(activity_text, width - 140, 10)
                        
                        pdf.setFont("Helvetica", 10)
                        pdf.setFillColor(text_color)
                        for line in activity_lines[:6]:  # Allow more lines per period
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
    
    # --- Add user prompt to cover page (before showPage) ---
    if request.form.get('trip_description', ''):
        pdf.setFont("Helvetica-Oblique", 11)
        pdf.setFillColor(secondary_text)
        prompt_text = request.form['trip_description']
        prompt_lines = wrap_text(prompt_text, width - 120, 11)
        y_prompt = 70  # Lower section of cover page
        for line in prompt_lines:
            pdf.drawCentredString(width // 2, y_prompt, line)
            y_prompt -= 14
    
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