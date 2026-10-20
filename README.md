# Workout Tracker API

## Description

Workout Tracker API is a RESTful API built with Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Bcrypt, and Flask-JWT-Extended.

Users can register and log in, receive a JSON Web Token (JWT), and manage their own workout records. Protected endpoints require JWT authentication, and users cannot view, update, or delete workouts belonging to other users.

Each workout stores an activity, its duration in minutes, and the ID of the user who created it.

## Technologies

- Python
- Flask
- Flask-SQLAlchemy and SQLAlchemy
- Flask-Migrate and Alembic
- Flask-Bcrypt
- Flask-JWT-Extended
- SQLite
- Pytest
- Pipenv

## Requirements

- Python 3
- Pipenv
- Git

## Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/moseslenkai803-source/moringa-flask-summative-jwt.git
cd moringa-flask-summative-jwt
```

Install the project dependencies:

```bash
pipenv install
```

If the project uses a committed `Pipfile.lock`, Pipenv will use it to resolve the locked dependencies.

## Environment Configuration

The application supports these environment variables:

- `SECRET_KEY`: Flask application secret.
- `JWT_SECRET_KEY`: secret used to sign JWTs.
- `DATABASE_URL`: database connection URI. Defaults to `sqlite:///workout_tracker.db`.

When these variables are not set, the application uses development defaults.
Do not use those defaults in production. Set strong, unique secret values
through environment variables when deploying, and never commit production
secrets to Git.

## Database Setup

Apply the database migrations:

```bash
pipenv run flask --app server.app db upgrade
```

Check the current migration:

```bash
pipenv run flask --app server.app db current
```

## Running the Application

Start the Flask development server:

```bash
pipenv run flask --app server.app run
```

The API will normally be available at:

`http://127.0.0.1:5000`

## API Endpoints

| Method | Endpoint | Description | Authentication |

| GET | `/` | Home route | No |
| POST | `/signup` | Register a user | No |
| POST | `/login` | Log in and obtain a JWT | No |
| GET | `/me` | Get the authenticated user's information | JWT |
| POST | `/workouts` | Create a workout | JWT |
| GET | `/workouts` | List the authenticated user's workouts with pagination | JWT |
| GET | `/workouts/<workout_id>` | Retrieve a workout owned by the authenticated user | JWT |
| PATCH | `/workouts/<workout_id>` | Update an owned workout | JWT |
| DELETE | `/workouts/<workout_id>` | Delete an owned workout | JWT |

### Authentication

For protected endpoints, send the access token in the request header:

```text
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Workout Fields

A workout uses these fields:

- `activity`: the activity name.
- `duration_minutes`: a positive integer representing the duration.
- `user_id`: the ID of the user who owns the workout; assigned by the API.

Example workout request body:

```json
{
  "activity": "Running",
  "duration_minutes": 30
}
```

### Pagination

The workout listing endpoint accepts `page` and `per_page` query parameters.

Example:

```text
GET /workouts?page=1&per_page=10
```

The API returns the workout records and pagination metadata. The maximum page size is 100.

## Running Tests

Run the test suite:

```bash
pipenv run python -m pytest -v
```

The tests cover user registration, password hashing, login, JWT authentication, workout CRUD operations, pagination, input validation, and ownership restrictions.

## Security

- Passwords are hashed rather than stored as plain text.
- Protected routes require JWT authentication.
- Users can access and modify only their own workout records.
- Invalid workout updates are rejected.
