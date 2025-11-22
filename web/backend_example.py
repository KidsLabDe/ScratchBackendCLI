#!/usr/bin/env python3
"""
Beispiel Backend-Server für Scratch Auth

Dieser Server empfängt nur den Session-Token vom Browser,
NIE das Passwort des Nutzers.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests as http_requests
import json
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Für Cross-Origin Requests vom Frontend

# Verzeichnis für Session-Speicherung
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)


@app.route('/api/scratch-auth', methods=['POST'])
def login_proxy():
    """
    Proxy für Scratch-Login.

    Das Passwort wird an Scratch weitergeleitet, aber NIE gespeichert!
    Nur der Session-Token wird gespeichert.

    Erwartet JSON:
    {
        "username": "ScratchUser",
        "password": "..."
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Keine Daten empfangen"}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username oder Passwort fehlt"}), 400

    # Session für Scratch-Requests
    session = http_requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://scratch.mit.edu/",
        "Origin": "https://scratch.mit.edu",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })

    # 1. CSRF Token holen
    session.get("https://scratch.mit.edu/csrf_token/")
    csrf_token = session.cookies.get("scratchcsrftoken")

    if not csrf_token:
        return jsonify({"error": "Konnte CSRF-Token nicht abrufen"}), 500

    # 2. Login bei Scratch
    login_response = session.post(
        "https://scratch.mit.edu/accounts/login/",
        headers={
            "X-CSRFToken": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
        },
        json={
            "username": username,
            "password": password,  # Wird NUR an Scratch gesendet, nie gespeichert!
            "useMessages": True,
        }
    )

    # Passwort sofort vergessen (wird nicht mehr benötigt)
    password = None

    if login_response.status_code != 200:
        return jsonify({"error": f"Scratch-Login fehlgeschlagen: {login_response.status_code}"}), 401

    try:
        result = login_response.json()
        if not result or len(result) == 0 or "username" not in result[0]:
            msg = result[0].get("msg", "Unbekannter Fehler") if result and len(result) > 0 else "Login fehlgeschlagen"
            return jsonify({"error": msg}), 401
    except:
        return jsonify({"error": "Ungültige Antwort von Scratch"}), 500

    # 3. Session-Daten extrahieren (NICHT das Passwort!)
    scratch_username = result[0]["username"]
    token = result[0].get("token", "")
    session_id = session.cookies.get("scratchsessionsid", "")

    # 4. Nur Session speichern (in Produktion: Datenbank verwenden!)
    session_file = SESSIONS_DIR / f"{scratch_username}.json"

    session_data = {
        "username": scratch_username,
        "token": token,
        "session_id": session_id
    }

    with open(session_file, 'w') as f:
        json.dump(session_data, f)

    # Berechtigungen setzen (nur Server lesbar)
    os.chmod(session_file, 0o600)

    print(f"Session gespeichert für: {scratch_username}")

    return jsonify({
        "success": True,
        "message": f"Erfolgreich angemeldet als {scratch_username}",
        "username": scratch_username
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
