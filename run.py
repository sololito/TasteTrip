# run.py
from app import create_app
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Create Flask app instance using factory pattern
app = create_app()

if __name__ == '__main__':
    # Use PORT from environment if available (Render will inject it)
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
