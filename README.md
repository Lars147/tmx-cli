<p align="center">
  <img src="logo.jpg" alt="tmx-cli Logo" width="400">
</p>

<h1 align="center">tmx-cli</h1>

<p align="center">
  A pure Python CLI for managing your Cookidoo® (Thermomix®) weekly meal plan.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/dependencies-none-green.svg" alt="No Dependencies">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
</p>

---

## Features

- 🔐 **Login** – Authenticate with your Cookidoo account (Vorwerk OAuth)
- 📅 **Weekly Plan** – View, sync, and manage your meal plan
- 🔍 **Search** – Search 24,000+ recipes from Cookidoo
- ➕ **CRUD** – Add, remove, and move recipes in your plan
- 📦 **Zero Dependencies** – Uses only Python standard library

## Quick Start

```bash
# Install
uvx --from git+https://github.com/Lars147/tmx-cli tmx --help

# Or clone and run directly
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py login
python3 tmx_cli.py plan sync
```

## Installation

### Option 1: uvx (recommended)

```bash
# Run directly without install
uvx --from git+https://github.com/Lars147/tmx-cli tmx plan show

# Or install globally
uvx install git+https://github.com/Lars147/tmx-cli
tmx plan sync
```

### Option 2: pipx

```bash
pipx install git+https://github.com/Lars147/tmx-cli
tmx plan sync
```

### Option 3: Clone

```bash
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py --help
```

## Usage

### Login
```bash
tmx login
```

### View Plan
```bash
tmx plan show      # Show cached plan
tmx plan sync      # Sync from Cookidoo (14 days)
tmx plan sync -d 7 # Sync 7 days
tmx today          # Today's recipes
```

### Search Recipes
```bash
tmx search "Pasta"
tmx search "vegetarisch Curry" -n 20
```

### Manage Plan
```bash
tmx plan add r130616 --date 2026-02-10      # Add recipe
tmx plan remove r130616 --date 2026-02-10   # Remove recipe
tmx plan move r130616 -f 2026-02-10 -t 2026-02-15  # Move recipe
```

### Status
```bash
tmx status
```

## How It Works

| Component | Technology |
|-----------|------------|
| Authentication | Vorwerk/Cidaas OAuth |
| Plan Sync | Cookidoo Calendar API |
| Recipe Search | Algolia (same as website) |
| Storage | Local JSON files |

## Files

```
~/.tmx-cli/                    # Coming soon: XDG config
./cookidoo_cookies.json        # Session (gitignored)
./cookidoo_weekplan_raw.json   # Cache (gitignored)
```

## Disclaimer

This is an unofficial tool. Cookidoo® and Thermomix® are trademarks of Vorwerk.
Use responsibly and respect Cookidoo's terms of service.

## License

MIT
