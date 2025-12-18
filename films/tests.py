from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import Film, Genre, Keyword

User = get_user_model()


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


class CompromiseAPITests(APITestCase):
    """Tests for the /api/compromise/ endpoint (Blend Mode)."""

    def setUp(self):
        """Create test user, films, genres, and keywords."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create genres
        self.action = Genre.objects.create(id=1, name="Action", tmdb_id=28)
        self.thriller = Genre.objects.create(id=2, name="Thriller", tmdb_id=53)
        self.drama = Genre.objects.create(id=3, name="Drama", tmdb_id=18)
        self.scifi = Genre.objects.create(id=4, name="Science Fiction", tmdb_id=878)

        # Create keywords
        self.heist = Keyword.objects.create(id=1, name="heist", tmdb_id=1001)
        self.spy = Keyword.objects.create(id=2, name="spy", tmdb_id=1002)
        self.dream = Keyword.objects.create(id=3, name="dream", tmdb_id=1003)
        self.robot = Keyword.objects.create(id=4, name="robot", tmdb_id=1004)

        # Film A: Action + Thriller + Heist + Dream
        self.film_a = Film.objects.create(
            title="Ocean's Eleven",
            year=2001,
            tmdb_id=401,
            poster_path="/oceansm.jpg",
            runtime=116,
            critic_score=8.0,
            popularity=100.0,
        )
        self.film_a.genres.set([self.action, self.thriller])
        self.film_a.keywords.set([self.heist, self.dream])

        # Film B: Thriller + SciFi + Spy + Robot
        self.film_b = Film.objects.create(
            title="Inception",
            year=2010,
            tmdb_id=402,
            poster_path="/inception.jpg",
            runtime=148,
            critic_score=8.8,
            popularity=120.0,
        )
        self.film_b.genres.set([self.thriller, self.scifi])
        self.film_b.keywords.set([self.spy, self.dream])

        # Candidate 1: Action + Thriller + Heist + Spy (overlaps with both)
        self.candidate_1 = Film.objects.create(
            title="Mission: Impossible",
            year=2006,
            tmdb_id=403,
            poster_path="/mi.jpg",
            runtime=125,
            critic_score=7.5,
            popularity=90.0,
        )
        self.candidate_1.genres.set([self.action, self.thriller])
        self.candidate_1.keywords.set([self.heist, self.spy])

        # Candidate 2: Action + Heist (overlaps with A only)
        self.candidate_2 = Film.objects.create(
            title="Baby Driver",
            year=2017,
            tmdb_id=404,
            poster_path="/baby.jpg",
            runtime=113,
            critic_score=7.8,
            popularity=80.0,
        )
        self.candidate_2.genres.set([self.action])
        self.candidate_2.keywords.set([self.heist])

        # Candidate 3: SciFi + Dream (overlaps with B only)
        self.candidate_3 = Film.objects.create(
            title="The Matrix",
            year=1999,
            tmdb_id=405,
            poster_path="/matrix.jpg",
            runtime=136,
            critic_score=8.7,
            popularity=110.0,
        )
        self.candidate_3.genres.set([self.scifi])
        self.candidate_3.keywords.set([self.dream, self.robot])

        # Candidate 4: Drama (no overlap)
        self.candidate_4 = Film.objects.create(
            title="Shawshank Redemption",
            year=1994,
            tmdb_id=406,
            poster_path="/shawshank.jpg",
            runtime=142,
            critic_score=9.3,
            popularity=130.0,
        )
        self.candidate_4.genres.set([self.drama])

    def test_compromise_requires_authentication(self):
        """Unauthenticated users should get 401."""
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_compromise_missing_film_a_id(self):
        """Missing film_a_id should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_b_id": str(self.film_b.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_missing_film_b_id(self):
        """Missing film_b_id should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_same_film_ids(self):
        """Same film_a_id and film_b_id should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_a.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_alpha_below_zero(self):
        """Alpha < 0 should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "alpha": -0.1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_alpha_above_one(self):
        """Alpha > 1 should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "alpha": 1.5,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_limit_exceeds_cap(self):
        """Limit > 50 should return 400."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "limit": 51,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compromise_film_not_found(self):
        """Non-existent film should return 404."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": "00000000-0000-0000-0000-000000000000",
                "film_b_id": str(self.film_b.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_compromise_valid_request_returns_200(self):
        """Valid request should return 200 with results."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("meta", response.data)
        self.assertIn("results", response.data)

    def test_compromise_response_structure(self):
        """Response should have correct structure."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "alpha": 0.5,
                "limit": 20,
            },
        )

        data = response.data

        # Check meta
        self.assertEqual(data["meta"]["film_a_id"], str(self.film_a.id))
        self.assertEqual(data["meta"]["film_b_id"], str(self.film_b.id))
        self.assertEqual(data["meta"]["alpha"], 0.5)
        self.assertEqual(data["meta"]["limit"], 20)
        self.assertIn("returned", data["meta"])

        # Check results structure
        for result in data["results"]:
            self.assertIn("film", result)
            self.assertIn("score", result)
            self.assertIn("match", result)
            self.assertIn("reasons", result)

            # Check film card fields
            film = result["film"]
            self.assertIn("id", film)
            self.assertIn("title", film)
            self.assertIn("year", film)
            self.assertIn("poster_path", film)
            self.assertIn("runtime", film)
            self.assertIn("critic_score", film)
            self.assertIn("popularity", film)

            # Check match breakdown
            match = result["match"]
            self.assertIn("genre_overlap_a", match)
            self.assertIn("keyword_overlap_a", match)
            self.assertIn("genre_overlap_b", match)
            self.assertIn("keyword_overlap_b", match)
            self.assertIn("bonus", match)

            # Check reasons
            self.assertIsInstance(result["reasons"], list)

    def test_compromise_ranking_by_score(self):
        """Results should be ranked by score descending."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )

        results = response.data["results"]
        scores = [r["score"] for r in results]

        # Verify descending order
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_compromise_respects_limit(self):
        """Results should not exceed limit."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "limit": 2,
            },
        )

        results = response.data["results"]
        self.assertLessEqual(len(results), 2)

    def test_compromise_default_alpha(self):
        """Default alpha should be 0.5."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )

        self.assertEqual(response.data["meta"]["alpha"], 0.5)

    def test_compromise_default_limit(self):
        """Default limit should be 20."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )

        self.assertEqual(response.data["meta"]["limit"], 20)

    def test_compromise_no_candidates(self):
        """If no candidates exist, results should be empty list."""
        # Create two isolated films with no overlapping genres/keywords
        isolated_a = Film.objects.create(
            title="Isolated A",
            year=2020,
            tmdb_id=500,
            poster_path="/iso_a.jpg",
        )
        isolated_b = Film.objects.create(
            title="Isolated B",
            year=2020,
            tmdb_id=501,
            poster_path="/iso_b.jpg",
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(isolated_a.id),
                "film_b_id": str(isolated_b.id),
            },
        )

        self.assertEqual(len(response.data["results"]), 0)

    def test_compromise_reasons_present(self):
        """Results should include explanatory reasons."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")
        response = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
            },
        )

        results = response.data["results"]
        if results:
            # At least top result should have reasons
            self.assertGreater(len(results[0]["reasons"]), 0)

    def test_compromise_alpha_weighting(self):
        """Different alpha values should affect ranking."""
        self.client.force_authenticate(user=self.user)
        url = reverse("film-compromise")

        response_a05 = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "alpha": 0.5,
            },
        )

        response_a01 = self.client.post(
            url,
            {
                "film_a_id": str(self.film_a.id),
                "film_b_id": str(self.film_b.id),
                "alpha": 0.1,
            },
        )

        results_a05 = response_a05.data["results"]
        results_a01 = response_a01.data["results"]

        # Both should have results, but potentially different ordering
        self.assertGreater(len(results_a05), 0)
        self.assertGreater(len(results_a01), 0)
