"""Chat service: real-time chat rooms over WebSockets (Flask-SocketIO).
Users connect with their JWT (issued by the auth service). Messages are kept
in memory (last 50 per room): fine for Phase 2, replaced by a real broker later."""
import os, time
from collections import deque

import jwt
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
SECRET = os.environ.get("SECRET_KEY", "globetrotter-secret-change-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ROOMS = [
    {"id": "general", "label": "General"},
    {"id": "douala", "label": "Douala"},
    {"id": "yaounde", "label": "Yaoundé"},
    {"id": "kribi", "label": "Kribi and the coast"},
    {"id": "buea", "label": "Buea and Mount Cameroon"},
    {"id": "west", "label": "West region"},
    {"id": "north", "label": "North and Far North"},
]
ROOM_IDS = {r["id"] for r in ROOMS}
HISTORY = {r["id"]: deque(maxlen=50) for r in ROOMS}
MEMBERS = {r["id"]: {} for r in ROOMS}      # room -> {sid: username}
SID_USER = {}                               # sid -> username
RECENT = {}                                 # sid -> timestamps (simple rate limit)


def now():
    return int(time.time() * 1000)


def system_msg(room, text):
    msg = {"room": room, "user": "system", "text": text, "ts": now(), "system": True}
    HISTORY[room].append(msg)
    return msg


def send_presence(room):
    emit("presence", {"room": room, "users": sorted(set(MEMBERS[room].values()))}, to=room)


@socketio.on("connect")
def on_connect(auth):
    token = (auth or {}).get("token", "")
    try:
        username = jwt.decode(token, SECRET, algorithms=["HS256"]).get("sub")
    except jwt.PyJWTError:
        return False            # refuse the connection
    if not username:
        return False
    SID_USER[request.sid] = username
    emit("rooms", ROOMS)


@socketio.on("join")
def on_join(data):
    room = (data or {}).get("room")
    user = SID_USER.get(request.sid)
    if room not in ROOM_IDS or not user:
        return
    if request.sid not in MEMBERS[room]:
        join_room(room)
        MEMBERS[room][request.sid] = user
        emit("message", system_msg(room, f"{user} joined"), to=room)
    emit("history", {"room": room, "messages": list(HISTORY[room])})
    send_presence(room)


@socketio.on("leave")
def on_leave(data):
    room = (data or {}).get("room")
    user = SID_USER.get(request.sid)
    if room in ROOM_IDS and request.sid in MEMBERS[room]:
        leave_room(room)
        MEMBERS[room].pop(request.sid, None)
        emit("message", system_msg(room, f"{user} left"), to=room)
        send_presence(room)


@socketio.on("message")
def on_message(data):
    room = (data or {}).get("room")
    text = str((data or {}).get("text", "")).strip()[:500]
    user = SID_USER.get(request.sid)
    if not user or room not in ROOM_IDS or request.sid not in MEMBERS[room] or not text:
        return
    stamps = [t for t in RECENT.get(request.sid, []) if time.time() - t < 5]
    if len(stamps) >= 5:
        emit("error_msg", {"error": "You are sending messages too fast."})
        return
    stamps.append(time.time())
    RECENT[request.sid] = stamps
    msg = {"room": room, "user": user, "text": text, "ts": now()}
    HISTORY[room].append(msg)
    emit("message", msg, to=room)


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    user = SID_USER.pop(sid, None)
    RECENT.pop(sid, None)
    for room, members in MEMBERS.items():
        if sid in members:
            members.pop(sid)
            emit("message", system_msg(room, f"{user} left"), to=room)
            send_presence(room)


@app.route("/health")
def health():
    return jsonify({"service": "chat", "status": "ok"}), 200


@app.route("/rooms")
def rooms():
    return jsonify(ROOMS), 200


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5004)), allow_unsafe_werkzeug=True)
