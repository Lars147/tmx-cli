<p align="center">
  <img src="logo.jpg" alt="tmx-cli logo" width="400">
</p>

<h1 align="center">tmx-cli</h1>

<p align="center">
  <strong>🍳 Dein Thermomix®/Cookidoo® im Terminal — Wochenplan, Rezepte, Einkaufslisten</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen.svg" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/recipes-24000+-orange.svg" alt="24k+ Recipes">
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-demo">Demo</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage">Usage</a>
</p>

---

## Was ist das?

**tmx-cli** bringt Cookidoo® ins Terminal. Kein Browser-Gefummel mehr — verwalte deinen Wochenplan, durchsuche 24.000+ Rezepte und erstelle Einkaufslisten direkt von der Kommandozeile.

**Warum ist das cool?**
- ⚡ **Schneller** — Keine lahmen Web-Apps, alles instant
- 🔧 **Hackbar** — Pipe Rezepte in andere Tools, automatisiere deine Meal-Prep
- 📦 **Zero Dependencies** — Pure Python, funktioniert überall
- 🖥️ **Terminal-Native** — Perfekt für Power-User und Entwickler

---

## 🚀 Quick Start

```bash
# Mit uvx (empfohlen) — läuft sofort ohne Installation
uvx --from git+https://github.com/Lars147/tmx-cli tmx login

# Einloggen, dann loslegen!
uvx --from git+https://github.com/Lars147/tmx-cli tmx search "Pasta"
```

---

## ✨ Features

| Feature | Beschreibung |
|---------|-------------|
| 🔐 **Login** | Sichere OAuth-Authentifizierung mit deinem Cookidoo-Account |
| 📅 **Wochenplan** | Anzeigen, synchronisieren, Rezepte hinzufügen/verschieben |
| 🔍 **Suche** | 24.000+ Rezepte durchsuchen mit Filtern (Zeit, Schwierigkeit, Kategorie) |
| ❤️ **Favoriten** | Deine Lieblingsrezepte verwalten |
| 📖 **Rezeptdetails** | Zutaten, Schritte, Nährwerte — alles im Terminal |
| 🛒 **Einkaufsliste** | Automatisch generieren, exportieren (Markdown/JSON) |
| ⚡ **Shell Completion** | Tab-Completion für Bash, Zsh, Fish |
| 📦 **Zero Deps** | Nur Python Standard Library, keine Abhängigkeiten |

---

## 🎬 Demo

### Wochenplan anzeigen

```
$ tmx plan show

╔══════════════════════════════════════════════════════════╗
║  🍳 COOKIDOO WOCHENPLAN                                  ║
╠══════════════════════════════════════════════════════════╣
║  Stand: 2026-02-03 19:39 UTC                             ║
║  Ab: 2026-02-08                                          ║
╚══════════════════════════════════════════════════════════╝

  Sonntag 8.  (2026-02-08)
    • Auberginen-Pasta  [r292049]
    • Cremekartoffeln mit Spinat  [r45808]

  Montag 9.  (2026-02-09)
    (keine Rezepte)
```

### Rezepte suchen

```
$ tmx search "Pasta" -n 3

🔍 Suche in Cookidoo: 'Pasta'
──────────────────────────────────────────────────
Gefunden: 24044 Rezepte (zeige 3)

   1. Tomaten-Knoblauch-Pasta
      ⏱ 30 Min  ⭐ 4.1
      https://cookidoo.de/recipes/recipe/de-DE/r130616

   2. Garnelen-Pasta mit Pesto-Sauce
      ⏱ 25 Min  ⭐ 4.8
      https://cookidoo.de/recipes/recipe/de-DE/r792997

   3. Curry-Nudeln mit gebratenem Schweinefilet
      ⏱ 45 Min  ⭐ 4.6
      https://cookidoo.de/recipes/recipe/de-DE/r447830
```

### Rezeptdetails abrufen

```
$ tmx recipe r130616

╔══════════════════════════════════════════════════════════╗
║  Tomaten-Knoblauch-Pasta                                 ║
╠══════════════════════════════════════════════════════════╣
║  📊 Einfach  │  ⏱ 30 Min  │  🍽 3 Portionen               ║
╚══════════════════════════════════════════════════════════╝

🔗 https://cookidoo.de/recipes/recipe/de-DE/r130616

📝 ZUTATEN
────────────────────────────────────────
  • 50 g Parmesan (in Stücken)
  • 1 rote Chilischote, getrocknet
  • 4 Knoblauchzehen
  • 1 Zwiebel (halbiert)
  • 30 g Öl
  • 1 Bund Basilikum (ohne Stiele)
  • 550 g Wasser
  • 400 g Cherry-Tomaten (halbiert oder geviertelt)
  • 20 g Tomatenmark
  • 1 TL Salz
  • 340 g Tagliatelle

👨🍳 ZUBEREITUNG
────────────────────────────────────────

  1. Parmesan in den Mixtopf geben, 10 Sek./Stufe 8
     zerkleinern und umfüllen.

  2. Chili, Knoblauch und Zwiebeln in den Mixtopf geben, 4
     Sek./Stufe 7 zerkleinern und mit dem Spatel nach unten
     schieben.
  ...
```

### Einkaufsliste generieren

```
$ tmx shopping show

🛒 Einkaufsliste
──────────────────────────────────────────────────

📖 Rezepte (5):
  • Auberginen-Pasta  [r292049]
  • Butter-Paneer-Masala  [r762577]
  • Tofu-Curry mit Gemüse  [r821223]
  • Pilzragout mit Spätzle  [r784889]
  • Halloumi-Wraps  [r823455]

🥕 Zutaten (70):

  [ ] 2  Auberginen
  [ ] 4.5 TL Salz
  [ ] 8 Prisen Pfeffer
  [ ] 3 EL Olivenöl
  [ ] 400 g Muschelnudeln
  [ ] 800 g Cherry-Tomaten, aus der Dose
  ...
```

---

## 📦 Installation

### Option 1: uvx (empfohlen)

```bash
# Direkt ausführen — keine Installation nötig
uvx --from git+https://github.com/Lars147/tmx-cli tmx --help

# Oder global installieren
uv tool install git+https://github.com/Lars147/tmx-cli
tmx --help

# Update auf neueste Version
uv tool install --upgrade git+https://github.com/Lars147/tmx-cli
```

### Option 2: pipx

```bash
pipx install git+https://github.com/Lars147/tmx-cli
tmx --help

# Update
pipx install --force git+https://github.com/Lars147/tmx-cli
```

### Option 3: Repo klonen

```bash
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py --help
```

---

## 📖 Usage

### 🔐 Authentifizierung

```bash
tmx login                                    # Interaktiv einloggen
tmx login --email user@example.com --password secret  # Mit Credentials
tmx status                                   # Login-Status prüfen
```

### 📅 Wochenplan

```bash
tmx plan show                    # Plan anzeigen (aus Cache)
tmx plan sync                    # Von Cookidoo synchronisieren
tmx plan sync --days 7           # Nur nächste 7 Tage
tmx plan sync --since 2026-02-01 # Ab bestimmtem Datum
tmx today                        # Nur heutige Rezepte

# Rezepte verwalten
tmx plan add r130616 --date 2026-02-10       # Hinzufügen
tmx plan remove r130616 --date 2026-02-10    # Entfernen
tmx plan move r130616 --from 2026-02-10 --to 2026-02-15  # Verschieben
```

### 🔍 Suche

```bash
tmx search "Pasta"                      # Einfache Suche
tmx search "Curry" -n 20                # Mehr Ergebnisse
tmx search "Salat" --time 15            # Max 15 Minuten
tmx search "Kuchen" --difficulty easy   # Nur einfache
tmx search "Suppe" --tm TM6             # Nur TM6-Rezepte
tmx search "" --category vegetarisch    # Nach Kategorie browsen
tmx search "Pasta" -t 30 -d easy        # Filter kombinieren
```

### 📂 Kategorien

```bash
tmx categories                  # Alle Kategorien auflisten
tmx categories sync             # Aktuelle von Cookidoo holen
```

### 📖 Rezeptdetails

```bash
tmx recipe r130616              # Zutaten, Schritte, Nährwerte
```

### ❤️ Favoriten

```bash
tmx favorites                   # Alle Favoriten anzeigen
tmx favorites add r130616       # Zu Favoriten hinzufügen
tmx favorites remove r130616    # Aus Favoriten entfernen
```

### 🛒 Einkaufsliste

```bash
# Anzeigen
tmx shopping show               # Aggregierte Liste
tmx shopping show --by-recipe   # Gruppiert nach Rezept

# Verwalten
tmx shopping add r130616        # Rezept hinzufügen
tmx shopping add-item "Milch" "Brot"  # Eigene Items hinzufügen
tmx shopping from-plan          # Alle Rezepte aus Plan (7 Tage)
tmx shopping from-plan -d 14    # Nächste 14 Tage
tmx shopping remove r130616     # Rezept entfernen
tmx shopping clear              # Liste leeren

# Exportieren
tmx shopping export                       # Text zu stdout
tmx shopping export -f markdown           # Markdown mit Checkboxen
tmx shopping export -f markdown -r        # Nach Rezept gruppiert
tmx shopping export -f json -o list.json  # JSON in Datei
```

### 🗑️ Cache

```bash
tmx cache clear                 # Cache leeren
tmx cache clear --all           # Auch Session (erfordert Re-Login)
```

### ⚡ Shell Completion

```bash
# Bash (zu ~/.bashrc hinzufügen)
eval "$(tmx completion bash)"

# Zsh (zu ~/.zshrc hinzufügen)
eval "$(tmx completion zsh)"

# Fish (einmalig ausführen)
tmx completion fish > ~/.config/fish/completions/tmx.fish
```

---

## 🔧 Wie es funktioniert

| Komponente | Technologie |
|------------|-------------|
| Authentifizierung | Vorwerk/Cidaas OAuth Flow |
| Wochenplan | Cookidoo Calendar API |
| Rezeptsuche | Algolia (wie Cookidoo-Website) |
| Speicherung | Lokale JSON-Dateien |

### Dateien

```
~/.tmx-cli/
├── cookidoo_cookies.json       # Session
├── cookidoo_search_token.json  # Such-Token
├── cookidoo_weekplan_raw.json  # Gecachter Plan
└── cookidoo_categories.json    # Kategorien
```

---

## 🤝 Contributing

Beiträge sind willkommen! 

1. Fork das Repo
2. Erstelle einen Feature-Branch (`git checkout -b feature/awesome`)
3. Committe deine Änderungen (`git commit -m 'Add awesome feature'`)
4. Push zum Branch (`git push origin feature/awesome`)
5. Öffne einen Pull Request

### Ideas & TODOs

- [ ] Collections-Support
- [ ] Meal-Plan Templates
- [ ] Nährwert-Summierung
- [ ] Recipe-Export (Markdown/PDF)

---

## ⚠️ Disclaimer

Dies ist ein **inoffizielles** Tool. Cookidoo® und Thermomix® sind eingetragene Marken der Vorwerk Gruppe.

Dieses Projekt steht in keiner Verbindung zu Vorwerk und wird nicht von Vorwerk unterstützt oder gesponsert. Bitte respektiere die Nutzungsbedingungen von Cookidoo.

---

## 📄 License

MIT © [Lars Heinen](https://github.com/Lars147)

---

<p align="center">
  <sub>Made with ❤️ for Thermomix-Nerds who live in the terminal</sub>
</p>
