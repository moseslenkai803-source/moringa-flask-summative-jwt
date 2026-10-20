
import pytest

from server import bcrypt
from server import db
from server.app import create_app
from server.models import User


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-jwt-secret-key-at-least-32-bytes",
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_home_route(app):
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Workout Tracker API is running"
    }


def test_signup_route(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "testuser",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "token" in data
    assert data["user"]["username"] == "testuser"

    response = client.post(
        "/signup",
        json={
            "username": "testuser",
            "password": "anotherpassword",
            "password_confirmation": "anotherpassword",
        },
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "errors": ["Username already exists"]
    }

    response = client.post(
        "/signup",
        json={
            "username": "",
            "password": "",
            "password_confirmation": "",
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["All fields are required"]
    }

    response = client.post(
        "/signup",
        json={
            "username": "newuser",
            "password": "password1",
            "password_confirmation": "password2",
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["Passwords do not match"]
    }

def test_signup_stores_hashed_password(app):
    client = app.test_client()
    password = "testpassword"

    response = client.post(
        "/signup",
        json={
            "username": "hashuser",
            "password": password,
            "password_confirmation": password,
        },
    )

    assert response.status_code == 201

    with app.app_context():
        user = User.query.filter_by(username="hashuser").first()

        assert user is not None
        assert user.password_hash != password
        assert bcrypt.check_password_hash(
            user.password_hash, password
        )


def test_login_route(app):
    client = app.test_client()

    client.post(
        "/signup",
        json={
            "username": "loginuser",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )

    response = client.post(
        "/login",
        json={
            "username": "loginuser",
            "password": "testpassword",
        },
    )

    assert response.status_code == 200

    data = response.get_json()
    assert "token" in data
    assert data["user"]["username"] == "loginuser"


def test_me_route_requires_and_returns_authenticated_user(app):
    client = app.test_client()

    # Register a user and obtain a JWT.
    response = client.post(
        "/signup",
        json={
            "username": "meuser",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    assert response.status_code == 201
    token = response.get_json()["token"]

    # Without a token, access should be rejected.
    response = client.get("/me")
    assert response.status_code == 401

    # With a valid token, the user's identity should be returned.
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "id": 1,
        "username": "meuser",
    }


def test_create_workout_requires_authentication_and_saves_owner(app):
    client = app.test_client()

    # A request without a JWT must be rejected.
    response = client.post(
        "/workouts",
        json={
            "activity": "Running",
            "duration_minutes": 30,
        },
    )
    assert response.status_code == 401

    # Register a user and obtain their token.
    response = client.post(
        "/signup",
        json={
            "username": "workoutuser",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    assert response.status_code == 201
    token = response.get_json()["token"]

    # Create a workout using that user's token.
    response = client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "activity": "Running",
            "duration_minutes": 30,
        },
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["activity"] == "Running"
    assert data["duration_minutes"] == 30
    assert data["user_id"] == 1
    assert "id" in data


def test_get_workouts_paginates_and_only_returns_current_users_workouts(app):
    client = app.test_client()

    # Register the first user.
    response = client.post(
        "/signup",
        json={
            "username": "runner1",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    assert response.status_code == 201
    token1 = response.get_json()["token"]

    # Register the second user.
    response = client.post(
        "/signup",
        json={
            "username": "runner2",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    assert response.status_code == 201
    token2 = response.get_json()["token"]

    # Each user creates one workout.
    client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {token1}"},
        json={"activity": "Running", "duration_minutes": 30},
    )
    client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {token2}"},
        json={"activity": "Cycling", "duration_minutes": 45},
    )

    # Listing workouts without a token must be rejected.
    response = client.get("/workouts")
    assert response.status_code == 401

    # The first user should see only their own workout.
    response = client.get(
        "/workouts?page=1&per_page=1",
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["workouts"]) == 1
    assert data["workouts"][0]["activity"] == "Running"
    assert data["workouts"][0]["user_id"] == 1
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 1
    assert data["pagination"]["total"] == 1
    assert data["pagination"]["pages"] == 1


def test_get_single_workout_returns_current_users_workout(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "single_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token = response.get_json()["token"]

    create_response = client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "activity": "Swimming",
            "duration_minutes": 40,
        },
    )
    workout_id = create_response.get_json()["id"]

    response = client.get(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": workout_id,
        "activity": "Swimming",
        "duration_minutes": 40,
        "user_id": 1,
    }


def test_get_single_workout_requires_authentication(app):
    client = app.test_client()

    response = client.get("/workouts/1")

    assert response.status_code == 401


def test_user_cannot_get_another_users_workout(app):
    client = app.test_client()

    # Register the first user.
    response = client.post(
        "/signup",
        json={
            "username": "runner_one",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token1 = response.get_json()["token"]

    # Register the second user.
    response = client.post(
        "/signup",
        json={
            "username": "runner_two",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token2 = response.get_json()["token"]

    # The first user creates a workout.
    response = client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "activity": "Cycling",
            "duration_minutes": 25,
        },
    )
    workout_id = response.get_json()["id"]

    # The second user tries to retrieve the first user's workout.
    response = client.get(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "errors": ["Workout not found"]
    }

def test_update_workout_changes_only_provided_fields(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "patch_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token = response.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/workouts",
        headers=headers,
        json={"activity": "Running", "duration_minutes": 30},
    )
    workout_id = response.get_json()["id"]

    response = client.patch(
        f"/workouts/{workout_id}",
        headers=headers,
        json={"duration_minutes": 45},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "id": workout_id,
        "activity": "Running",
        "duration_minutes": 45,
        "user_id": 1,
    }


def test_update_workout_requires_authentication(app):
    client = app.test_client()

    response = client.patch(
        "/workouts/1",
        json={"activity": "Cycling"},
    )

    assert response.status_code == 401


def test_user_cannot_update_another_users_workout(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "owner_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    owner_token = response.get_json()["token"]

    response = client.post(
        "/signup",
        json={
            "username": "other_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    other_token = response.get_json()["token"]

    response = client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"activity": "Running", "duration_minutes": 30},
    )
    workout_id = response.get_json()["id"]

    response = client.patch(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"activity": "Cycling"},
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "errors": ["Workout not found"]
    }

    response = client.get(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["activity"] == "Running"


def test_update_workout_rejects_invalid_data(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "invalid_patch_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token = response.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/workouts",
        headers=headers,
        json={"activity": "Running", "duration_minutes": 30},
    )
    workout_id = response.get_json()["id"]

    response = client.patch(
        f"/workouts/{workout_id}",
        headers=headers,
        json={"duration_minutes": -5},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["duration_minutes must be a positive integer"]
    }

def test_delete_workout_requires_authentication(app):
    client = app.test_client()

    response = client.delete("/workouts/1")

    assert response.status_code == 401


def test_user_cannot_delete_another_users_workout(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "delete_owner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    owner_token = response.get_json()["token"]

    response = client.post(
        "/signup",
        json={
            "username": "delete_other",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    other_token = response.get_json()["token"]

    response = client.post(
        "/workouts",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"activity": "Running", "duration_minutes": 30},
    )
    workout_id = response.get_json()["id"]

    response = client.delete(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404

    # Confirm the owner's workout still exists.
    response = client.get(
        f"/workouts/{workout_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200


def test_owner_can_delete_workout(app):
    client = app.test_client()

    response = client.post(
        "/signup",
        json={
            "username": "delete_runner",
            "password": "testpassword",
            "password_confirmation": "testpassword",
        },
    )
    token = response.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/workouts",
        headers=headers,
        json={"activity": "Swimming", "duration_minutes": 40},
    )
    workout_id = response.get_json()["id"]

    response = client.delete(
        f"/workouts/{workout_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert response.data == b""

    # Confirm the deleted workout can no longer be retrieved.
    response = client.get(
        f"/workouts/{workout_id}",
        headers=headers,
    )
    assert response.status_code == 404
