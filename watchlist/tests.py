# watchlist/tests.py

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from films.models import Film
from .models import Watchlist

User = get_user_model()


class WatchlistAPITests(APITestCase):
    def setUp(self):
        # user
        self.user = User.objects.create_user(
            username="watchuser",
            email="watch@example.com",
            password="testpass123",
        )

        # films
        self.film = Film.objects.create(
            title="Watchlist Film",
            year=2024,
            tmdb_id=900,
            poster_path="/watch.jpg",
            runtime=100,
            critic_score=7.5,
            popularity=4.0,
        )

        # from router: basename="watchlist"
        self.watchlist_url = reverse("watchlist-list")

    def test_anonymous_cannot_add_watchlist_item(self):
        payload = {"film": str(self.film.id)}
        response = self.client.post(self.watchlist_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Watchlist.objects.count(), 0)

    def test_authenticated_user_can_add_watchlist_item(self):
        self.client.login(username="watchuser", password="testpass123")

        # no name sent -> should use default "Watchlist"
        payload = {"film": str(self.film.id)}
        response = self.client.post(self.watchlist_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Watchlist.objects.count(), 1)

        item = Watchlist.objects.first()
        self.assertEqual(item.user, self.user)
        self.assertEqual(item.film, self.film)
        self.assertEqual(item.name, "Watchlist")

    def test_user_cannot_add_same_film_twice_to_same_list(self):
        self.client.login(username="watchuser", password="testpass123")

        payload = {"film": str(self.film.id), "name": "Watchlist"}

        first = self.client.post(self.watchlist_url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Watchlist.objects.count(), 1)

        second = self.client.post(self.watchlist_url, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Watchlist.objects.count(), 1)

    def test_list_returns_only_user_watchlist_items(self):
        # our user's item
        Watchlist.objects.create(
            user=self.user,
            film=self.film,
            name="Watchlist",
        )

        # another user + another watchlist item (should not be visible)
        other = User.objects.create_user(
            username="otherwatch",
            email="otherwatch@example.com",
            password="otherpass123",
        )
        other_film = Film.objects.create(
            title="Other Watch Film",
            year=2023,
            tmdb_id=901,
            poster_path="/otherwatch.jpg",
            runtime=110,
            critic_score=6.0,
            popularity=2.0,
        )
        Watchlist.objects.create(
            user=other,
            film=other_film,
            name="Watchlist",
        )

        self.client.login(username="watchuser", password="testpass123")

        response = self.client.get(self.watchlist_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        # film is returned as UUID, compare to our film id
        self.assertEqual(response.data[0]["film"], self.film.id)
