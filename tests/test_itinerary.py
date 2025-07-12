import unittest
from unittest.mock import patch
from app.itinerary import generate_itinerary

class TestItinerary(unittest.TestCase):
    @patch('app.itinerary.openai.ChatCompletion.create')
    def test_itinerary_returns_text(self, mock_openai):
        # Mock the OpenAI API response
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": "Mocked itinerary response."
                }
            }]
        }

        taste_data = {
            "city": "Barcelona",
            "themes": ["music", "food", "art"]
        }

        itinerary = generate_itinerary(taste_data)
        self.assertIsInstance(itinerary, str)
        self.assertIn("Mocked itinerary", itinerary)

if __name__ == '__main__':
    unittest.main()
