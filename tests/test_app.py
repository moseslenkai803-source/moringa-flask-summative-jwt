
import pytest

from server import bcrypt, db
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
