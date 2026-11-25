"""Flask backend server for AeroRelief Interactive Web Application."""

import os
from flask import Flask, jsonify, request, send_from_directory, abort
from aerorelief.scenarios import list_scenarios
from aerorelief.solver import solve_mission

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
MEDIA_DIR = os.path.join(ROOT_DIR, "media")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")


@app.after_request
def add_no_cache_headers(response):
    if request.path == "/" or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "engine": "Python AeroRelief AI (Dynamic Re-plan)"})


@app.get("/api/scenarios")
def get_scenarios():
    return jsonify({"scenarios": list_scenarios()})


@app.post("/api/solve")
def api_solve():
    payload = request.get_json(silent=True) or {}
    try:
        result = solve_mission(payload)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"reachable": False, "error": True, "message": str(exc)}), 400


@app.post("/api/replan")
def api_replan():
    """Mid-flight adaptive obstacle injection & dynamic re-planning endpoint."""
    payload = dict(request.get_json(silent=True) or {})
    injected = list(payload.get("injected_events") or [])
    new_ev = payload.pop("new_event", None)
    if new_ev:
        injected.append(new_ev)
    payload["injected_events"] = injected
    try:
        result = solve_mission(payload)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"reachable": False, "error": True, "message": str(exc)}), 400


@app.get("/media/<path:filename>")
def serve_media(filename: str):
    media_candidate = os.path.join(MEDIA_DIR, filename)
    if os.path.isfile(media_candidate):
        return send_from_directory(MEDIA_DIR, filename)
    root_allowed = {"AeroRelief_Progress_KKA.pptx", "mockup_simulation.png"}
    if filename in root_allowed and os.path.isfile(os.path.join(ROOT_DIR, filename)):
        return send_from_directory(ROOT_DIR, filename)
    abort(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    print(f"AeroRelief Web Server running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
