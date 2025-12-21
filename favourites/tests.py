# favourites/tests.py

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from films.models import Film
from .models import Favourite

User = get_user_model()


class FavouriteAPITests(APITestCase):
    def setUp(self):
        # user
        self.user = User.objects.create_user(
            username="favuser",
            email="fav@example.com",
            password="testpass123",
        )

        # film
        self.film = Film.objects.create(
            title="Favourite Film",
            year=2024,
            tmdb_id=789,
            poster_path="/fav.jpg",
            runtime=90,
            critic_score=8.0,
            popularity=3.0,
        )

        # from router: router.register("favourites", FavouriteViewSet,
        # basename="favourite")
        self.fav_list_url = reverse("favourite-list")

    def test_anonymous_cannot_add_favourite(self):
        payload = {"film": str(self.film.id)}
        response = self.client.post(self.fav_list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Favourite.objects.count(), 0)

    def test_authenticated_user_can_add_favourite(self):
        self.client.force_authenticate(user=self.user)

        payload = {"film": str(self.film.id)}
        response = self.client.post(self.fav_list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Favourite.objects.count(), 1)

        fav = Favourite.objects.first()
        self.assertEqual(fav.user, self.user)
        self.assertEqual(fav.film, self.film)

    def test_user_cannot_add_same_film_twice(self):
        self.client.force_authenticate(user=self.user)

        payload = {"film": str(self.film.id)}

        first = self.client.post(self.fav_list_url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Favourite.objects.count(), 1)

        second = self.client.post(self.fav_list_url, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Favourite.objects.count(), 1)

    def test_list_returns_only_user_favourites(self):
        # create favourite for our user
        Favourite.objects.create(user=self.user, film=self.film)

        # another user + favourite (should not appear in our list)
        other = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123",
        )
        other_film = Film.objects.create(
            title="Other Film",
            year=2023,
            tmdb_id=790,
            poster_path="/other.jpg",
            runtime=110,
            critic_score=6.0,
            popularity=1.0,
        )
        Favourite.objects.create(user=other, film=other_film)

        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.fav_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["film"], self.film.id)
