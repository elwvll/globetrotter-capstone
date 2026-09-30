"""Itinerary service: create, list and delete trips. Owns itineraries.json."""
import os, json, uuid, datetime
import jwt
from flask import Flask, request, jsonify

app = Flask(__name__)
SECRET = os.environ.get("SECRET_KEY", "globetrotter-secret-change-in-prod")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
FILE = os.path.join(DATA_DIR, "itineraries.json")


def read_all():
    if not os.path.exists(FILE):
        return []
    with open(FILE, "r", encoding="utf-8") as fh:
        content = fh.read().strip()
        return json.loads(content) if content else []


def write_all(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2)


def current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        return jwt.decode(header.split(" ", 1)[1], SECRET, algorithms=["HS256"]).get("sub")
    except jwt.PyJWTError:
        return None


@app.route("/itineraries", methods=["POST"])
def create():
    username = current_user()
    if not username:
        return jsonify({"error": "authentication required"}), 401
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    destinations = data.get("destinations", [])
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not isinstance(destinations, list):
        return jsonify({"error": "destinations must be a list"}), 400
    item = {
        "id": str(uuid.uuid4()),
        "username": username,
        "title": title,
        "destinations": destinations,
        "start_date": data.get("start_date", ""),
        "end_date": data.get("end_date", ""),
        "notes": data.get("notes", ""),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    items = read_all()
    items.append(item)
    write_all(items)
    return jsonify(item), 201


@app.route("/itineraries", methods=["GET"])
def list_mine():
    username = current_user()
    if not username:
        return jsonify({"error": "authentication required"}), 401
    return jsonify([i for i in read_all() if i.get("username") == username]), 200


@app.route("/itineraries/<itinerary_id>", methods=["DELETE"])
def delete(itinerary_id):
    username = current_user()
    if not username:
        return jsonify({"error": "authentication required"}), 401
    items = read_all()
    for it in items:
        if it.get("id") == itinerary_id:
            if it.get("username") != username:
                return jsonify({"error": "you can only delete your own itineraries"}), 403
            items.remove(it)
            write_all(items)
            return jsonify({"message": "itinerary deleted"}), 200
    return jsonify({"error": "itinerary not found"}), 404


@app.route("/health")
def health():
    return jsonify({"service": "itineraries", "status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5003)))
