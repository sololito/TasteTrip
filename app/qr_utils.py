import qrcode
import io
from flask import send_file
from PIL import Image

def generate_qr_code(data):
    """Generate a QR code image for the given data and return a Flask send_file response."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

def create_direction_qr(start_location, destination, city):
    """Create QR code for directions between two locations"""
    from .geodb_api import get_route_url
    from .maps_utils import google_maps_link
    
    # Try Geoapify routing first, fallback to Google Maps
    route_url = get_route_url(start_location, destination)
    if not route_url:
        # Fallback to Google Maps
        route_url = google_maps_link(destination, city)
    
    return generate_qr_image_data(route_url)

def generate_qr_image_data(data):
    """Generate QR code and return image data for PDF embedding"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes for PDF embedding
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_place_qr_codes(places, city_name):
    """Generate QR codes for multiple places"""
    qr_codes = {}
    
    for place in places:
        try:
            # Create Google Maps link for the place
            from .maps_utils import google_maps_link
            maps_url = google_maps_link(place, city_name)
            
            # Generate QR code data
            qr_data = generate_qr_image_data(maps_url)
            qr_codes[place] = qr_data
        except Exception as e:
            print(f"Error generating QR for {place}: {e}")
    
    return qr_codes
