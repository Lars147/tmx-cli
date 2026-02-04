<p align="center">
  <img src="logo.jpg" alt="tmx-cli logo" width="400">
</p>

<h1 align="center">tmx-cli</h1>

<p align="center">
  <strong>A pure Python CLI for managing your Cookidoo® (Thermomix®) weekly meal plan</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/dependencies-none-green.svg" alt="No dependencies">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
</p>

---

## Features

- 🔐 **Login** – Authenticate with your Cookidoo account
- 📅 **Weekly Plan** – View, sync, and manage your meal plan  
- 🔍 **Search** – Search 24,000+ recipes from Cookidoo
- ➕ **CRUD** – Add, remove, and move recipes in your plan
- 🛒 **Shopping List** – Generate ingredient lists from your plan
- 📦 **Zero dependencies** – Uses only Python standard library

## Quick Start

```bash
# Install via uvx (recommended)
uvx --from git+https://github.com/Lars147/tmx-cli tmx login

# Or clone and run directly
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py login
```

## Installation

### Option 1: uvx (recommended)

```bash
# Run directly without installation
uvx --from git+https://github.com/Lars147/tmx-cli tmx --help

# Or install globally
uv tool install git+https://github.com/Lars147/tmx-cli
tmx --help

# Upgrade to latest version
uv tool install --upgrade git+https://github.com/Lars147/tmx-cli
```

### Option 2: pipx

```bash
pipx install git+https://github.com/Lars147/tmx-cli
tmx --help

# Upgrade to latest version
pipx install --force git+https://github.com/Lars147/tmx-cli
```

### Option 3: Clone repository

```bash
git clone https://github.com/Lars147/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py --help
```

## Usage

### Login
```bash
tmx login
# Or with credentials:
tmx login --email user@example.com --password secret
```

### View Plan
```bash
tmx plan show      # Show cached plan
tmx plan sync      # Sync from Cookidoo (14 days)
tmx today          # Today's recipes
```

### Sync Options
```bash
tmx plan sync --days 7              # Next 7 days
tmx plan sync --since 2026-02-01    # From specific date
tmx plan sync -s 2026-02-01 -d 21   # 21 days from date
```

### Search Recipes
```bash
tmx search "Pasta"                  # Search recipes
tmx search "vegetarisch Curry" -n 20  # More results
```

### Manage Plan
```bash
# Add recipe to plan
tmx plan add r130616 --date 2026-02-10

# Remove recipe
tmx plan remove r130616 --date 2026-02-10

# Move recipe to another day
tmx plan move r130616 --from 2026-02-10 --to 2026-02-15
```

### Shopping List
```bash
tmx shopping show              # Show aggregated shopping list
tmx shopping show --by-recipe  # Show ingredients per recipe
tmx shopping add r130616       # Add recipe to shopping list
tmx shopping from-plan         # Add all recipes from plan (7 days)
tmx shopping from-plan -d 14   # Add recipes from next 14 days
tmx shopping remove r130616    # Remove recipe from shopping list
tmx shopping clear             # Clear entire shopping list

# Export shopping list
tmx shopping export                      # Plain text to stdout
tmx shopping export -f markdown          # Markdown with checkboxes
tmx shopping export -f markdown -r       # Grouped by recipe
tmx shopping export -f json -o list.json # JSON to file
```

### Status & Cache
```bash
tmx status             # Check login status and cache info
tmx cache clear        # Clear cached data (weekplan, search token)
tmx cache clear --all  # Also clear session cookies (requires re-login)
```

### Shell Completion

Enable tab completion for your shell:

**Bash** (add to `~/.bashrc`):
```bash
eval "$(tmx completion bash)"
```

**Zsh** (add to `~/.zshrc`):
```bash
eval "$(tmx completion zsh)"
```

**Fish** (run once):
```fish
tmx completion fish > ~/.config/fish/completions/tmx.fish
```

## How It Works

| Component | Technology |
|-----------|------------|
| Authentication | Vorwerk/Cidaas OAuth flow |
| Plan Sync | Cookidoo Calendar API |
| Recipe Search | Algolia (same as Cookidoo website) |
| Storage | Local JSON files |

## Files

```
~/.tmx-cli/           # or current directory
├── cookidoo_cookies.json       # Session (auto-created)
├── cookidoo_search_token.json  # Search token (auto-created)
└── cookidoo_weekplan_raw.json  # Cached plan
```

## Disclaimer

This is an unofficial tool. Cookidoo® and Thermomix® are trademarks of Vorwerk.  
Use responsibly and respect Cookidoo's terms of service.

## License

MIT © Lars Heinen
