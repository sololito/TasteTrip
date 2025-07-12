import unittest
from app import create_app

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TasteTrip", response.data)

    def test_itinerary_route_post(self):
        response = self.app.post('/itinerary', data={
            "music": "Jazz",
            "movie": "Amélie",
            "food": "French"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your Trip to", response.data)

if __name__ == '__main__':
    unittest.main()
