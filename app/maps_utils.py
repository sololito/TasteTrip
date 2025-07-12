def google_maps_link(place, city=None):
    """Return a Google Maps search link for a place (optionally in a city)."""
    import urllib.parse
    query = f"{place} {city}" if city else place
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"
