from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Film


class FilmAPITests(APITestCase):
    def setUp(self):
        self.film = Film.objects.create(
            title="Test Film",
            year=2024,
            tmdb_id=123,
            poster_path="/test.jpg",
            runtime=120,
            critic_score=8.5,
            popularity=10.0,
        )

    def test_list_films_returns_200_and_includes_film(self):
        url = reverse("film-list")  # /api/films/
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        titles = [item["title"] for item in response.data]
        self.assertIn("Test Film", titles)

    def test_retrieve_single_film(self):
        url = reverse("film-detail", args=[self.film.id])  # /api/films/<id>/
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Film")
        # annotated fields should exist
        self.assertIn("average_rating", response.data)
        self.assertIn("review_count", response.data)
        self.assertIn("is_favourited", response.data)
        self.assertIn("in_watchlist", response.data)
