# FilmHive API (Backend) — Django REST Framework 🎬

FilmHive API is the Django REST Framework back-end for the FilmHive platform. It provides a secure, well-structured REST API for film discovery (via a lightweight TMDB cache), reviews, likes, favourites, watchlists, and user profile preferences.

This repository is the **backend only** (separate from the React frontend README, which can be found [here](https://github.com/Kerem-Haeger/filmhive_frontend/blob/main/README.md)).

---

## Project Purpose

FilmHive aims to make choosing a film easier by combining:

- **Fast discovery** (browse/search/filter)
- **User-driven signals** (ratings, reviews, likes)
- **Personal organisation** (favourites + watchlists)
- **Personalisation** (recommendations and preference storage)

The API is designed to be consumed by the FilmHive React frontend and follows REST conventions with secure authentication and permission-based access control.

---

## Target Audience

- Casual viewers who want **simple browsing** without needing an account
- Logged-in users who want to **save**, **review**, and **curate** films
- Users who value community input via **helpful review likes**

---

## Key Features

### Public (no login required)
- List films and view film detail (from the local TMDB cache)
- Browse by genre and view associated metadata (runtime, popularity, critic score where available)
- Read reviews for a film

### Authenticated (login required)
- Create/update/delete **your own** reviews (one review per film per user)
- Like/unlike reviews (prevent duplicate likes)
- Add/remove favourites
- Create and manage watchlist entries (supports **multiple named lists** per user)
- Maintain a user profile (e.g. preferred genres)

---
## API Base URL

All API requests are served from the deployed backend:

```
https://filmhive-api-7c5c6cd06ecf.herokuapp.com
```

---

## Authentication & API Access

FilmHive uses **dj-rest-auth** with **django-allauth** for user registration and authentication.  
Authentication is handled via **DRF TokenAuthentication** (not JWT).

### Auth Endpoints

All auth endpoints are prefixed with `/api/auth/`:

- `POST /api/auth/login/` — Log in (returns auth token)
- `POST /api/auth/logout/` — Log out (invalidates token)
- `POST /api/auth/registration/` — Register a new user
- `GET /api/auth/user/` — Retrieve the currently authenticated user

The frontend stores the returned token and includes it in the `Authorization` header for protected requests:

```
Authorization: Token <user_token>
```

---

## CORS Configuration

CORS is configured to support separate frontend deployments.

Allowed origins are dynamically loaded from environment variables:

- `CLIENT_ORIGIN`
- `CLIENT_ORIGIN_DEV`

Additionally, the following frontend domain is explicitly trusted:

```
https://filmhive-85b95f07d5b8.herokuapp.com
```

This setup ensures:
- Public read-only endpoints remain accessible
- Authenticated requests are securely restricted
- The deployed frontend can safely communicate with the API

---
## API Users and Permissions

FilmHive uses Django's built-in `auth_user` model for authentication.

Typical access rules:
- **Read-only** endpoints are public where appropriate (e.g., films, genres, public reviews).
- **Write** actions require authentication.
- Users can **only edit/delete their own** resources (e.g., reviews, favourites, watchlists).
- Duplicate actions are prevented with DB uniqueness constraints (e.g., one like per user per review).

This aligns with the requirement that users must not be permitted write access to restricted content/functionality.

---

## Data Model

The database schema is designed around a **thin local cache** of TMDB film data plus FilmHive user interactions.

### Core domain entities

**Films**
- `films` stores minimal film data (UUID PK) and a unique `tmdb_id`
- Includes metadata for filtering and ranking (year, runtime, popularity, critic_score)

**Taxonomy**
- `genres` + `film_genres` (many-to-many)
- `keywords` + `film_keywords` (many-to-many)

**People**
- `people` + `film_people` for cast/director links with role + billing order

### User-generated content
- `reviews` (one per user per film enforced by unique index)
- `review_likes` (one per user per review enforced by unique index)
- `review_reports` (one report per user per review enforced by unique index, reports create a record for admin review via Django admin.)

### User collections
- `favourites` (one per user per film enforced by unique index)
- `watchlists` supports **multiple named lists** per user (and prevents duplicates per list)

### User profile
- `user_profiles` stores preferences (e.g., `preferred_genres` JSON)

### Database Schema Overview

The following table summarises the ERD entities described above.

The FilmHive backend uses a relational PostgreSQL database designed to support film discovery, user interaction, and personal curation.  
The schema enforces data integrity through foreign keys, unique constraints, and indexed relationships.

#### Core Tables

| Table Name | Purpose |
|-----------|--------|
| `auth_user` | Django's built-in user table used for authentication, permissions, and account management |
| `films` | Stores cached film metadata sourced from TMDB |
| `genres` | Stores film genres sourced from TMDB |
| `keywords` | Stores film keywords used for tagging and filtering |
| `people` | Stores people associated with films (cast and directors) |

#### Relationship Tables (Many-to-Many)

| Table Name | Purpose |
|-----------|--------|
| `film_genres` | Links films to genres (many-to-many) |
| `film_keywords` | Links films to keywords (many-to-many) |
| `film_people` | Links films to people with role (`cast` or `director`) and billing order |

#### User Interaction Tables

| Table Name | Purpose |
|-----------|--------|
| `reviews` | Stores user-written reviews for films (one per user per film) |
| `review_likes` | Tracks which users have liked which reviews |
| `review_reports` | Reports create a record for admin review via Django admin. |

#### User Collection Tables

| Table Name | Purpose |
|-----------|--------|
| `favourites` | Stores films marked as favourites by users |
| `watchlists` | Stores user-created watchlists (supports multiple named lists per user) |

#### User Profile Table

| Table Name | Purpose |
|-----------|--------|
| `user_profiles` | Stores additional user preferences such as preferred genres |

#### Data Integrity & Constraints

- One review per user per film is enforced via a unique constraint on `reviews (user_id, film_id)`
- Duplicate likes, favourites, and watchlist entries are prevented using composite unique indexes
- Foreign key constraints ensure referential integrity between users, films, and related entities
- UUID primary keys are used for most domain tables to improve security and scalability

![ERD](documentation/erd.png)

---

## Endpoints

### Films (public read)
- `GET /films/` — list films (supports search/filter/order)
- `GET /films/{id}/` — film detail
- `POST /films/sync/` *(admin/maintenance or internal)* — fetch from TMDB and store/update cache

### Genres / Keywords / People (public read)
- `GET /genres/`
- `GET /keywords/`
- `GET /people/`

### Reviews
- `GET /reviews/` — list (filterable by film)
- `POST /reviews/` — create (auth required)
- `GET /reviews/{id}/`
- `PUT/PATCH /reviews/{id}/` — owner only
- `DELETE /reviews/{id}/` — owner only

### Review Likes
- `POST /review-likes/` — like a review (auth required, unique per user/review)
- `DELETE /review-likes/{id}/` — unlike (owner only)

### Favourites
- `GET /favourites/` — list mine (auth required)
- `POST /favourites/` — add favourite
- `DELETE /favourites/{id}/` — remove favourite

### Watchlists (multi-list design)
- `GET /watchlists/` — list mine (auth required)
- `POST /watchlists/` — add film to a named list
- `PATCH /watchlists/{id}/` — update (position, privacy, etc.)
- `DELETE /watchlists/{id}/` — remove entry

### Reports
- `POST /review-reports/` — report a review (auth required)

This structure demonstrates framework-specific features (serializers, permissions, generic views) and full CRUD for core resources.

---

## TMDB Data Strategy

“We seed ~1500 films once using a management command. No runtime TMDB calls in production.”

---

## Search, Filter, Ordering

To meet the requirement that users can easily find what they’re looking for (Merit), the API supports:

- **Search** (e.g., title)
- **Filtering** (e.g., year, runtime ranges, genres, popularity)
- **Ordering** (e.g., by popularity, year, critic_score)

Implementation commonly uses DRF:
- `SearchFilter`
- `DjangoFilterBackend`
- `OrderingFilter`

This is especially important for the films list endpoint, where discoverability is the product.

---

## Tech Stack

- Python + Django
- Django REST Framework
- PostgreSQL
- dj-rest-auth with DRF Token Authentication
- CORS support for React frontend integration

---

## Installation and Local Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Kerem-Haeger/filmhive_backend.git
   cd filmhive_backend
   ```

2. **Create and activate a virtual environment:**
   
   **Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   
   **macOS/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   
   Create an `env.py` file in the project root (same level as `manage.py`):
   
   ```python
   import os
   
   os.environ.setdefault("SECRET_KEY", "your-secret-key-here")
   os.environ.setdefault("DEV", "1")  # Enables SQLite for local dev
   os.environ.setdefault("TMDB_API_KEY", "your-tmdb-api-key")
   os.environ.setdefault("SITE_ID", "1")
   ```
   
   **Note:** `env.py` is in `.gitignore` and will not be committed to the repository.

5. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser (optional, for admin access):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Seed the database with TMDB films (optional):**
   ```bash
   python manage.py seed_tmdb_films
   ```

8. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

   The API will be available at `http://localhost:8000/`

### Obtaining a TMDB API Key

1. Create a free account at [https://www.themoviedb.org/](https://www.themoviedb.org/)
2. Go to Settings → API
3. Request an API key (choose "Developer" option)
4. Copy your API key and add it to your `env.py` file

---

## Environment Variables

The FilmHive API requires several environment variables for configuration. In local development, these are stored in `env.py`. In production (Heroku), they are configured as Config Vars.

### Required Variables

| Variable | Description | Example |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key for cryptographic signing | `django-insecure-abc123...` |
| `TMDB_API_KEY` | API key for The Movie Database (TMDB) | `a1b2c3d4e5f6...` |
| `DATABASE_URL` | PostgreSQL database connection string (production only) | `postgres://user:pass@host:5432/db` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|----------|
| `DEV` | Enables development mode (uses SQLite instead of PostgreSQL) | Not set | `1` |
| `DEBUG` | Django debug mode (should be `False` in production) | `False` | `True` |
| `SITE_ID` | Django sites framework site ID | `1` | `1` |
| `CLIENT_ORIGIN` | Production frontend URL for CORS | Not set | `https://filmhive-85b95f07d5b8.herokuapp.com` |
| `CLIENT_ORIGIN_DEV` | Development frontend URL for CORS | Not set | `http://localhost:3000` |

### Example `env.py` for Local Development

```python
import os

# Security
os.environ.setdefault("SECRET_KEY", "your-django-secret-key-here")
os.environ.setdefault("DEBUG", "True")

# Database (SQLite for local development)
os.environ.setdefault("DEV", "1")

# TMDB Integration
os.environ.setdefault("TMDB_API_KEY", "your-tmdb-api-key-here")

# Django Sites Framework
os.environ.setdefault("SITE_ID", "1")

# CORS (optional for local development)
os.environ.setdefault("CLIENT_ORIGIN_DEV", "http://localhost:3000")
```

### Production Environment Variables (Heroku Config Vars)

In production, set the following in Heroku:

```bash
heroku config:set SECRET_KEY="your-production-secret-key"
heroku config:set DEBUG="False"
heroku config:set TMDB_API_KEY="your-tmdb-api-key"
heroku config:set CLIENT_ORIGIN="https://your-frontend-domain.com"
heroku config:set SITE_ID="1"
```

**Note:** `DATABASE_URL` is automatically set by Heroku when you attach a Postgres add-on.

### Generating a Django Secret Key

To generate a secure secret key for production:

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Deployment

The FilmHive API is deployed to Heroku.

Full deployment steps, configuration details, and production notes are documented in
[DEPLOYMENT.md](DEPLOYMENT.md).

> **Note:**  
> A small number of test user accounts and reviews have been intentionally left in the deployed database to demonstrate review creation, permissions, and aggregation behaviour.  
> Reviews are primarily associated with a limited set of films (e.g. *The Avengers*) to make assessment and testing clearer.

---

## Testing

For detailed information about testing, including test coverage, validation procedures, and results, please see [TESTING.md](TESTING.md).

---

## Security

FilmHive API follows standard security practices:

- Sensitive values stored in environment variables (not in repo)
- DEBUG=False in production
- Auth required for write actions
- Owner-only permissions on user-owned data
- Database constraints to prevent duplicate interactions (likes/favourites/reviews/watchlist items)
- CORS restricted to the frontend domain(s)

These directly support the project's security and access-control criteria.

---

## Future Improvements

- Enhance recommendation algorithms for the For You feed (personalized suggestions based on user preferences and viewing history)
- Improve Blend Mode matching algorithm to provide better shared recommendations
- Expand test coverage for edge cases and complex permission scenarios
- Add rate-limiting / throttling for additional abuse protection

---

## Credits

TMDB API is used as the external film metadata provider (FilmHive stores only a minimal cache).

