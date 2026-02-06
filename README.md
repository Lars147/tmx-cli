<p align="center">
  <img src="logo.jpg" alt="tmx-cli logo" width="400">
</p>

<h1 align="center">tmx-cli</h1>

<p align="center">
  <strong>🍳 Your Thermomix®/Cookidoo® in the terminal — meal plans, recipes, shopping lists</strong>
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

## What is this?

**tmx-cli** brings Cookidoo® to your terminal. No more browser hassle — manage your weekly meal plan, search 24,000+ recipes, and generate shopping lists directly from the command line.

> ⚠️ **Disclaimer:** This is a hobby project for personal use. Not officially affiliated with or endorsed by Vorwerk/Cookidoo®.

It's fast (no slow web apps), hackable (pipe recipes into other tools, automate your meal prep), and runs anywhere with zero dependencies — just pure Python standard library.

---

## 🚀 Quick Start

```bash
# With uvx (recommended) — runs instantly without installation
uvx --from git+https://github.com/Lars147/tmx-cli tmx login

# Log in, then get started!
uvx --from git+https://github.com/Lars147/tmx-cli tmx search "Pasta"
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Setup** | Interactive onboarding — configure TM version, diet preferences, max cooking time |
| 🔐 **Login** | Secure OAuth authentication with your Cookidoo account |
| 📅 **Meal Plan** | View, sync, add/move recipes |
| 🔍 **Search** | Browse 24,000+ recipes with filters (time, difficulty, category) — auto-applies your config preferences |
| ❤️ **Favorites** | Manage your favorite recipes |
| 📖 **Recipe Details** | Ingredients, steps, nutrition — all in the terminal |
| 🛒 **Shopping List** | Auto-generate, export (Markdown/JSON) |
| ⚡ **Shell Completion** | Tab completion for Bash, Zsh, Fish |
| 📦 **Zero Deps** | Python standard library only, no dependencies |
| 🤖 **AI-Agent Friendly** | Perfect for Claude, Codex, OpenClaw & other AI assistants |

### Works great with AI Agents

The CLI approach makes tmx-cli ideal for AI coding assistants like **Claude Code**, **Codex**, or **OpenClaw**. Text-based, structured commands and parseable output mean AI agents can easily manage your meal planning for you — "add a vegetarian recipe to Thursday" just works.

---

## 🎬 Demo

### View meal plan

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

### Search recipes

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

### Get recipe details

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

### Generate shopping list

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

### Option 1: uvx (recommended)

```bash
# Run directly — no installation needed
uvx --from git+https://github.com/Lars147/tmx-cli tmx --help

# Or install globally
uv tool install git+https://github.com/Lars147/tmx-cli
tmx --help

# Update to latest version
uv tool install --upgrade git+https://github.com/Lars147/tmx-cli
```

### Option 2: pipx

```bash
pipx install git+https://github.com/Lars147/tmx-cli
tmx --help

# Update
pipx install --force git+https://github.com/Lars147/tmx-cli
```

### Option 3: Clone the repo

```bash
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py --help
```

---

## 📖 Usage

### 🎯 Setup & Configuration

```bash
tmx setup                        # Interactive onboarding
                                 # → TM version (TM5/TM6/TM7)
                                 # → Diet preferences (vegetarian, vegan, etc.)
                                 # → Max cooking time
                                 # Searches automatically use these preferences!
```

### 🔐 Authentication

```bash
tmx login                                    # Interactive login
tmx login --email user@example.com --password secret  # With credentials
tmx status                                   # Check login status
```

### 📅 Meal Plan

```bash
tmx plan show                    # Show plan (from cache)
tmx plan sync                    # Sync from Cookidoo
tmx plan sync --days 7           # Only next 7 days
tmx plan sync --since 2026-02-01 # From specific date
tmx today                        # Today's recipes only

# Manage recipes
tmx plan add r130616 --date 2026-02-10       # Add
tmx plan remove r130616 --date 2026-02-10    # Remove
tmx plan move r130616 --from 2026-02-10 --to 2026-02-15  # Move
```

### 🔍 Search

```bash
tmx search "Pasta"                      # Simple search
tmx search "Curry" -n 20                # More results
tmx search "Salat" --time 15            # Max 15 minutes
tmx search "Kuchen" --difficulty easy   # Easy recipes only
tmx search "Suppe" --tm TM6             # TM6 recipes only
tmx search "" --category vegetarisch    # Browse by category
tmx search "Pasta" -t 30 -d easy        # Combine filters

# 💡 Pro tip: Run `tmx setup` once — searches will auto-apply your
#    TM version, diet preferences, and max time filters!
```

### 📂 Categories

```bash
tmx categories                  # List all categories
tmx categories sync             # Fetch current from Cookidoo
```

### 📖 Recipe Details

```bash
tmx recipe r130616              # Ingredients, steps, nutrition
tmx recipe show r130616         # Same — detailed view with nutrition info
```

### ❤️ Favorites

```bash
tmx favorites                   # Show all favorites
tmx favorites add r130616       # Add to favorites
tmx favorites remove r130616    # Remove from favorites
```

### 🛒 Shopping List

```bash
# View
tmx shopping show               # Aggregated list
tmx shopping show --by-recipe   # Grouped by recipe

# Manage
tmx shopping add r130616        # Add recipe
tmx shopping add-item "Milk" "Bread"  # Add custom items
tmx shopping from-plan          # All recipes from plan (7 days)
tmx shopping from-plan -d 14    # Next 14 days
tmx shopping remove r130616     # Remove recipe
tmx shopping clear              # Clear list

# Export
tmx shopping export                       # Text to stdout
tmx shopping export -f markdown           # Markdown with checkboxes
tmx shopping export -f markdown -r        # Grouped by recipe
tmx shopping export -f json -o list.json  # JSON to file
```

### 🗑️ Cache

```bash
tmx cache clear                 # Clear cache
tmx cache clear --all           # Also session (requires re-login)
```

### ⚡ Shell Completion

```bash
# Bash (add to ~/.bashrc)
eval "$(tmx completion bash)"

# Zsh (add to ~/.zshrc)
eval "$(tmx completion zsh)"

# Fish (run once)
tmx completion fish > ~/.config/fish/completions/tmx.fish
```

---

## 🔧 How It Works

| Component | Technology |
|-----------|------------|
| Authentication | Vorwerk/Cidaas OAuth Flow |
| Meal Plan | Cookidoo Calendar API |
| Recipe Search | Algolia (same as Cookidoo website) |
| Storage | Local JSON files |

### Files

```
~/.tmx-cli/
├── cookidoo_cookies.json       # Session
├── cookidoo_search_token.json  # Search token
├── cookidoo_weekplan_raw.json  # Cached plan
└── cookidoo_categories.json    # Categories
```

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/awesome`)
3. Commit your changes (`git commit -m 'Add awesome feature'`)
4. Push to the branch (`git push origin feature/awesome`)
5. Open a Pull Request

### Ideas & TODOs

- [ ] Collections support
- [ ] Meal plan templates
- [ ] Nutrition summary
- [ ] Recipe export (Markdown/PDF)

---

## ⚠️ Disclaimer

This is an **unofficial** tool. Cookidoo® and Thermomix® are registered trademarks of the Vorwerk Group.

This project is not affiliated with, endorsed, or sponsored by Vorwerk. Please respect Cookidoo's terms of service.

---

## 📄 License

MIT © [Lars Heinen](https://github.com/Lars147)

---

<p align="center">
  <sub>Made with ❤️ for Thermomix nerds who live in the terminal</sub>
</p>
