from flask import Flask, jsonify, request
from flask_jwt_extended import (create_access_token, jwt_required, get_jwt_identity)

from server import bcrypt, db, jwt, migrate, models
from server.config import Config
from server.models import User


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    @app.route("/")
    def index():
        return jsonify({"message": "Workout Tracker API is running"})


    @app.route("/signup", methods=["POST"])
    def signup():
        data = request.get_json()

        if not data:
            return jsonify({"errors": ["Request body must be JSON"]}), 400

        username = data.get("username")
        password = data.get("password")
        password_confirmation = data.get("password_confirmation")

        if not username or not password or not password_confirmation:
            return jsonify({"errors": ["All fields are required"]}), 400

        if password != password_confirmation:
            return jsonify({"errors": ["Passwords do not match"]}), 400
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return jsonify({"errors": ["Username already exists"]}), 409

        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

        new_user = User(
            username=username,
            password_hash=password_hash
        )

        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=str(new_user.id))

        return jsonify({
            "token": access_token,
            "user": {
                "id": new_user.id,
                "username": new_user.username
            }
        }), 201

    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json()

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"errors": ["Username and password are required"]}), 400
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"errors": ["Invalid username or password"]}), 401
        if not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({"errors": ["Invalid username or password"]}), 401
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
        "token": access_token,
        "user": {
            "id": user.id,
            "username": user.username
        }
    }), 200
    @app.route("/me", methods=["GET"])
    @jwt_required()
    def me():
        user_id = get_jwt_identity()
        user = db.session.get(User, int(user_id))

        if user is None:
            return jsonify({"errors": ["User not found"]}), 404

        return jsonify({
            "id": user.id,
            "username": user.username
        }), 200
    
    return app
if __name__ == "__main__":
    app = create_app()
    app.run(port=5555, debug=True)