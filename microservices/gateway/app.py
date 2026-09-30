"""API gateway: single public entry point. Serves the website and forwards
API calls to the right microservice. The frontend does not need to change."""
import os
import requests
from flask import Flask, request, Response, jsonify

app = Flask(__name__, static_folder="static")

SERVICES = {
    "auth": os.environ.get("AUTH_URL", "http://localhost:5001"),
    "destinations": os.environ.get("DESTINATIONS_URL", "http://localhost:5002"),
    "itineraries": os.environ.get("ITINERARIES_URL", "http://localhost:5003"),
    "chat": os.environ.get("CHAT_URL", "http://localhost:5004"),
}
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 5))
HEALTH_TIMEOUT = int(os.environ.get("HEALTH_TIMEOUT", 2))


def forward(service, path):
    url = f"{SERVICES[service]}{path}"
    headers = {k: v for k, v in request.headers if k.lower() in ("authorization", "content-type")}
    try:
        resp = requests.request(request.method, url, params=request.args, data=request.get_data(),
                                headers=headers, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        return jsonify({"error": f"{service} service timed out"}), 504
    except requests.exceptions.RequestException:
        return jsonify({"error": f"{service} service unavailable"}), 503
    return Response(resp.content, status=resp.status_code,
                    content_type=resp.headers.get("Content-Type", "application/json"))


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/config")
def config():
    """Tell the browser where the chat service lives (own URL on the cloud, port 5004 locally)."""
    chat_url = os.environ.get("CHAT_PUBLIC_URL") or f"{request.scheme}://{request.host.split(':')[0]}:5004"
    return jsonify({"chat_url": chat_url}), 200


@app.route("/chat")
def chat_page():
    return app.send_static_file("chat.html")


@app.route("/register", methods=["POST"])
def register():
    return forward("auth", "/register")


@app.route("/login", methods=["POST"])
def login():
    return forward("auth", "/login")


@app.route("/destinations", methods=["GET"])
def destinations():
    return forward("destinations", "/destinations")


@app.route("/recommendations", methods=["GET"])
def recommendations():
    return forward("destinations", "/recommendations")


@app.route("/itineraries", methods=["GET", "POST"])
def itineraries():
    return forward("itineraries", "/itineraries")


@app.route("/itineraries/<itinerary_id>", methods=["DELETE"])
def itinerary_one(itinerary_id):
    return forward("itineraries", f"/itineraries/{itinerary_id}")


@app.route("/health")
def health():
    report = {}
    for name, base in SERVICES.items():
        try:
            ok = requests.get(f"{base}/health", timeout=HEALTH_TIMEOUT).status_code == 200
        except requests.exceptions.RequestException:
            ok = False
        report[name] = "up" if ok else "down"
    overall = "ok" if all(v == "up" for v in report.values()) else "degraded"
    return jsonify({"gateway": "up", "status": overall, "services": report}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
