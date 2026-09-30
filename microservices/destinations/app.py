"""Destination service: catalogue search + recommendations.
Recommendations call the auth service over HTTP to get the user's interests."""
import os, json
import jwt
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
SECRET = os.environ.get("SECRET_KEY", "globetrotter-secret-change-in-prod")
INTERNAL_KEY = os.environ.get("INTERNAL_KEY", "internal-dev-key")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:5001")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DEST_FILE = os.path.join(DATA_DIR, "destinations.json")


def all_destinations():
    if not os.path.exists(DEST_FILE):
        return []
    with open(DEST_FILE, "r", encoding="utf-8") as fh:
        content = fh.read().strip()
        return json.loads(content) if content else []


def current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        return jwt.decode(header.split(" ", 1)[1], SECRET, algorithms=["HS256"]).get("sub")
    except jwt.PyJWTError:
        return None


@app.route("/destinations", methods=["GET"])
def search_destinations():
    q = request.args.get("q", "").strip().lower()
    tag = request.args.get("tag", "").strip().lower()
    continent = request.args.get("continent", "").strip().lower()
    max_cost_str = request.args.get("max_cost", "").strip()
    max_cost = None
    if max_cost_str:
        try:
            max_cost = int(max_cost_str)
        except ValueError:
            return jsonify({"error": "max_cost must be an integer"}), 400
    results = []
    for d in all_destinations():
        if q and q not in " ".join([d.get("name", ""), d.get("country", ""), d.get("description", "")]).lower():
            continue
        if tag and tag not in [t.lower() for t in d.get("tags", [])]:
            continue
        if continent and continent != d.get("continent", "").lower():
            continue
        if max_cost is not None:
            cost = d.get("avg_cost_per_day")
            if cost is None or cost > max_cost:
                continue
        results.append(d)
    return jsonify(results), 200


@app.route("/recommendations", methods=["GET"])
def recommendations():
    username = current_user()
    if not username:
        return jsonify({"error": "authentication required"}), 401
    try:
        limit = int(request.args.get("limit", 5))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    # Inter-service communication: ask the auth service for this user's interests
    try:
        resp = requests.get(f"{AUTH_URL}/internal/users/{username}",
                            headers={"X-Internal-Key": INTERNAL_KEY}, timeout=3)
    except requests.exceptions.RequestException:
        return jsonify({"error": "auth service unavailable, try again later"}), 503
    if resp.status_code == 404:
        return jsonify({"error": "user not found"}), 404
    if resp.status_code != 200:
        return jsonify({"error": "could not load user preferences"}), 502

    prefs = [p.lower() for p in resp.json().get("preferences", [])]
    scored = []
    for d in all_destinations():
        tags = [t.lower() for t in d.get("tags", [])]
        scored.append((sum(1 for p in prefs if p in tags), d))
    scored.sort(key=lambda x: (-x[0], x[1].get("name", "")))
    out = []
    for score, d in scored[:limit]:
        entry = dict(d)
        entry["match_score"] = score
        out.append(entry)
    return jsonify(out), 200


@app.route("/health")
def health():
    return jsonify({"service": "destinations", "status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))
