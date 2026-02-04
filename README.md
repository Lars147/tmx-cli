<p align="center">
  <img src="logo.jpg" alt="TMX-CLI Logo" width="400">
</p>

# TMX-CLI

A pure Python CLI for managing your Cookidoo® (Thermomix®) weekly meal plan.

**No external dependencies** – uses only Python standard library.

## Features

- 🔐 **Login** – Authenticate with your Cookidoo account
- 📅 **Weekly Plan** – View, sync, and manage your meal plan
- 🔍 **Search** – Search 24,000+ recipes from Cookidoo
- ➕ **Add/Remove/Move** – Full CRUD operations on your plan

## Installation

Just clone and run – Python 3.9+ required:

```bash
git clone https://github.com/YOUR_USERNAME/tmx-cli.git
cd tmx-cli
python3 tmx_cli.py --help
```

## Usage

### Login
```bash
python3 tmx_cli.py login
# Or with credentials:
python3 tmx_cli.py login --email user@example.com --password secret
```

### View Plan
```bash
python3 tmx_cli.py plan show
python3 tmx_cli.py today
```

### Sync from Cookidoo
```bash
# Sync next 14 days (default)
python3 tmx_cli.py plan sync

# Sync specific range
python3 tmx_cli.py plan sync --since 2026-02-01 --days 21
```

### Search Recipes
```bash
python3 tmx_cli.py search "Pasta"
python3 tmx_cli.py search "vegetarisch Curry" -n 20
```

### Manage Plan (CRUD)
```bash
# Add recipe to plan
python3 tmx_cli.py plan add r130616 --date 2026-02-10

# Remove recipe
python3 tmx_cli.py plan remove r130616 --date 2026-02-10

# Move recipe to another day
python3 tmx_cli.py plan move r130616 --from 2026-02-10 --to 2026-02-15
```

### Status
```bash
python3 tmx_cli.py status
```

## How It Works

- **Authentication**: OAuth flow with Vorwerk/Cidaas identity provider
- **Sync**: Fetches calendar data from Cookidoo's internal API
- **Search**: Uses Algolia search (same as Cookidoo website)
- **Storage**: Session cookies and plan cache stored as local JSON files

## Files

| File | Description |
|------|-------------|
| `tmx_cli.py` | Main CLI script |
| `cookidoo_cookies.json` | Session cookies (auto-created, gitignored) |
| `cookidoo_weekplan_raw.json` | Cached plan data (gitignored) |

## Disclaimer

This is an unofficial tool. Cookidoo® and Thermomix® are trademarks of Vorwerk.
Use responsibly and respect Cookidoo's terms of service.

## License

MIT
