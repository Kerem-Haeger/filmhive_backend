# Deployment (Heroku)

This document describes how the FilmHive **backend API** is deployed to Heroku for assessment.

The deployment is intentionally simple:
- Heroku **web dyno** for the Django API
- Database is a **managed PostgreSQL instance provided by Code Institute** (not a Heroku Postgres add-on)
- TMDB seeding is only used in development and **does not need to be repeated in production**, because the production database is already populated for the deployed API

---

## Platform

- **Hosting:** Heroku (web dyno)
- **Database:** Code Institute PostgreSQL (connected via `DATABASE_URL`)
- **Static handling:** not required for the API deployment
  - `DISABLE_COLLECTSTATIC=1` is set

---

## Required Config Vars (Heroku)

These environment variables must be set in the Heroku app **Settings → Config Vars**.

| Key | Required | Notes |
|---|---:|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (Code Institute DB) |
| `TMDB_API_KEY` | ✅ | Used for development-only seeding / optional internal tasks |
| `CLIENT_ORIGIN` | ✅ | Allowed frontend origin for CORS (production frontend URL) |
| `DISABLE_COLLECTSTATIC` | ✅ | Set to `1` for API deployment |

> Note: Values are not included here for security reasons.

---

## Deployment Steps (Heroku)

### 1. Create the Heroku app
Create a new Heroku application from the Heroku dashboard.

### 2. Set Config Vars
In **Settings → Config Vars**, add the variables listed above.

### 3. Connect the GitHub repository
In **Deploy → Deployment method**, connect the GitHub repository containing the FilmHive backend.

> Automatic deploys are not enabled for this project. Deployments are performed manually from Heroku.

### 4. Ensure required files exist in the repo
The repository must include:
- `requirements.txt`
- `Procfile` (Gunicorn)
- `runtime.txt` (optional but recommended if pinning Python version)

Example `Procfile`:

```
web: gunicorn filmhive.wsgi
```

### 5. Deploy the branch
Use Heroku’s manual deploy option to deploy the selected branch.

### 6. Run migrations
After deployment, apply database migrations:

```bash
heroku run python manage.py migrate --app <HEROKU_APP_NAME>
```

### 7. Create a superuser (optional)

Optional for admin access:

```bash
heroku run python manage.py createsuperuser --app <HEROKU_APP_NAME>
```
---

## Database Note (Important)

This project uses a PostgreSQL database provided by Code Institute and connected via `DATABASE_URL`.

As a result:

- A Heroku Postgres add-on is not required
- The deployed API already has the film dataset available in the connected database
- The TMDB seeding command (`seed_tmdb_films`) is used in development only and is not required to be run in production for assessment

---

## Post-deployment Checks

After deployment, confirm:

- API is reachable at the deployed base URL
- Public endpoints work (e.g. films list)
- Protected endpoints reject unauthenticated requests
- Auth flow works (login returns token)
- CORS allows requests from the configured frontend origin (`CLIENT_ORIGIN`)

---

## Troubleshooting

### CORS Errors

- Confirm `CLIENT_ORIGIN` matches the deployed frontend domain exactly (protocol included)
- Ensure CORS middleware is enabled and configured in Django settings

### 500 Errors on Deploy

Check Heroku logs:

```bash
heroku logs --tail --app <HEROKU_APP_NAME>
```

Confirm:
- `SECRET_KEY` and `DATABASE_URL` are present
- Migrations were run successfully