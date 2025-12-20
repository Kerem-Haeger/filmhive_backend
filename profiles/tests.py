from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import UserProfile

User = get_user_model()


class UserProfileSignalTests(APITestCase):
    """Tests for automatic profile creation via signals."""

    def test_profile_created_on_user_registration(self):
        """Profile should be automatically created when user is created."""
        user = User.objects.create_user(
            username="newuser",
            email="newuser@example.com",
            password="testpass123",
        )

        # Profile should exist
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsInstance(user.profile, UserProfile)
        self.assertEqual(user.profile.user, user)

    def test_profile_has_default_preferred_genres(self):
        """New profile should have empty list for preferred_genres."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.assertEqual(user.profile.preferred_genres, [])


class MyProfileViewTests(APITestCase):
    """Tests for the /api/profiles/me/ endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.url = reverse("my-profile")

    def test_retrieve_profile_requires_authentication(self):
        """Unauthenticated users should get 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_own_profile(self):
        """Authenticated user should be able to retrieve their profile."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.user.profile.id))
        self.assertEqual(response.data["preferred_genres"], [])
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)

    def test_update_profile_requires_authentication(self):
        """Unauthenticated users should not be able to update profile."""
        response = self.client.patch(
            self.url,
            {"preferred_genres": [1, 2, 3]},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_preferred_genres(self):
        """User should be able to update their preferred genres."""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.url,
            {"preferred_genres": [28, 53, 18]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferred_genres"], [28, 53, 18])

        # Verify in database
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.preferred_genres, [28, 53, 18])

    def test_update_with_put(self):
        """User should be able to update profile with PUT."""
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            self.url,
            {"preferred_genres": [12, 35]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferred_genres"], [12, 35])

    def test_update_clears_preferred_genres(self):
        """User should be able to clear their preferred genres."""
        self.client.force_authenticate(user=self.user)

        # First set some genres
        self.user.profile.preferred_genres = [28, 53]
        self.user.profile.save()

        # Then clear them
        response = self.client.patch(
            self.url,
            {"preferred_genres": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferred_genres"], [])

    def test_readonly_fields_not_updated(self):
        """id, created_at, and updated_at should be read-only."""
        self.client.force_authenticate(user=self.user)

        original_id = str(self.user.profile.id)
        original_created = self.user.profile.created_at

        response = self.client.patch(
            self.url,
            {
                "id": "00000000-0000-0000-0000-000000000000",
                "created_at": "2020-01-01T00:00:00Z",
                "preferred_genres": [28],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # ID and created_at should remain unchanged
        self.assertEqual(response.data["id"], original_id)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.created_at, original_created)

    def test_multiple_users_have_separate_profiles(self):
        """Each user should have their own profile."""
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        # Update user1's profile
        self.client.force_authenticate(user=self.user)
        self.client.patch(
            self.url,
            {"preferred_genres": [28]},
            format="json",
        )

        # Check user2's profile is separate
        self.client.force_authenticate(user=user2)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferred_genres"], [])
        self.assertNotEqual(response.data["id"], str(self.user.profile.id))

    def test_profile_str_representation(self):
        """Profile __str__ should return formatted string."""
        expected = f"Profile<{self.user.id}>"
        self.assertEqual(str(self.user.profile), expected)
