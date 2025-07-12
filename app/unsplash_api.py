# app/unsplash_api.py
import os
import requests

def get_image(query):
    # STEP: Unsplash API → city image
    # Input: city name from qloo_api
    # Output: landscape image URL for the destination
    
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={access_key}&orientation=landscape"

    try:
        response = requests.get(url)
        print(f"Unsplash API response status: {response.status_code}")
        if response.status_code == 200:
            image_url = response.json()["urls"]["regular"]
            print(f"Retrieved image URL: {image_url}")
            return image_url
    except Exception as e:
        print(f"Unsplash API error: {e}")

    return "/static/images/logo.png"
