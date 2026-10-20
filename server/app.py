from flask import Flask, jsonify, request
from flask_jwt_extended import (create_access_token, jwt_required, get_jwt_identity)

from server import bcrypt, db, jwt, migrate, models
from server.config import Config
from server.models import User, Workout


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

    @app.route("/workouts", methods=["POST"])
    @jwt_required()
    def create_workout():
        data = request.get_json()

        if not data:
            return jsonify({"errors": ["Request body must be JSON"]}), 400

        activity = data.get("activity")
        duration = data.get("duration_minutes")

        if not activity or duration is None:
            return jsonify({
                "errors": ["Activity and duration_minutes are required"]
            }), 400

        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            return jsonify({
                "errors": ["duration_minutes must be a positive integer"]
            }), 400

        user_id = int(get_jwt_identity())

        workout = Workout(
            activity=activity,
            duration_minutes=duration,
            user_id=user_id
        )

        db.session.add(workout)
        db.session.commit()

        return jsonify({
            "id": workout.id,
            "activity": workout.activity,
            "duration_minutes": workout.duration_minutes,
            "user_id": workout.user_id
        }), 201

    @app.route("/workouts", methods=["GET"])
    @jwt_required()
    def get_workouts():
        user_id = int(get_jwt_identity())

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        if page < 1 or per_page < 1:
            return jsonify({
                "errors": ["page and per_page must be positive integers"]
            }), 400

        per_page = min(per_page, 100)

        pagination = Workout.query.filter_by(
            user_id=user_id
        ).order_by(Workout.id).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        workouts = [
            {
                "id": workout.id,
                "activity": workout.activity,
                "duration_minutes": workout.duration_minutes,
                "user_id": workout.user_id,
            }
            for workout in pagination.items
        ]

        return jsonify({
            "workouts": workouts,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        }), 200

    @app.route("/workouts/<int:workout_id>", methods=["GET"])
    @jwt_required()
    def get_workout(workout_id):
        user_id = int(get_jwt_identity())

        workout = Workout.query.filter_by(
            id=workout_id,
            user_id=user_id
        ).first()

        if workout is None:
            return jsonify({"errors": ["Workout not found"]}), 404

        return jsonify({
            "id": workout.id,
            "activity": workout.activity,
            "duration_minutes": workout.duration_minutes,
            "user_id": workout.user_id
        }), 200

    @app.route("/workouts/<int:workout_id>", methods=["PATCH"])
    @jwt_required()
    def update_workout(workout_id):
        user_id = int(get_jwt_identity())

        workout = Workout.query.filter_by(
            id=workout_id,
            user_id=user_id
        ).first()

        if workout is None:
            return jsonify({"errors": ["Workout not found"]}), 404

        data = request.get_json()

        if not isinstance(data, dict) or not data:
            return jsonify({
                "errors": ["Provide a non-empty JSON object"]
            }), 400

        allowed_fields = {"activity", "duration_minutes"}

        if not set(data.keys()).issubset(allowed_fields):
            return jsonify({
                "errors": ["Only activity and duration_minutes can be updated"]
            }), 400

        if "activity" in data:
            activity = data["activity"]

            if not isinstance(activity, str) or not activity.strip():
                return jsonify({
                    "errors": ["activity must be a non-empty string"]
                }), 400

            workout.activity = activity.strip()

        if "duration_minutes" in data:
            duration = data["duration_minutes"]

            if (
                not isinstance(duration, int)
                or isinstance(duration, bool)
                or duration <= 0
            ):
                return jsonify({
                    "errors": ["duration_minutes must be a positive integer"]
                }), 400

            workout.duration_minutes = duration

        db.session.commit()

        return jsonify({
            "id": workout.id,
            "activity": workout.activity,
            "duration_minutes": workout.duration_minutes,
            "user_id": workout.user_id
        }), 200


    @app.route("/workouts/<int:workout_id>", methods=["DELETE"])
    @jwt_required()
    def delete_workout(workout_id):
        user_id = int(get_jwt_identity())

        workout = Workout.query.filter_by(
            id=workout_id,
            user_id=user_id
        ).first()

        if workout is None:
            return jsonify({"errors": ["Workout not found"]}), 404

        db.session.delete(workout)
        db.session.commit()

        return "", 204


    
    return app
if __name__ == "__main__":
    app = create_app()
    app.run(port=5555, debug=True)