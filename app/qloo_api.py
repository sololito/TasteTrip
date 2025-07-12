import os
import requests
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

QLOO_API_KEY = os.getenv("QLOO_API_KEY")
QLOO_BASE_URL = "https://hackathon.api.qloo.com"

# Ensure API key is present
if not QLOO_API_KEY:
    print("Warning: QLOO_API_KEY not found in .env file. Qloo features will be limited.")

HEADERS = {
    "x-api-key": QLOO_API_KEY,
    "Content-Type": "application/json"
}

def get_similar_entities(entity_type, name, expected_city=None, expected_country=None):
    """Get entities from Qloo search with location enrichment and filtering"""
    if not QLOO_API_KEY or not name:
        print(f"[Qloo] Missing API key or name: key={bool(QLOO_API_KEY)}, name='{name}'")
        return []
    
    try:
        url = f"{QLOO_BASE_URL}/search"
        print(f"[Qloo] Calling {url} with query='{name}'")
        response = requests.get(url, headers=HEADERS, params={"query": name}, timeout=10)
        
        print(f"[Qloo] Response status: {response.status_code}")
        print(f"[Qloo] Response text: {response.text[:500]}...")  # First 500 chars
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            print(f"[Qloo] Found {len(results)} results for '{name}'")
            
            # Enrich with location data and filter
            enriched = []
            for res in results:
                if res:  # Check if result is not None
                    location = res.get("location") or {}
                    # Try to extract city from multiple possible locations
                    city = res.get("city") or location.get("city")
                    country = location.get("country")
                    if not city:
                        # Try Qloo's new format: properties.geocode.city
                        properties = res.get("properties", {})
                        geocode = properties.get("geocode", {})
                        city = geocode.get("city")
                        country = country or geocode.get("country")
                    
                    # Filter by expected city and country
                    if expected_city and expected_city.lower() not in str(city or "").lower():
                        continue
                    if expected_country and expected_country.lower() not in str(country or "").lower():
                        continue
                    
                    enriched.append({
                        "name": res.get("name"),
                        "type": res.get("type"),
                        "city": city,
                        "country": country,
                        "category": res.get("category")
                    })
            print(f"[Qloo] Enriched to {len(enriched)} results")
            return enriched
        else:
            print(f"[Qloo] API returned status {response.status_code} for query '{name}'")
            return []
    except Exception as e:
        print(f"[Qloo] Error searching for '{name}': {e}")
        return []

def get_associated_locations(entity_name, entity_type):
    """Get locations from Qloo search with enhanced cultural mapping"""
    return get_similar_entities(entity_type, entity_name)

def get_venues_for_city(city, country=None, categories=["attractions", "restaurants", "music venues"], venues_needed=12):
    """Get venues for a specific city with country filtering"""
    venues = []
    for category in categories:
        try:
            query = f"{city} {category}"
            results = get_similar_entities('', query, expected_city=city, expected_country=country)
            for r in results[:3]:  # Top 3 per category
                if r.get("name") and r["name"] not in venues:
                    venues.append(r["name"])
        except Exception as e:
            print(f"Error getting venues for {city} {category}: {e}")
    
    # Fallback if no venues found
    if not venues:
        fallback_venues = {
            'Tokyo': ['Shibuya Crossing', 'Senso-ji Temple', 'Harajuku District'],
            'Paris': ['Eiffel Tower', 'Louvre Museum', 'Montmartre'],
            'Rome': ['Colosseum', 'Vatican City', 'Trevi Fountain'],
            'Barcelona': ['Park Güell', 'Sagrada Familia', 'Gothic Quarter'],
            'London': ['Big Ben', 'Tower Bridge', 'British Museum'],
            'Kingston': ['Bob Marley Museum', 'Devon House', 'Emancipation Park']
        }
        venues = fallback_venues.get(city, ['City Center', 'Historic District', 'Cultural Quarter'])
    
    return venues[:venues_needed]

def get_qloo_branding_info():
    """Return Qloo branding information for templates"""
    return {
        'name': 'Qloo',
        'tagline': 'Powered by Qloo\'s Taste AI™',
        'description': 'Qloo\'s advanced cultural intelligence understands the deep connections between your personal tastes and travel destinations.',
        'logo_url': 'https://qloo.com/assets/qloo-logo.png',
        'website': 'https://qloo.com'
    }

def get_taste_based_destinations(user_preferences):
    """Get destinations based on user cultural preferences using Qloo's Taste AI™"""
    music = user_preferences.get('music', '')
    food = user_preferences.get('food', '')
    movie = user_preferences.get('movie', '')
    vibe = user_preferences.get('vibe', 'cultural')
    days = user_preferences.get('days', '3')
    
    print(f"DEBUG: Qloo received - Music: '{music}', Movie: '{movie}', Food: '{food}', Vibe: '{vibe}'")
    
    if not QLOO_API_KEY:
        return None
    
    # Dynamic vibe modifier based on Qloo results
    def get_vibe_modifier(vibe, city):
        vibe_modifiers = {
            'relaxing': 'peaceful and serene',
            'adventurous': 'thrilling and exciting', 
            'romantic': 'romantic and intimate',
            'party': 'vibrant nightlife and party',
            'cultural': 'rich cultural heritage',
            'luxury': 'luxurious and upscale',
            'nature': 'natural beauty and wildlife',
            'historical': 'ancient history and monuments'
        }
        return vibe_modifiers.get(vibe, 'culturally enriching')
    
    # Dynamic city detection using Qloo results
    def get_city_from_qloo_result(result, preference):
        """Extract city and country from Qloo result or infer from entity type"""
        if not result:
            return None, None
        if result.get("city"):
            return result["city"], result.get("country")
        
        # Fallback inference based on entity name and type
        entity_name = str(result.get("name") or "").lower()
        entity_type = str(result.get("type") or "").lower()
        
        # Simple inference rules (expanded) - return city, country
        if any(word in entity_name for word in ['korean', 'k-pop', 'bts', 'ghibli', 'anime', 'japanese']):
            return 'Tokyo', 'Japan'
        elif any(word in entity_name for word in ['french', 'paris', 'louvre']):
            return 'Paris', 'France'
        elif any(word in entity_name for word in ['italian', 'rome', 'vatican']):
            return 'Rome', 'Italy'
        elif any(word in entity_name for word in ['spanish', 'barcelona', 'madrid']):
            return 'Barcelona', 'Spain'
        elif any(word in entity_name for word in ['british', 'london', 'beatles']):
            return 'London', 'United Kingdom'
        elif any(word in entity_name for word in ['west african', 'nollywood', 'african']):
            return 'Lagos', 'Nigeria'
        elif any(word in entity_name for word in ['indian', 'bollywood', 'curry']):
            return 'Mumbai', 'India'
        elif any(word in entity_name for word in ['chinese', 'mandarin', 'cantonese']):
            return 'Beijing', 'China'
        elif any(word in entity_name for word in ['mexican', 'latin', 'spanish']):
            return 'Mexico City', 'Mexico'
        elif any(word in entity_name for word in ['electronic']):
            return 'Berlin', 'Germany'
        elif any(word in entity_name for word in ['reggae']):
            return 'Kingston', 'Jamaica'
        elif any(word in entity_name for word in ['jazz']):
            return 'New Orleans', 'United States'
        elif any(word in entity_name for word in ['hip-hop', 'hiphop', 'rap']):
            return 'New York', 'United States'
        elif any(word in entity_name for word in ['classical', 'mozart', 'vienna']):
            return 'Vienna', 'Austria'
        elif any(word in entity_name for word in ['mediterranean']):
            return 'Athens', 'Greece'
        elif any(word in entity_name for word in ['bbq', 'barbecue', 'southern']):
            return 'Austin', 'United States'
        elif any(word in entity_name for word in ['pizza']):
            return 'Naples', 'Italy'
        elif any(word in entity_name for word in ['sushi']):
            return 'Tokyo', 'Japan'
        elif any(word in entity_name for word in ['tapas']):
            return 'Madrid', 'Spain'
        elif any(word in entity_name for word in ['opera']):
            return 'Milan', 'Italy'
        elif any(word in entity_name for word in ['blues']):
            return 'Chicago', 'United States'
        elif any(word in entity_name for word in ['tango']):
            return 'Buenos Aires', 'Argentina'
        elif any(word in entity_name for word in ['wine']):
            return 'Bordeaux', 'France'
        elif any(word in entity_name for word in ['beer', 'bier']):
            return 'Munich', 'Germany'
        elif any(word in entity_name for word in ['surf']):
            return 'Sydney', 'Australia'
        
        return None, None
    
    try:
        # Get Qloo recommendations for each preference
        qloo_matches = []
        preferences = [music, food, movie]
        pref_types = ['music', 'cuisine', 'entertainment']
        
        for i, pref in enumerate(preferences):
            if pref:
                print(f"[Qloo] Processing preference {i}: '{pref}' (type: {pref_types[i]})")
                results = get_similar_entities('', pref)
                print(f"[Qloo] Got {len(results)} results for '{pref}'")
                for result in results[:3]:  # Top 3 matches
                    entity_name = result.get('name', '')
                    # Use Qloo result to determine city and country dynamically
                    city, country = get_city_from_qloo_result(result, pref)
                    if city:
                        qloo_matches.append({
                            'city': city,
                            'country': country,
                            'reason': f'Related to your interest in {result.get("name", entity_name)}',
                            'preference': pref,
                            'type': pref_types[i],
                            'qloo_match': result.get("name", entity_name)
                        })
                        print(f"DEBUG: Qloo matched '{result.get('name')}' to {city}, {country}")
                    else:
                        print(f"DEBUG: No city data for {result.get('name')}, skipping")
        
        # Select best match based on Qloo data
        print(f"DEBUG: Found {len(qloo_matches)} Qloo matches: {[m['city'] for m in qloo_matches]}")
        if qloo_matches:
            best_match = qloo_matches[0]  # Take first match
            print(f"DEBUG: Selected best match: {best_match['city']}")
            
            # Apply vibe modifier to destination selection
            vibe_modifier = get_vibe_modifier(vibe, best_match['city'])
            
            # Create comprehensive reason with Qloo branding and vibe consideration
            reason = f"""Qloo's Taste AI™ analyzed your cultural preferences and {vibe} travel vibe to identify {best_match['city']} as your perfect destination. 
            
            Based on your love for {music or 'your music taste'}, {movie or 'your entertainment preferences'}, and {food or 'your culinary interests'}, combined with your desire for a {vibe} experience, {best_match['city']} offers {best_match['reason']} with a {vibe_modifier} atmosphere. 
            
            This recommendation leverages Qloo's advanced cultural intelligence, which understands the deep connections between your personal tastes, travel mood, and destinations that will truly resonate with your cultural DNA. Qloo's AI has identified cultural patterns that make {best_match['city']} an ideal match for your {vibe} {days}-day adventure."""
            
            # Create taste graph connections with vibe integration
            taste_graph = f"""
            
            🔗 Qloo's Taste Graph Connections:
            • {music or 'Your music taste'} → {best_match['type']} culture → {best_match['city']}'s {best_match['reason'].split()[0]} scene
            • {movie or 'Your film preferences'} → Cultural storytelling → {best_match['city']}'s cinematic heritage
            • {food or 'Your cuisine interests'} → Culinary traditions → {best_match['city']}'s authentic food culture
            • {vibe.capitalize()} vibe → {vibe_modifier} experiences → {best_match['city']}'s {vibe} attractions
            
            These connections were identified using Qloo's cross-domain intelligence between your music, film, cuisine preferences, and desired travel mood."""
            
            # Get venues needed based on trip duration
            try:
                num_days = int(days)
            except (ValueError, TypeError):
                num_days = 3
            venues_needed = min(num_days * 3, 15)  # 3 venues per day, max 15
            
            # Get venues dynamically from Qloo with country filtering
            city_venues_list = get_venues_for_city(
                city=best_match['city'],
                country=best_match.get('country'),
                categories=["attractions", "restaurants", "music venues"],
                venues_needed=venues_needed
            )
            
            # Categorize venues by type using Qloo
            music_venues = []
            film_venues = []
            food_venues = []
            additional_venues = []
            
            for venue in city_venues_list:
                venue_lower = venue.lower()
                if any(word in venue_lower for word in ['music', 'concert', 'palau', 'born', 'gracia']):
                    music_venues.append(venue)
                elif any(word in venue_lower for word in ['market', 'boqueria', 'food', 'mercat', 'raval']):
                    food_venues.append(venue)
                elif any(word in venue_lower for word in ['gothic', 'museum', 'park', 'casa', 'sagrada', 'ciutadella', 'poble']):
                    film_venues.append(venue)
                else:
                    additional_venues.append(venue)
            
            # Get additional spots from Qloo based on user preferences
            def get_qloo_additional_spots(city, music, movie, food):
                additional_spots = []
                
                # Use remaining venues from categorization as additional spots
                for venue in additional_venues:
                    if len(additional_spots) < 6:
                        # Create meaningful cultural paths based on venue type
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
                
                return additional_spots[:6]  # Max 6 spots
            
            # Create organized taste mapping structure
            taste_mapping = {
                'preferences': {
                    'music': music or 'Various',
                    'film': movie or 'Various',
                    'cuisine': food or 'Various'
                },
                'music_experiences': [
                    {
                        'venue': venue,
                        'cultural_path': f"{music} → Mediterranean rhythms → {venue.split()[-1] if len(venue.split()) > 1 else 'music hub'}"
                    } for venue in music_venues[:3]
                ],
                'film_experiences': [
                    {
                        'venue': venue,
                        'cultural_path': f"{movie} → European cinema → {venue.split()[-1] if len(venue.split()) > 1 else 'cultural storytelling'}"
                    } for venue in film_venues[:3]
                ],
                'cuisine_experiences': [
                    {
                        'venue': venue,
                        'cultural_path': f"{food} → Mediterranean diet → {venue.split()[-1] if len(venue.split()) > 1 else 'local flavors'}"
                    } for venue in food_venues[:3]
                ],
                'additional_spots': get_qloo_additional_spots(best_match['city'], music, movie, food)
            }
            
            return {
                'city': best_match['city'],
                'reason': reason + taste_graph,
                'taste_mapping': taste_mapping,
                'venues': city_venues_list,
                'vibe': vibe,
                'confidence': 5,
                'qloo_powered': True
            }
        
    except Exception as e:
        print(f"[Qloo] Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG: Qloo found no matches, returning fallback city")
    # Fallback: return a default city and reason, so downstream code doesn't break
    fallback_city = 'Paris'
    fallback_reason = "Our cultural engine didn't find an exact destination that matches all your tastes right now.\nBut don't worry — your preferences are unique and worth exploring.\nWhile Qloo's Taste AI continues to learn, we've handpicked a destination that still captures the vibe you're looking for.\nIt's not a direct match, but it's a place known for cultural richness, great food, and immersive experiences.\n\n✨ Want to try adjusting your preferences — or explore a different vibe?"
    return {
        'city': fallback_city,
        'reason': fallback_reason,
        'taste_mapping': {},
        'venues': [],
        'vibe': user_preferences.get('vibe', 'cultural'),
        'confidence': 1,
        'qloo_powered': False
    }