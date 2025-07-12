# run.py
from app import create_app

# Create Flask app instance using factory pattern
app = create_app()

if __name__ == '__main__':
    # Run the Flask app in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000)
