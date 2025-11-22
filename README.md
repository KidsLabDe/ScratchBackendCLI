# Scratch CLI

Ein Kommandozeilen-Tool zum Zugriff auf deine Scratch-Projekte.

## Features

- Login mit Scratch-Account (Session wird gespeichert)
- Projekte auflisten (inkl. unveröffentlichte)
- Projekt-Metadaten anzeigen
- Projekte als .sb3 herunterladen (mit allen Assets)

## Installation

```bash
pip install requests
```

## Verwendung

### Anmelden

```bash
python scratch_cli.py login
python scratch_cli.py login -u dein_benutzername
```

### Status prüfen

```bash
python scratch_cli.py status
```

### Projekte auflisten

```bash
python scratch_cli.py list              # Einfache Liste
python scratch_cli.py list -v           # Mit Details (Views, Likes, etc.)
python scratch_cli.py list -l 100       # Bis zu 100 Projekte anzeigen
```

### Projekt-Informationen

```bash
python scratch_cli.py info 123456789
```

### Projekte herunterladen

```bash
# Als .sb3 mit allen Assets (Standard)
python scratch_cli.py download 123456789

# In bestimmtes Verzeichnis
python scratch_cli.py download 123456789 -o ./meine_projekte

# Nur project.json (ohne Assets)
python scratch_cli.py download 123456789 --json

# Alle eigenen Projekte herunterladen
python scratch_cli.py download --all
python scratch_cli.py download --all -o ./backup
```

### Abmelden

```bash
python scratch_cli.py logout
```

## Session-Speicherung

Nach dem Login wird die Session in `~/.scratch_cli_config.json` gespeichert (nur für dich lesbar). Das Passwort wird nicht gespeichert.

## Beispiel-Workflow

```bash
# 1. Anmelden
python scratch_cli.py login -u MeinScratchName

# 2. Projekte anzeigen
python scratch_cli.py list -v

# 3. Projekt herunterladen
python scratch_cli.py download 123456789 -o ./downloads

# 4. Abmelden (optional)
python scratch_cli.py logout
```
