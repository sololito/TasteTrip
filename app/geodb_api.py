# app/geodb_api.py
import os
import requests
from .qloo_api import get_qloo_branding_info

def get_taste_recommendations(user_input):
    """Get destination using Qloo's Taste AI™ based on cultural preferences"""
    from .qloo_api import get_taste_based_destinations, get_qloo_branding_info
    
    # Always use Qloo for destination recommendation
    print(f"DEBUG: Calling Qloo with user_input: {user_input}")
    qloo_result = get_taste_based_destinations(user_input)
    print(f"DEBUG: Qloo returned: {qloo_result}")
    
    if qloo_result:
        print(f"DEBUG: Using Qloo result for city: {qloo_result['city']}")
        return {
            'city': qloo_result['city'],
            'reason': qloo_result['reason'],
            'vibe': user_input.get('vibe', 'cultural'),
            'days': user_input.get('days', '3'),
            'venues': qloo_result.get('venues', []),
            'taste_mapping': qloo_result.get('taste_mapping', []),
            'qloo_powered': qloo_result.get('qloo_powered', True),
            'confidence': qloo_result.get('confidence', 3)
        }
    
    print(f"DEBUG: Qloo returned None, using fallback")
    
    # Enhanced fallback with Qloo branding
    music = user_input.get('music', 'various music')
    movie = user_input.get('movie', 'great cinema')
    food = user_input.get('food', 'diverse cuisine')
    days = user_input.get('days', '3')
    
    # Calculate venues needed based on trip duration
    try:
        num_days = int(user_input.get('days', '3'))
    except (ValueError, TypeError):
        num_days = 3
    venues_needed = min(num_days * 4, 20)  # 4 venues per day, max 20
    
    # Get city from user preferences using keyword matching
    recommended_city = 'Paris'  # Default fallback
    
    # Combine all user preferences for analysis
    all_preferences = f"{music} {movie} {food}".lower()
    
    # City keyword mapping
    city_keywords = {
        'Paris': ['french', 'france', 'paris', 'louvre', 'eiffel', 'baguette', 'croissant', 'wine', 'cheese', 'amélie', 'godard'],
        'Rome': ['italian', 'italy', 'rome', 'pasta', 'pizza', 'vatican', 'colosseum', 'fellini', 'gelato'],
        'Tokyo': ['japanese', 'japan', 'tokyo', 'sushi', 'anime', 'manga', 'ramen', 'miyazaki', 'kurosawa'],
        'London': ['british', 'england', 'london', 'tea', 'fish and chips', 'beatles', 'shakespeare', 'pub'],
        'Barcelona': ['spanish', 'spain', 'barcelona', 'tapas', 'paella', 'flamenco', 'gaudí', 'catalan'],
        'Berlin': ['german', 'germany', 'berlin', 'beer', 'sausage', 'techno', 'bowie', 'kraftwerk'],
        'Amsterdam': ['dutch', 'netherlands', 'amsterdam', 'cheese', 'stroopwafel', 'van gogh', 'rembrandt'],
        'Madrid': ['spanish', 'spain', 'madrid', 'tapas', 'flamenco', 'prado', 'almodovar']
    }
    
    # Find best matching city
    best_match_score = 0
    for city, keywords in city_keywords.items():
        score = sum(1 for keyword in keywords if keyword in all_preferences)
        if score > best_match_score:
            best_match_score = score
            recommended_city = city
    
    # Get venues based on city with proper fallbacks
    def get_city_specific_venues(city, venues_needed):
        city_venues = {
            'Barcelona': ['Park Güell', 'Sagrada Familia', 'Gothic Quarter', 'El Born District', 'La Boqueria Market', 'Casa Batlló', 'Picasso Museum', 'Barceloneta Beach', 'Montjuïc Hill', 'Casa Milà', 'Palau de la Música', 'Camp Nou'],
            'Paris': ['Eiffel Tower', 'Louvre Museum', 'Notre-Dame', 'Champs-Élysées', 'Montmartre', 'Arc de Triomphe', 'Seine River', 'Latin Quarter', 'Marais District', 'Versailles'],
            'Rome': ['Colosseum', 'Vatican City', 'Trevi Fountain', 'Roman Forum', 'Pantheon', 'Spanish Steps', 'Trastevere', 'Campo de Fiori', 'Villa Borghese', 'Castel Sant Angelo'],
            'Tokyo': ['Shibuya Crossing', 'Senso-ji Temple', 'Tsukiji Market', 'Harajuku', 'Tokyo Skytree', 'Meiji Shrine', 'Akihabara', 'Ginza', 'Ueno Park', 'Roppongi'],
            'London': ['Big Ben', 'Tower Bridge', 'British Museum', 'Hyde Park', 'Covent Garden', 'Camden Market', 'Tate Modern', 'Westminster Abbey', 'Buckingham Palace', 'Thames River'],
            'Berlin': ['Brandenburg Gate', 'Museum Island', 'East Side Gallery', 'Checkpoint Charlie', 'Reichstag', 'Potsdamer Platz', 'Kreuzberg', 'Tiergarten', 'Hackescher Markt', 'Alexanderplatz'],
            'Amsterdam': ['Anne Frank House', 'Van Gogh Museum', 'Rijksmuseum', 'Jordaan District', 'Red Light District', 'Vondelpark', 'Canal Ring', 'Dam Square', 'Bloemenmarkt', 'Museumplein'],
            'Madrid': ['Prado Museum', 'Royal Palace', 'Retiro Park', 'Gran Vía', 'Plaza Mayor', 'Reina Sofía Museum', 'Thyssen Museum', 'Malasaña', 'La Latina', 'Temple of Debod']
        }
        
        venues = city_venues.get(city, ['City Center', 'Historic District', 'Cultural Quarter', 'Main Square', 'Local Market', 'Arts District'])
        return venues[:venues_needed]
    
    # Get city-specific venues
    dynamic_venues = get_city_specific_venues(recommended_city, venues_needed)
    
    # Categorize venues by type for organized format
    music_venues = []
    film_venues = []
    food_venues = []
    additional_venues = []
    
    for venue in dynamic_venues:
        venue_lower = venue.lower()
        if any(word in venue_lower for word in ['music', 'concert', 'palau', 'born', 'gracia']):
            music_venues.append(venue)
        elif any(word in venue_lower for word in ['market', 'boqueria', 'food', 'mercat', 'raval']):
            food_venues.append(venue)
        elif any(word in venue_lower for word in ['gothic', 'museum', 'park', 'casa', 'sagrada', 'ciutadella', 'poble']):
            film_venues.append(venue)
        else:
            additional_venues.append(venue)
    
    # Get additional spots using remaining venues only
    def get_additional_spots_clean(city, music, movie, food, remaining_venues):
        additional_spots = []
        
        for venue in remaining_venues:
            if len(additional_spots) < 6:
                if any(word in venue.lower() for word in ['beach', 'hill', 'mountain']):
                    cultural_path = f'{music} → Scenic inspiration → {venue}'
                elif any(word in venue.lower() for word in ['stadium', 'camp']):
                    cultural_path = f'{movie} → Sports culture → {venue}'
                elif any(word in venue.lower() for word in ['port', 'vell']):
                    cultural_path = f'{food} → Waterfront dining → {venue}'
                else:
                    cultural_path = f'Cultural exploration → {venue}'
                
                additional_spots.append({
                    'venue': venue,
                    'cultural_path': cultural_path
                })
        
        return additional_spots[:6]
    
    # Create organized taste mapping structure
    taste_mapping = {
        'preferences': {
            'music': music,
            'film': movie,
            'cuisine': food
        },
        'music_experiences': [
            {
                'venue': venue,
                'cultural_path': f"{music} → Global music culture → {venue}"
            } for venue in music_venues[:3]
        ],
        'film_experiences': [
            {
                'venue': venue,
                'cultural_path': f"{movie} → Cinema culture → {venue}"
            } for venue in film_venues[:3]
        ],
        'cuisine_experiences': [
            {
                'venue': venue,
                'cultural_path': f"{food} → Culinary culture → {venue}"
            } for venue in food_venues[:3]
        ],
        'additional_spots': get_additional_spots_clean(recommended_city, music, movie, food, additional_venues)
    }
    
    fallback_reason = f"""No exact match found, but {recommended_city} captures your cultural vibe! 🌟

✨ Why {recommended_city} works for you:
• {music} → Vibrant music scene & live venues
• {movie} → Cinematic heritage & visual culture  
• {food} → Authentic culinary traditions

Your unique tastes deserve exploration — this destination offers rich cultural experiences while Qloo's AI continues learning your preferences."""
    
    return {
        'city': recommended_city,
        'reason': fallback_reason,
        'vibe': user_input.get('vibe', 'cultural'),
        'days': user_input.get('days', '3'),
        'venues': dynamic_venues,
        'taste_mapping': taste_mapping,
        'qloo_powered': True,
        'confidence': 2,
        'is_fallback': True,
        'fallback_message': f"Our cultural engine didn't find an exact destination that matches all your tastes right now.\nBut don't worry — your preferences are unique and worth exploring.\nWhile Qloo's Taste AI continues to learn, we've handpicked a destination that still captures the vibe you're looking for.\nIt's not a direct match, but it's a place known for cultural richness, great food, and immersive experiences.\n\n✨ Want to try adjusting your preferences — or explore a different vibe?"
    }

def get_city_info(city_name, venues=None):
    """Get comprehensive city information using provided venues for consistency"""
    
    # Enhanced city descriptions for better context
    city_descriptions = {
        'Liverpool': 'Liverpool is a vibrant port city in northwest England, famous as the birthplace of The Beatles and home to a rich musical heritage that shaped global pop culture.',
        'Berlin': 'Berlin is Germany\'s dynamic capital, a city where history meets cutting-edge culture, known for its artistic innovation and transformative musical scenes.',
        'Rome': 'Rome is the eternal city where ancient history meets culinary excellence, offering authentic Italian cuisine in the very place where it originated.',
        'Tokyo': 'Tokyo is a mesmerizing metropolis that seamlessly blends traditional Japanese culture with ultra-modern innovation, creating a unique cultural experience.',
        'Barcelona': 'Barcelona is a captivating Mediterranean city renowned for its distinctive architecture, vibrant arts scene, and exceptional culinary culture.',
        'Paris': 'Paris is the city of light and love, a cultural epicenter known for its artistic heritage, world-class cuisine, and cinematic history.',
        'New Orleans': 'New Orleans is a soulful city where jazz was born, offering a unique blend of musical heritage, Creole culture, and distinctive cuisine.',
        'Vienna': 'Vienna is the imperial city of music, home to classical composers and elegant coffee house culture in the heart of Europe.',
        'Amsterdam': 'Amsterdam is a charming canal city known for its artistic heritage, liberal culture, and historic architecture.',
        'Madrid': 'Madrid is Spain\'s vibrant capital, renowned for its world-class museums, lively tapas culture, and passionate flamenco traditions.'
    }
    
    description = city_descriptions.get(city_name, f'{city_name} is a vibrant destination offering rich cultural experiences and unique local attractions.')
    
    # Use provided venues for consistency, or fallback to generic places
    places = venues if venues else ['City Center', 'Historic District', 'Cultural Quarter', 'Main Square']
    
    return {
        'name': city_name,
        'description': description,
        'places': places
    }