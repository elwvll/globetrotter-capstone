"""Auth service: registration, login, JWT issuing. Owns users.json."""
import os, json, uuid, datetime
import jwt
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
SECRET = os.environ.get("SECRET_KEY", "globetrotter-secret-change-in-prod")
INTERNAL_KEY = os.environ.get("INTERNAL_KEY", "internal-dev-key")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def read_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as fh:
        content = fh.read().strip()
        return json.loads(content) if content else []


def write_users(users):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as fh:
        json.dump(users, fh, indent=2)


def find_user(username):
    return next((u for u in read_users() if u.get("username") == username), None)


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    preferences = data.get("preferences", [])
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if find_user(username):
        return jsonify({"error": "username already exists"}), 409
    users = read_users()
    users.append({
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": generate_password_hash(password),
        "preferences": preferences,
    })
    write_users(users)
    return jsonify({"message": "user registered successfully", "username": username}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = find_user(username)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    now = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode({"sub": username, "iat": now, "exp": now + datetime.timedelta(hours=24)},
                       SECRET, algorithm="HS256")
    return jsonify({"token": token}), 200


@app.route("/internal/users/<username>", methods=["GET"])
def internal_user(username):
    """Service-to-service only: never exposed by the gateway."""
    if request.headers.get("X-Internal-Key") != INTERNAL_KEY:
        return jsonify({"error": "forbidden"}), 403
    user = find_user(username)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify({"username": user["username"], "preferences": user.get("preferences", [])}), 200


@app.route("/health")
def health():
    return jsonify({"service": "auth", "status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
