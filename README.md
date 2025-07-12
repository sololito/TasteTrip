# TasteTrip: AI-Powered Personalized Travel Planning 🌍✈️

**Author:** SOLOMON OMONDI ODIPO  
**Title:** IT ENGINEER  
**Company:** SEA-TECH(K) LTD.

---

TasteTrip is an AI-powered travel planner that transforms your unique tastes and dreams into a beautifully organized, actionable trip plan. Simply describe your ideal trip in your own words, and TasteTrip does the rest—no dropdowns, no checkboxes, just pure inspiration.

---

## 🚀 Quick Start

1. **Clone the repository**
    ```bash
    git clone https://github.com/sololito/TasteTrip
    cd taste-trip
    ```
2. **Set up your environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```
3. **Configure API keys**
    - Copy `.env.example` to `.env` and add your keys for Qloo, Together AI, Unsplash, and OpenWeatherMap.
4. **Run the app**
    ```bash
    python run.py
    ```
5. **Open your browser** and go to `http://localhost:5000`

---

## 🧭 User Journey: Step by Step

### 📝 How Free Text Preferences Are Understood

Just describe your travel tastes and dreams in your own words—TasteTrip’s AI will understand and extract all your preferences for you. Here’s how it works:

- **AI Parsing:**
  - Together AI receives your description and is prompted to extract specific details about your music, movie, food, and travel vibe.
  - The AI is asked to return only valid JSON containing:
    - `music`: artist, genre, or style
    - `movie`: movie, director, or genre
    - `food`: cuisine or food type
    - `vibe`: travel mood (relaxing, adventurous, romantic, party, cultural, luxury, nature, historical)

**Prompt Example:**
```
Extract travel preferences from this description: "I love jazz and Italian food"

Be specific and extract actual names/types. Return ONLY valid JSON:
{
    "music": "specific artist, genre, or music style mentioned",
    "movie": "specific movie, director, or film genre mentioned", 
    "food": "specific cuisine type or food preference mentioned",
    "vibe": "travel mood: relaxing, adventurous, romantic, party, cultural, luxury, nature, historical"
}
```

**Example Mappings:**
- "I love jazz and Italian food" → `{ "music": "jazz", "movie": "", "food": "Italian", "vibe": "cultural" }`
- "Beatles fan wanting French cuisine" → `{ "music": "Beatles", "movie": "", "food": "French", "vibe": "cultural" }`

*This means you can describe your travel style however you like, and the system will intelligently map it to structured preferences!* 

---

### 1. **Tell Us About Your Tastes & Plans**
- **Cultural Preferences:**
  - Food (favorite cuisines)
  - Film/Movies
  - Other interests
- **Departure City:**
  - Helps estimate flight costs
- **Travel Dates:**
  - Start & End dates (used for weather and planning)

*All information is entered through a simple input form.*

---

### 2. **Generate My Itinerary**
- Click the **Generate My Itinerary** button.
- Your preferences and travel details are securely sent to our backend.

---

### 3. **Taste Mapping & Destination Discovery**
- **Qloo Taste AI** analyzes your cultural preferences.
- Qloo recommends a country and city that best matches your tastes.
- Qloo also returns a curated list of places to visit in that destination—these are tailored to your food, film, and cultural profile.

---

### 4. **Smart Itinerary Planning**
- The list of recommended places is sent to **Together AI**.
- Together AI arranges your trip day by day:
  - Each day is split into morning, afternoon, and evening activities.
  - The plan is logical, efficient, and reflects your tastes.

---

### 5. **Weather Forecasting**
- If your trip is within the next 7 days, your dates and chosen country are sent to **OpenWeather**.
- You get a weather forecast for your destination for the first 6 days—helpful for packing and planning.

---

### 6. **Visual Inspiration**
- **Unsplash** finds a beautiful, high-resolution image representing your destination.
- This image is included in your itinerary for inspiration and sharing.

---

### 7. **Navigation & QR Codes**
- The recommended places from Qloo are sent to **Geoapify** for directions and mapping.
- Each location’s coordinates are passed to our QR code utility.
- **Clickable QR codes** are generated for every place—scan or click to navigate easily during your trip.

---

### 8. **Your Final Itinerary**
- All data is brought together into a beautiful, organized itinerary:
  - Day-by-day plan (morning, afternoon, evening)
  - Weather forecast
  - Budget estimates
  - Safety tips and local vibes
  - Inspiring cover image
  - Clickable QR codes for every place
- **Download as PDF:**
  - One click to save your entire trip—including all info and QR codes—for offline use or sharing.

---

## 🗺️ Illustration of the Flow

```
[User Inputs Preferences & Dates]
        ↓
   [Qloo: Taste → Country/City/Places]
        ↓
   [Together AI: Day-by-Day Plan]
        ↓
   [OpenWeather: Forecast (if <7 days)]
        ↓
   [Unsplash: Destination Image]
        ↓
   [Geoapify: Directions]
        ↓
   [QR Utils: QR Codes]
        ↓
[Final Plan: Web Display & PDF Export]
```

---

## 🎒 What You Get
- A trip that feels made just for you
- A clear, logical daily plan
- Local weather and safety info
- Budget and packing tips
- Directions and QR codes for every stop
- A beautiful, downloadable PDF

---

## 🔗 Integrations Used
- **Qloo**: Taste-to-destination recommendations
- **Together AI**: Smart itinerary planning
- **OpenWeather**: Local forecasts
- **Unsplash**: Destination images
- **Geoapify**: Directions and mapping
- **QR Utils**: Clickable QR codes
- **PDF Export**: Downloadable, shareable trip plan

---

## 📥 How to Use
1. Enter your preferences, departure city, and dates
2. Click **Generate My Itinerary**
3. Review your personalized trip plan
4. Download your PDF and get ready to explore!

---

*Travel smart. Travel inspired. Travel your way—with TasteTrip.*

### 1. User Input Processing
**Route**: `/itinerary` (POST)

**Input Types**:
- **Structured**: Direct form inputs (music, movies, food preferences)
- **Text Description**: Free-form text parsed by AI

**Text Parsing Logic**:
```python
# Uses Together AI (Mistral-7B) to extract structured data
prompt = "Extract travel preferences from: '{description}'"
# Returns: {"music": "jazz", "movie": "godfather", "food": "italian", "vibe": "cultural"}
```

**Date Processing**:
- Calculates activity days: `total_days - 2` (excludes travel days)
- Minimum 1 day, maximum based on date range

### 2. Taste-Based City Recommendation
**Module**: `geodb_api.py`

**Process**:
1. **Qloo API Call**: Sends user preferences to Qloo Taste AI
2. **Cultural Mapping**: Creates taste-to-destination connections
3. **City Selection**: Returns recommended city with reasoning
4. **Venue Discovery**: Finds taste-aligned venues in the city

**Output Structure**:
```python
{
    "city": "Barcelona",
    "reason": "Perfect match for your jazz and art preferences...",
    "venues": ["Palau de la Música", "Picasso Museum"],
    "taste_mapping": [
        {
            "category": "🎵 Music",
            "preference": "Jazz",
            "cultural_path": "Barcelona's vibrant jazz scene...",
            "experience": "Live performances at historic venues"
        }
    ]
}
```

### 3. AI Itinerary Generation
**Module**: `itinerary.py`

**Multi-AI Approach**:
- **Primary**: Together AI (Mistral-7B) for speed and cost-efficiency
- **Fallback**: OpenAI GPT-4 for complex requests

**Generation Logic**:
```python
# Comprehensive prompt engineering
prompt = f"""
Create a {days}-day itinerary for {city} based on:
- Music taste: {music}
- Movie preferences: {movie}  
- Food preferences: {food}
- Weather: {weather_data}
- Recommended venues: {venues}

Return JSON with sections: itinerary, packing, tips, budget, transport, safety, closing
"""
```

**Sections Generated**:
- **Itinerary**: Day-by-day activities (morning/afternoon/evening)
- **Packing**: Categorized items (Clothing, Electronics, Documents, etc.)
- **Budget**: Daily cost estimates by category
- **Tips**: Local insights and recommendations
- **Transport**: Getting around options
- **Safety**: Important safety information
- **Closing**: Personalized farewell message

### 4. Data Enhancement & Enrichment

**Weather Integration**:
- Fetches 7-day forecast from OpenWeatherMap
- Influences packing recommendations and activity suggestions

**Visual Content**:
- **City Images**: Unsplash API for hero images
- **QR Codes**: Generated for each recommended place
- **Maps Integration**: Google Maps links for navigation

**Content Processing**:
```python
# Robust JSON parsing with multiple attempts
def robust_json_parse(val):
    tries = 0
    while isinstance(val, str) and tries < 3:
        try:
            val = json.loads(val)
        except Exception:
            break
        tries += 1
    return val
```

### 5. PDF Generation
**Module**: `routes.py` - `download_pdf()`

**Architecture**:
- **Library**: ReportLab for professional PDF creation
- **Layout**: Multi-page document with proper pagination
- **Styling**: Custom color scheme and typography

**PDF Structure**:
1. **Cover Page** (no page numbers)
   - Trip title and destination
   - User information and dates
   - Hero image
   - Qloo branding

2. **Content Pages** (with page breaks)
   - Destination overview with "Why This City?" reasoning
   - Cultural DNA table showing taste mappings
   - Weather forecast table
   - Taste summary
   - Categorized packing checklist
   - Budget estimates table
   - Flight cost estimates
   - Travel essentials (tips, transport, safety)
   - Recommended places with QR codes
   - Day-by-day itinerary with time periods
   - Final message and attribution

**Page Break Logic**:
```python
# Automatic page breaks when content exceeds available space
if y < minimum_space_needed:
    pdf.showPage()
    y = height - 40
```

**Text Processing**:
- **Cleaning**: Removes AI artifacts, markdown, and formatting issues
- **Wrapping**: Intelligent text wrapping for proper layout
- **Styling**: Consistent fonts, colors, and spacing

## 🔧 Key Processing Logic

### Taste Mapping Algorithm
1. **Input Analysis**: Extracts cultural preferences from user input
2. **API Integration**: Queries Qloo for taste-based recommendations
3. **Cultural Bridging**: Maps personal tastes to destination experiences
4. **Venue Matching**: Finds specific locations aligned with preferences

### Content Normalization
```python
# Handles various AI response formats
def normalize_json_section(section):
    if isinstance(section, str):
        parsed = try_parse_json(section)
        return parsed if isinstance(parsed, (dict, list)) else section
    return section
```

### Packing List Intelligence
- **Categorization**: Automatically sorts items into logical groups
- **Weather Integration**: Adjusts recommendations based on forecast
- **Cleaning**: Fixes common AI parsing errors (e.g., 'rncoat' → 'raincoat')

### Error Handling & Fallbacks
- **API Failures**: Graceful degradation with default content
- **Parsing Errors**: Multiple parsing attempts with fallbacks
- **Missing Data**: Sensible defaults and user-friendly messages

## 🚀 User Journey

1. **Input**: User provides travel preferences (structured or text)
2. **Processing**: AI analyzes preferences and recommends destination
3. **Generation**: Comprehensive itinerary created using multiple AI services
4. **Enhancement**: Weather, images, and local data added
5. **Presentation**: Beautiful web interface with all information
6. **Export**: Professional PDF generated for offline use

## 🔑 Key Features

- **AI-Powered Recommendations**: Uses advanced taste profiling
- **Multi-Modal Input**: Accepts both structured and natural language input
- **Comprehensive Planning**: Covers all aspects of travel planning
- **Professional Output**: High-quality PDF suitable for printing
- **Real-Time Data**: Current weather and local information
- **Mobile-Friendly**: QR codes for easy navigation
- **Personalized**: Every recommendation tailored to user's taste profile

## 📊 Data Flow Summary

```
User Input → Text Parsing (AI) → Taste Analysis (Qloo) → 
City Recommendation → Itinerary Generation (AI) → 
Data Enhancement (Weather/Images) → Web Display → PDF Export
```

## 🛠️ Setup & Installation

```bash
git clone https://github.com/yourname/taste-trip.git
cd taste-trip
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export QLOO_API_KEY="your_qloo_key"
export TOGETHER_API_KEY="your_together_key"
export UNSPLASH_ACCESS_KEY="your_unsplash_key"
export WEATHER_API_KEY="your_weather_key"

python app.py
```

## 🔐 Environment Variables Required

- `QLOO_API_KEY`: Qloo Taste AI API key
- `TOGETHER_API_KEY`: Together AI API key
- `UNSPLASH_ACCESS_KEY`: Unsplash API key
- `WEATHER_API_KEY`: OpenWeatherMap API key

## 📝 API Rate Limits & Costs

- **Qloo**: Taste profiling and recommendations
- **Together AI**: Primary AI generation (cost-effective)
- **Unsplash**: Image fetching (free tier available)
- **OpenWeatherMap**: Weather data (free tier available)

## 🎯 Future Enhancements

- Real-time flight price integration
- Multi-language support
- Collaborative trip planning
- Mobile app development
- Advanced personalization algorithms

---

*Maintained by SOLOMON OMONDI ODIPO, IT ENGINEER, SEA-TECH(K) LTD.*