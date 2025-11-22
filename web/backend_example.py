#!/usr/bin/env python3
"""
Beispiel Backend-Server für Scratch Auth

Dieser Server empfängt nur den Session-Token vom Browser,
NIE das Passwort des Nutzers.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Für Cross-Origin Requests vom Frontend

# Verzeichnis für Session-Speicherung
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)


@app.route('/api/scratch-auth', methods=['POST'])
def receive_session():
    """
    Empfängt Session-Token vom Browser.

    Erwartet JSON:
    {
        "username": "ScratchUser",
        "token": "...",
        "sessionId": "..."
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Keine Daten empfangen"}), 400

    username = data.get('username')
    token = data.get('token')
    session_id = data.get('sessionId')

    if not username:
        return jsonify({"error": "Username fehlt"}), 400

    if not session_id and not token:
        return jsonify({"error": "Session-Daten fehlen"}), 400

    # Session speichern (in Produktion: Datenbank verwenden!)
    session_file = SESSIONS_DIR / f"{username}.json"

    session_data = {
        "username": username,
        "token": token,
        "session_id": session_id
    }

    with open(session_file, 'w') as f:
        json.dump(session_data, f)

    # Berechtigungen setzen (nur Server lesbar)
    os.chmod(session_file, 0o600)

    print(f"Session gespeichert für: {username}")

    return jsonify({
        "success": True,
        "message": f"Session für {username} gespeichert",
        "username": username
    })


@app.route('/api/scratch-auth/status/<username>', methods=['GET'])
def check_session(username):
    """Prüft ob eine Session für einen User existiert"""
    session_file = SESSIONS_DIR / f"{username}.json"

    if session_file.exists():
        return jsonify({
            "logged_in": True,
            "username": username
        })
    else:
        return jsonify({
            "logged_in": False
        })


@app.route('/api/scratch-auth/logout/<username>', methods=['POST'])
def logout(username):
    """Löscht die Session eines Users"""
    session_file = SESSIONS_DIR / f"{username}.json"

    if session_file.exists():
        session_file.unlink()
        return jsonify({
            "success": True,
            "message": f"Session für {username} gelöscht"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Keine Session gefunden"
        }), 404


if __name__ == '__main__':
    print("Scratch Auth Backend Server")
    print("Empfängt nur Session-Tokens, NIE Passwörter!")
    print("-" * 40)
    app.run(debug=True, port=5000)
