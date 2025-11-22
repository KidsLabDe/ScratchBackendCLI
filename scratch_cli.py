#!/usr/bin/env python3
"""
Scratch CLI - Ein Kommandozeilen-Tool zum Zugriff auf Scratch-Projekte

Funktionen:
- Login mit Scratch-Account
- Projekte auflisten
- Projekte herunterladen (.sb3)
- Projekt-Metadaten anzeigen
"""

import argparse
import json
import os
import sys
import zipfile
import io
from pathlib import Path
from getpass import getpass

try:
    import requests
except ImportError:
    print("Fehler: 'requests' Bibliothek nicht gefunden.")
    print("Installiere mit: pip install requests")
    sys.exit(1)


class ScratchAPI:
    """Scratch API Client für Authentifizierung und Projektzugriff"""

    BASE_URL = "https://scratch.mit.edu"
    API_URL = "https://api.scratch.mit.edu"
    PROJECTS_URL = "https://projects.scratch.mit.edu"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ScratchCLI/1.0)",
            "Referer": "https://scratch.mit.edu",
        })
        self.username = None
        self.session_id = None
        self.token = None
        self.config_path = Path.home() / ".scratch_cli_config.json"

    def login(self, username: str, password: str) -> bool:
        """
        Authentifiziert den Benutzer bei Scratch.

        Args:
            username: Scratch Benutzername
            password: Scratch Passwort

        Returns:
            True bei erfolgreicher Anmeldung, False sonst
        """
        # CSRF Token holen
        self.session.get(f"{self.BASE_URL}/csrf_token/")
        csrf_token = self.session.cookies.get("scratchcsrftoken")

        if not csrf_token:
            print("Fehler: Konnte CSRF-Token nicht abrufen")
            return False

        # Login Request
        login_url = f"{self.BASE_URL}/accounts/login/"
        headers = {
            "X-CSRFToken": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

        data = {
            "username": username,
            "password": password,
            "useMessages": True,
        }

        response = self.session.post(
            login_url,
            headers=headers,
            json=data,
        )

        if response.status_code == 200:
            try:
                result = response.json()
                if result and len(result) > 0 and "username" in result[0]:
                    self.username = result[0]["username"]
                    self.session_id = self.session.cookies.get("scratchsessionsid")
                    self.token = result[0].get("token", "")

                    # Session speichern
                    self._save_session()

                    print(f"Erfolgreich angemeldet als: {self.username}")
                    return True
                else:
                    # Fehlermeldung von Scratch anzeigen
                    if result and len(result) > 0:
                        msg = result[0].get("msg", "Unbekannter Fehler")
                        print(f"Scratch Antwort: {msg}")
                    else:
                        print(f"Unerwartete Antwort: {result}")
            except json.JSONDecodeError:
                print(f"Konnte Antwort nicht parsen: {response.text[:200]}")
        else:
            print(f"HTTP Fehler: {response.status_code}")
            print(f"Antwort: {response.text[:200]}")

        print("Fehler: Anmeldung fehlgeschlagen. Bitte Benutzername und Passwort überprüfen.")
        return False

    def _save_session(self):
        """Speichert die Session-Daten für spätere Verwendung"""
        config = {
            "username": self.username,
            "session_id": self.session_id,
            "token": self.token,
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)
        os.chmod(self.config_path, 0o600)

    def load_session(self) -> bool:
        """
        Lädt eine gespeicherte Session.

        Returns:
            True wenn Session geladen wurde, False sonst
        """
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path) as f:
                config = json.load(f)

            self.username = config.get("username")
            self.session_id = config.get("session_id")
            self.token = config.get("token")

            if self.session_id:
                self.session.cookies.set("scratchsessionsid", self.session_id)

            # Session validieren
            if self._validate_session():
                return True
            else:
                self.logout()
                return False

        except (json.JSONDecodeError, KeyError):
            return False

    def _validate_session(self) -> bool:
        """Überprüft ob die aktuelle Session noch gültig ist"""
        if not self.username:
            return False

        response = self.session.get(f"{self.API_URL}/users/{self.username}")
        return response.status_code == 200

    def logout(self):
        """Löscht die gespeicherte Session"""
        if self.config_path.exists():
            self.config_path.unlink()
        self.username = None
        self.session_id = None
        self.token = None
        print("Erfolgreich abgemeldet.")

    def get_my_projects(self, limit: int = 40, offset: int = 0) -> list:
        """
        Ruft die Projekte des angemeldeten Benutzers ab (inkl. unveröffentlichte).

        Args:
            limit: Maximale Anzahl der Projekte
            offset: Offset für Pagination

        Returns:
            Liste der Projekte
        """
        if not self.username:
            print("Fehler: Nicht angemeldet.")
            return []

        # Zuerst versuchen, alle Projekte über die MyStuff-API zu holen
        # Diese zeigt auch unveröffentlichte Projekte
        url = f"{self.BASE_URL}/site-api/projects/all/"
        params = {"page": 1, "ascsort": "", "descsort": ""}

        response = self.session.get(url, params=params)

        if response.status_code == 200:
            try:
                return response.json()
            except:
                pass

        # Fallback: Normale API (nur veröffentlichte)
        url = f"{self.API_URL}/users/{self.username}/projects"
        params = {"limit": limit, "offset": offset}

        response = self.session.get(url, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fehler beim Abrufen der Projekte: {response.status_code}")
            return []

    def get_project_metadata(self, project_id: int) -> dict:
        """
        Ruft Metadaten für ein Projekt ab.

        Args:
            project_id: Die Projekt-ID

        Returns:
            Dictionary mit Projekt-Metadaten
        """
        url = f"{self.API_URL}/projects/{project_id}"

        # Für eigene unveröffentlichte Projekte: Token senden
        headers = {}
        if self.token:
            # CSRF Token holen
            self.session.get(f"{self.BASE_URL}/csrf_token/")
            csrf = self.session.cookies.get("scratchcsrftoken", "")
            headers = {
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "X-Token": self.token,
            }

        response = self.session.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fehler beim Abrufen der Metadaten: {response.status_code}")
            return {}

    def download_project(self, project_id: int, output_dir: str = ".", title: str = None) -> str:
        """
        Lädt ein Projekt als .sb3 Datei herunter.

        Args:
            project_id: Die Projekt-ID
            output_dir: Zielverzeichnis für den Download
            title: Optionaler Titel (für unveröffentlichte Projekte)

        Returns:
            Pfad zur heruntergeladenen Datei oder leerer String bei Fehler
        """
        # Zuerst Metadaten holen für den Dateinamen
        metadata = self.get_project_metadata(project_id)

        if metadata:
            title = metadata.get("title", f"project_{project_id}")
            project_token = metadata.get("project_token", "")
        else:
            # Für unveröffentlichte Projekte: versuche ohne Token
            if not title:
                title = f"project_{project_id}"
            project_token = ""

        # Ungültige Zeichen aus Dateinamen entfernen
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()

        # Projekt-JSON herunterladen
        url = f"{self.PROJECTS_URL}/{project_id}"
        if project_token:
            url += f"?token={project_token}"

        # Für eigene unveröffentlichte Projekte: Token im Header senden
        headers = {}
        if self.token and not project_token:
            headers["X-Token"] = self.token

        response = self.session.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Fehler beim Herunterladen: {response.status_code}")
            if response.status_code == 404:
                print("Projekt nicht gefunden oder nicht zugänglich.")
            elif response.status_code == 403:
                print("Zugriff verweigert. Das Projekt ist möglicherweise nicht freigegeben.")
            return ""

        # Als .json speichern (Scratch Projektformat)
        output_path = Path(output_dir) / f"{safe_title}_{project_id}.json"

        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"Projekt heruntergeladen: {output_path}")
        return str(output_path)

    def download_project_sb3(self, project_id: int, output_dir: str = ".") -> str:
        """
        Lädt ein vollständiges Projekt als .sb3 Datei herunter (ZIP-Format mit Assets).

        Args:
            project_id: Die Projekt-ID
            output_dir: Zielverzeichnis für den Download

        Returns:
            Pfad zur heruntergeladenen Datei oder leerer String bei Fehler
        """
        # Metadaten holen
        metadata = self.get_project_metadata(project_id)

        if metadata:
            title = metadata.get("title", f"project_{project_id}")
            project_token = metadata.get("project_token", "")
        else:
            title = f"project_{project_id}"
            project_token = ""

        # Ungültige Zeichen aus Dateinamen entfernen
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()

        # Projekt-JSON herunterladen
        url = f"{self.PROJECTS_URL}/{project_id}"
        if project_token:
            url += f"?token={project_token}"

        headers = {}
        if self.token and not project_token:
            headers["X-Token"] = self.token

        response = self.session.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Fehler beim Herunterladen: {response.status_code}")
            return ""

        try:
            project_json = response.json()
        except json.JSONDecodeError:
            print("Fehler: Ungültige Projektdaten")
            return ""

        # Assets sammeln (md5ext -> Dateiname)
        assets = set()

        # Kostüme und Sounds aus Targets extrahieren
        for target in project_json.get("targets", []):
            for costume in target.get("costumes", []):
                if "md5ext" in costume:
                    assets.add(costume["md5ext"])
                elif "assetId" in costume:
                    ext = costume.get("dataFormat", "svg")
                    assets.add(f"{costume['assetId']}.{ext}")

            for sound in target.get("sounds", []):
                if "md5ext" in sound:
                    assets.add(sound["md5ext"])
                elif "assetId" in sound:
                    ext = sound.get("dataFormat", "wav")
                    assets.add(f"{sound['assetId']}.{ext}")

        print(f"Lade {len(assets)} Assets herunter...")

        # ZIP-Datei erstellen
        output_path = Path(output_dir) / f"{safe_title}_{project_id}.sb3"

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # project.json hinzufügen
            zf.writestr("project.json", json.dumps(project_json))

            # Assets herunterladen und hinzufügen
            asset_url_base = "https://assets.scratch.mit.edu/internalapi/asset"

            for i, asset_name in enumerate(assets, 1):
                asset_url = f"{asset_url_base}/{asset_name}/get/"

                try:
                    asset_response = self.session.get(asset_url)
                    if asset_response.status_code == 200:
                        zf.writestr(asset_name, asset_response.content)
                    else:
                        print(f"  Warnung: Asset {asset_name} nicht gefunden ({asset_response.status_code})")
                except Exception as e:
                    print(f"  Fehler beim Laden von {asset_name}: {e}")

                # Fortschritt anzeigen
                if i % 10 == 0 or i == len(assets):
                    print(f"  {i}/{len(assets)} Assets geladen")

        print(f"Projekt heruntergeladen: {output_path}")
        return str(output_path)


def normalize_project(project: dict) -> dict:
    """Normalisiert Projektdaten aus verschiedenen API-Formaten"""
    # MyStuff API Format (fields/pk)
    if 'fields' in project:
        fields = project['fields']
        return {
            'id': project.get('pk'),
            'title': fields.get('title', 'Unbenannt'),
            'description': fields.get('description', ''),
            'stats': {
                'views': fields.get('view_count', 0),
                'loves': fields.get('love_count', 0),
                'favorites': fields.get('favorite_count', 0),
                'remixes': fields.get('remixers_count', 0),
            },
            'history': {
                'created': fields.get('datetime_created', 'N/A'),
                'modified': fields.get('datetime_modified', 'N/A'),
            },
            'public': fields.get('isPublished', False),
        }
    # Standard API Format
    return project


def format_project_info(project: dict) -> str:
    """Formatiert Projektinformationen für die Ausgabe"""
    # Normalisiere das Projekt-Format
    project = normalize_project(project)

    output = []
    output.append(f"  ID: {project.get('id', 'N/A')}")
    output.append(f"  Titel: {project.get('title', 'N/A')}")

    if project.get('description'):
        desc = project['description'][:100]
        if len(project['description']) > 100:
            desc += "..."
        output.append(f"  Beschreibung: {desc}")

    stats = project.get('stats', {})
    output.append(f"  Views: {stats.get('views', 0)}")
    output.append(f"  Loves: {stats.get('loves', 0)}")
    output.append(f"  Favorites: {stats.get('favorites', 0)}")
    output.append(f"  Remixes: {stats.get('remixes', 0)}")

    history = project.get('history', {})
    output.append(f"  Erstellt: {history.get('created', 'N/A')}")
    output.append(f"  Geändert: {history.get('modified', 'N/A')}")

    public = project.get('public', False)
    output.append(f"  Öffentlich: {'Ja' if public else 'Nein'}")

    return "\n".join(output)


def cmd_login(api: ScratchAPI, args):
    """Login-Befehl"""
    username = args.username or input("Benutzername: ")
    password = args.password or getpass("Passwort: ")

    if api.login(username, password):
        print("Session wurde gespeichert.")
    else:
        sys.exit(1)


def cmd_logout(api: ScratchAPI, args):
    """Logout-Befehl"""
    api.logout()


def cmd_list(api: ScratchAPI, args):
    """Projekte auflisten"""
    if not api.load_session():
        print("Fehler: Nicht angemeldet. Bitte zuerst 'login' ausführen.")
        sys.exit(1)

    print(f"\nProjekte von {api.username}:\n")

    projects = api.get_my_projects(limit=args.limit)

    if not projects:
        print("Keine Projekte gefunden.")
        return

    for i, project in enumerate(projects, 1):
        normalized = normalize_project(project)
        print(f"{i}. {normalized.get('title', 'Unbenannt')} (ID: {normalized.get('id')})")
        if args.verbose:
            print(format_project_info(project))
            print()


def cmd_info(api: ScratchAPI, args):
    """Projekt-Informationen anzeigen"""
    if not api.load_session():
        print("Fehler: Nicht angemeldet. Bitte zuerst 'login' ausführen.")
        sys.exit(1)

    metadata = api.get_project_metadata(args.project_id)

    if metadata:
        print(f"\nProjekt-Details:\n")
        print(format_project_info(metadata))
    else:
        sys.exit(1)


def cmd_download(api: ScratchAPI, args):
    """Projekt herunterladen"""
    if not api.load_session():
        print("Fehler: Nicht angemeldet. Bitte zuerst 'login' ausführen.")
        sys.exit(1)

    output_dir = args.output or "."
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Standard: .sb3 mit Assets, außer --json ist gesetzt
    use_sb3 = not args.json

    if args.all:
        # Alle Projekte herunterladen
        projects = api.get_my_projects(limit=100)
        print(f"Lade {len(projects)} Projekte herunter...")

        for project in projects:
            normalized = normalize_project(project)
            project_id = normalized.get('id')
            if project_id:
                if use_sb3:
                    api.download_project_sb3(project_id, output_dir)
                else:
                    api.download_project(project_id, output_dir)
    else:
        # Einzelnes Projekt herunterladen
        if not args.project_id:
            print("Fehler: Bitte Projekt-ID angeben oder --all verwenden.")
            sys.exit(1)

        if use_sb3:
            result = api.download_project_sb3(args.project_id, output_dir)
        else:
            result = api.download_project(args.project_id, output_dir)

        if not result:
            sys.exit(1)


def cmd_status(api: ScratchAPI, args):
    """Zeigt den aktuellen Login-Status"""
    if api.load_session():
        print(f"Angemeldet als: {api.username}")
    else:
        print("Nicht angemeldet.")


def main():
    parser = argparse.ArgumentParser(
        description="Scratch CLI - Zugriff auf deine Scratch-Projekte",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s login                     # Anmelden
  %(prog)s list                      # Projekte auflisten
  %(prog)s list -v                   # Projekte mit Details auflisten
  %(prog)s info 123456789            # Projekt-Metadaten anzeigen
  %(prog)s download 123456789        # Projekt als .sb3 herunterladen (mit Assets)
  %(prog)s download 123456789 --json # Nur project.json herunterladen
  %(prog)s download --all            # Alle Projekte als .sb3 herunterladen
  %(prog)s logout                    # Abmelden
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # Login
    login_parser = subparsers.add_parser("login", help="Bei Scratch anmelden")
    login_parser.add_argument("-u", "--username", help="Benutzername")
    login_parser.add_argument("-p", "--password", help="Passwort (unsicher, besser interaktiv eingeben)")

    # Logout
    subparsers.add_parser("logout", help="Abmelden und Session löschen")

    # Status
    subparsers.add_parser("status", help="Login-Status anzeigen")

    # List
    list_parser = subparsers.add_parser("list", help="Projekte auflisten")
    list_parser.add_argument("-v", "--verbose", action="store_true",
                             help="Ausführliche Informationen anzeigen")
    list_parser.add_argument("-l", "--limit", type=int, default=40,
                             help="Maximale Anzahl (Standard: 40)")

    # Info
    info_parser = subparsers.add_parser("info", help="Projekt-Details anzeigen")
    info_parser.add_argument("project_id", type=int, help="Projekt-ID")

    # Download
    download_parser = subparsers.add_parser("download", help="Projekt herunterladen")
    download_parser.add_argument("project_id", type=int, nargs="?",
                                 help="Projekt-ID")
    download_parser.add_argument("-o", "--output", help="Ausgabeverzeichnis")
    download_parser.add_argument("-a", "--all", action="store_true",
                                 help="Alle Projekte herunterladen")
    download_parser.add_argument("--sb3", action="store_true",
                                 help="Als .sb3 mit Assets herunterladen (Standard: nur JSON)")
    download_parser.add_argument("--json", action="store_true",
                                 help="Nur project.json herunterladen (ohne Assets)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    api = ScratchAPI()

    commands = {
        "login": cmd_login,
        "logout": cmd_logout,
        "status": cmd_status,
        "list": cmd_list,
        "info": cmd_info,
        "download": cmd_download,
    }

    if args.command in commands:
        commands[args.command](api, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
