# reviews/tests.py

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from films.models import Film
from .models import Review

User = get_user_model()


class ReviewAPITests(APITestCase):
    def setUp(self):
        # create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # create film
        self.film = Film.objects.create(
            title="Review Film",
            year=2024,
            tmdb_id=456,
            poster_path="/test2.jpg",
            runtime=100,
            critic_score=7.0,
            popularity=5.0,
        )

        self.review_list_url = reverse("review-list")  # from router

    def test_anonymous_cannot_create_review(self):
        payload = {
            "film": str(self.film.id),
            "rating": 8,
            "body": "Great movie!",
        }
        response = self.client.post(self.review_list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Review.objects.count(), 0)

    def test_authenticated_user_can_create_review(self):
        self.client.login(username="testuser", password="testpass123")

        payload = {
            "film": str(self.film.id),
            "rating": 9,
            "body": "Loved it!",
        }
        response = self.client.post(self.review_list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)

        review = Review.objects.first()
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.film, self.film)
        self.assertEqual(review.rating, 9)

    def test_user_cannot_review_same_film_twice(self):
        self.client.login(username="testuser", password="testpass123")

        payload = {
            "film": str(self.film.id),
            "rating": 7,
            "body": "First review",
        }
        first_response = self.client.post(self.review_list_url, payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        # try again for same film
        second_response = self.client.post(self.review_list_url, payload, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)
