#!/usr/bin/env python3
"""Thermomix/Cookidoo CLI - Wochenplan Management.

Rein Python, keine externen Dependencies (nur stdlib).

Nutzung:
    python3 tmx_cli.py login                    # Einloggen
    python3 tmx_cli.py plan show                # Wochenplan anzeigen
    python3 tmx_cli.py plan sync --since DATE   # Sync von Cookidoo
    python3 tmx_cli.py today                    # Heutige Rezepte
    python3 tmx_cli.py search "Linsen"          # Suche
"""

import argparse
import datetime as dt
import getpass
import json
import re
import ssl
import urllib.request
import urllib.error
import urllib.parse
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Config & Paths
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
WEEKPLAN_JSON = SCRIPT_DIR / "cookidoo_weekplan_raw.json"
COOKIES_FILE = SCRIPT_DIR / "cookidoo_cookies.json"

COOKIDOO_BASE = "https://cookidoo.de"
LOCALE = "de-DE"

# Algolia Search
ALGOLIA_APP_ID = "3TA8NT85XJ"
ALGOLIA_INDEX = "recipes-production-de"
SEARCH_TOKEN_FILE = SCRIPT_DIR / "cookidoo_search_token.json"


# ─────────────────────────────────────────────────────────────────────────────
# Cookie Management
# ─────────────────────────────────────────────────────────────────────────────

def load_cookies() -> dict[str, str]:
    """Load cookies from JSON file (Puppeteer format)."""
    if not COOKIES_FILE.exists():
        return {}
    
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        cookies_raw = json.load(f)
    
    # Puppeteer format: list of {name, value, domain, ...}
    cookies = {}
    for c in cookies_raw:
        name = c.get("name")
        value = c.get("value")
        if name and value:
            cookies[name] = value
    
    return cookies


def format_cookie_header(cookies: dict[str, str]) -> str:
    """Format cookies as HTTP Cookie header."""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def is_authenticated(cookies: dict[str, str]) -> bool:
    """Check if we have auth cookies."""
    return "v-authenticated" in cookies or "_oauth2_proxy" in cookies


def save_cookies_from_jar(jar: CookieJar):
    """Save cookies from CookieJar to JSON file (Puppeteer-compatible format)."""
    cookies_list = []
    for cookie in jar:
        cookies_list.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires or -1,
            "httpOnly": cookie.has_nonstandard_attr("HttpOnly"),
            "secure": cookie.secure,
            "session": cookie.expires is None,
        })
    
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies_list, f, ensure_ascii=False, indent=2)
    
    return cookies_list


# ─────────────────────────────────────────────────────────────────────────────
# Login Flow (Vorwerk/Cidaas OAuth)
# ─────────────────────────────────────────────────────────────────────────────

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Handler that captures redirects instead of following them."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Don't follow redirects


def do_login(email: str, password: str) -> tuple[bool, str]:
    """
    Perform Cookidoo login via Vorwerk/Cidaas OAuth.
    Returns (success, message).
    """
    ctx = ssl.create_default_context()
    jar = CookieJar()
    
    # Opener that follows redirects and stores cookies
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ctx),
    )
    
    headers_base = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    
    # Step 1: Start OAuth flow to get requestId
    print("  → Starte OAuth-Flow...")
    oauth_url = f"{COOKIDOO_BASE}/oauth2/start?market=de&ui_locales={LOCALE}&rd=/planning/{LOCALE}/my-week"
    
    req = urllib.request.Request(oauth_url, headers=headers_base)
    try:
        resp = opener.open(req, timeout=30)
        login_html = resp.read().decode("utf-8", errors="replace")
        login_url = resp.geturl()
    except urllib.error.HTTPError as e:
        return False, f"OAuth-Start fehlgeschlagen: HTTP {e.code}"
    except Exception as e:
        return False, f"OAuth-Start fehlgeschlagen: {e}"
    
    # Extract requestId from the login page
    request_id_match = re.search(r'name="requestId"\s+value="([^"]+)"', login_html)
    if not request_id_match:
        request_id_match = re.search(r'requestId=([^&"]+)', login_url)
    
    if not request_id_match:
        return False, "Konnte requestId nicht finden"
    
    request_id = request_id_match.group(1)
    
    # Step 2: Submit login form
    print("  → Sende Anmeldedaten...")
    login_post_url = "https://ciam.prod.cookidoo.vorwerk-digital.com/login-srv/login"
    
    login_data = urllib.parse.urlencode({
        "requestId": request_id,
        "username": email,
        "password": password,
    }).encode("utf-8")
    
    login_headers = {
        **headers_base,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://eu.login.vorwerk.com",
        "Referer": login_url,
    }
    
    req = urllib.request.Request(login_post_url, data=login_data, headers=login_headers)
    
    try:
        resp = opener.open(req, timeout=30)
        result_html = resp.read().decode("utf-8", errors="replace")
        final_url = resp.geturl()
    except urllib.error.HTTPError as e:
        if e.code in (302, 303, 307):
            # Redirect is expected - follow it manually
            final_url = e.headers.get("Location", "")
            result_html = ""
        else:
            return False, f"Login fehlgeschlagen: HTTP {e.code}"
    except Exception as e:
        return False, f"Login fehlgeschlagen: {e}"
    
    # Step 3: Follow redirect chain back to Cookidoo
    print("  → Folge Redirects...")
    max_redirects = 10
    redirect_count = 0
    
    while redirect_count < max_redirects:
        # Check if we're back at Cookidoo with auth
        if "cookidoo.de" in final_url and "oauth2/start" not in final_url:
            # Try to access the final URL
            req = urllib.request.Request(final_url, headers=headers_base)
            try:
                resp = opener.open(req, timeout=30)
                result_html = resp.read().decode("utf-8", errors="replace")
                final_url = resp.geturl()
                
                # Check if we're authenticated
                if "is-authenticated" in result_html or "my-week" in final_url:
                    break
            except:
                pass
        
        # Look for redirect in response
        redirect_match = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', result_html)
        if not redirect_match:
            redirect_match = re.search(r'<meta[^>]+http-equiv="refresh"[^>]+url=([^"\'>\s]+)', result_html, re.I)
        
        if redirect_match:
            next_url = redirect_match.group(1)
            if not next_url.startswith("http"):
                # Relative URL
                from urllib.parse import urljoin
                next_url = urljoin(final_url, next_url)
            
            req = urllib.request.Request(next_url, headers=headers_base)
            try:
                resp = opener.open(req, timeout=30)
                result_html = resp.read().decode("utf-8", errors="replace")
                final_url = resp.geturl()
            except urllib.error.HTTPError as e:
                if e.code in (302, 303, 307):
                    final_url = e.headers.get("Location", "")
                else:
                    break
            except:
                break
        else:
            break
        
        redirect_count += 1
    
    # Step 4: Verify we got auth cookies
    auth_cookies = {c.name: c.value for c in jar if "cookidoo" in c.domain}
    
    if "v-authenticated" in auth_cookies or "_oauth2_proxy" in auth_cookies:
        # Save cookies
        save_cookies_from_jar(jar)
        cookie_count = len([c for c in jar])
        return True, f"Login erfolgreich! {cookie_count} Cookies gespeichert."
    
    # Check for login errors
    if "falsches Passwort" in result_html.lower() or "incorrect" in result_html.lower():
        return False, "Falsches Passwort"
    if "nicht gefunden" in result_html.lower() or "not found" in result_html.lower():
        return False, "E-Mail-Adresse nicht gefunden"
    
    return False, "Login fehlgeschlagen - keine Auth-Cookies erhalten"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Client
# ─────────────────────────────────────────────────────────────────────────────

def fetch(url: str, cookies: dict[str, str]) -> tuple[int, str]:
    """Fetch URL with cookies, return (status, body)."""
    ctx = ssl.create_default_context()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    
    if cookies:
        headers["Cookie"] = format_cookie_header(cookies)
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        print(f"HTTP Error: {e}")
        return 0, ""


# ─────────────────────────────────────────────────────────────────────────────
# HTML Parser for Cookidoo Calendar (Regex-based)
# ─────────────────────────────────────────────────────────────────────────────

def parse_weekplan_html(html: str) -> list[dict]:
    """Parse calendar/week HTML and extract days with recipes using regex."""
    days = []
    
    # Split by day blocks: <li class="my-week__day ...">
    day_pattern = re.compile(
        r'<li\s+class="my-week__day([^"]*)"[^>]*>.*?</li>',
        re.DOTALL
    )
    
    # Alternative: split by plan-week-day elements
    day_blocks = re.findall(
        r'<plan-week-day[^>]*date="([^"]+)"[^>]*>(.*?)</plan-week-day>',
        html,
        re.DOTALL
    )
    
    for date, block in day_blocks:
        # Extract day name and number
        day_short_match = re.search(r'class="my-week__day-short">([^<]+)<', block)
        day_num_match = re.search(r'class="my-week__day-number">([^<]+)<', block)
        is_today = 'my-week__today' in block or '>Heute<' in block
        
        day_name = day_short_match.group(1).strip() if day_short_match else ""
        day_number = day_num_match.group(1).strip() if day_num_match else ""
        
        # Extract recipes from this day
        recipes = []
        recipe_blocks = re.findall(
            r'<core-tile\s+data-recipe-id="([^"]+)"[^>]*>(.*?)</core-tile>',
            block,
            re.DOTALL
        )
        
        for recipe_id, recipe_block in recipe_blocks:
            # Title
            title_match = re.search(
                r'class="core-tile__description-text">([^<]+)<',
                recipe_block
            )
            title = title_match.group(1).strip() if title_match else None
            
            # Image
            img_match = re.search(
                r'<img[^>]+src="(https://assets\.tmecosys[^"]+)"',
                recipe_block
            )
            image = img_match.group(1) if img_match else None
            
            if title:
                recipes.append({
                    "id": recipe_id,
                    "title": title,
                    "url": f"{COOKIDOO_BASE}/recipes/recipe/{LOCALE}/{recipe_id}",
                    "image": image,
                })
        
        days.append({
            "date": date,
            "dayName": day_name,
            "dayNumber": day_number,
            "isToday": is_today,
            "recipes": recipes,
        })
    
    return days


# ─────────────────────────────────────────────────────────────────────────────
# Cookidoo API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_week(cookies: dict, date: str, today: str) -> list[dict]:
    """Fetch one week of recipes starting from date."""
    url = f"{COOKIDOO_BASE}/planning/{LOCALE}/calendar/week?date={date}&today={today}"
    status, html = fetch(url, cookies)
    
    if status != 200:
        print(f"  ⚠ Fehler beim Laden der Woche {date}: HTTP {status}")
        return []
    
    # Check for redirect to login
    if "oauth2/start" in html or "login" in html.lower()[:500]:
        return []
    
    return parse_weekplan_html(html)


def sync_weekplan(since: str, days_count: int = 14) -> dict:
    """Sync weekplan from Cookidoo, fetching specified number of days."""
    cookies = load_cookies()
    
    if not is_authenticated(cookies):
        return {"error": "Keine gültigen Cookies. Bitte zuerst einloggen."}
    
    today = dt.date.today().isoformat()
    all_days = []
    seen_dates = set()
    
    # Parse since date
    try:
        start_date = dt.date.fromisoformat(since)
    except ValueError:
        start_date = dt.date.today()
    
    # Calculate end date
    end_date = start_date + dt.timedelta(days=days_count)
    
    # Calculate weeks needed (each API call returns ~7 days)
    weeks_needed = (days_count // 7) + 2  # +2 for safety margin
    
    # Fetch multiple weeks
    for week_offset in range(weeks_needed):
        week_start = start_date + dt.timedelta(weeks=week_offset)
        
        # Stop if we're past our target range
        if week_start > end_date:
            break
            
        week_date = week_start.isoformat()
        
        print(f"  → Lade Woche ab {week_date}...")
        days = fetch_week(cookies, week_date, today)
        
        if not days:
            if week_offset == 0:
                return {"error": "Session abgelaufen oder keine Daten. Bitte neu einloggen."}
            break
        
        for day in days:
            date = day.get("date")
            if date and date not in seen_dates:
                day_date = dt.date.fromisoformat(date)
                # Only include days within our range
                if start_date <= day_date < end_date:
                    seen_dates.add(date)
                    day["isToday"] = (date == today)
                    all_days.append(day)
    
    # Sort by date
    all_days.sort(key=lambda d: d.get("date", ""))
    
    return {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sinceDate": since,
        "weekplan": {"days": all_days},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cookidoo Recipe Search (Algolia)
# ─────────────────────────────────────────────────────────────────────────────

def get_search_token(cookies: dict[str, str]) -> Optional[str]:
    """Get Algolia search token from Cookidoo API."""
    # Check cached token
    if SEARCH_TOKEN_FILE.exists():
        try:
            with open(SEARCH_TOKEN_FILE, "r") as f:
                cached = json.load(f)
            # Check if still valid (with 5 min buffer)
            if cached.get("validUntil", 0) > dt.datetime.now().timestamp() + 300:
                return cached.get("apiKey")
        except:
            pass
    
    # Fetch new token
    url = f"{COOKIDOO_BASE}/search/api/subscription/token"
    status, body = fetch(url, cookies)
    
    if status != 200:
        return None
    
    try:
        data = json.loads(body)
        # Cache token
        with open(SEARCH_TOKEN_FILE, "w") as f:
            json.dump(data, f)
        return data.get("apiKey")
    except:
        return None


def search_recipes(query: str, limit: int = 10) -> tuple[list[dict], int]:
    """
    Search Cookidoo recipes via Algolia.
    Returns (results, total_count).
    """
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return [], 0
    
    api_key = get_search_token(cookies)
    if not api_key:
        return [], 0
    
    # Algolia search API
    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
    
    query_data = json.dumps({
        "query": query,
        "hitsPerPage": limit,
    }).encode("utf-8")
    
    headers = {
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "X-Algolia-API-Key": api_key,
        "Content-Type": "application/json",
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=query_data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Suche fehlgeschlagen: {e}")
        return [], 0
    
    results = []
    for hit in data.get("hits", []):
        recipe_id = hit.get("id", "")
        results.append({
            "id": recipe_id,
            "title": hit.get("title", "Unbekannt"),
            "url": f"{COOKIDOO_BASE}/recipes/recipe/{LOCALE}/{recipe_id}",
            "image": hit.get("image"),
            "totalTime": hit.get("totalTime"),  # in seconds
            "rating": hit.get("rating"),
            "description": hit.get("description"),
        })
    
    return results, data.get("nbHits", 0)


def format_time(seconds: Optional[int]) -> str:
    """Format time in seconds to human-readable string."""
    if not seconds:
        return ""
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} Min"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"{hours}h {mins}min"
    return f"{hours}h"


# ─────────────────────────────────────────────────────────────────────────────
# Plan CRUD Operations
# ─────────────────────────────────────────────────────────────────────────────

def add_recipe_to_plan(recipe_id: str, date: str) -> tuple[bool, str]:
    """Add a recipe to the plan on a specific date."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = f"{COOKIDOO_BASE}/planning/{LOCALE}/api/my-day"
    
    data = json.dumps({
        "recipeSource": "VORWERK",
        "recipeIds": [recipe_id],
        "dayKey": date,
    }).encode("utf-8")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": COOKIDOO_BASE,
        "Referer": f"{COOKIDOO_BASE}/planning/{LOCALE}/my-week",
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("message", "Rezept hinzugefügt")
    except urllib.error.HTTPError as e:
        if e.code in (200, 201, 204):
            return True, "Rezept hinzugefügt"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def remove_recipe_from_plan(recipe_id: str, date: str) -> tuple[bool, str]:
    """Remove a recipe from the plan on a specific date."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = f"{COOKIDOO_BASE}/planning/{LOCALE}/api/my-day/{date}/recipes/{recipe_id}?recipeSource=VORWERK"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Accept": "application/json",
        "Origin": COOKIDOO_BASE,
        "Referer": f"{COOKIDOO_BASE}/planning/{LOCALE}/my-week",
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("message", "Rezept entfernt")
    except urllib.error.HTTPError as e:
        if e.code in (200, 204):
            return True, "Rezept entfernt"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def move_recipe_in_plan(recipe_id: str, from_date: str, to_date: str) -> tuple[bool, str]:
    """Move a recipe from one date to another."""
    # Remove from old date
    success, msg = remove_recipe_from_plan(recipe_id, from_date)
    if not success:
        return False, f"Entfernen fehlgeschlagen: {msg}"
    
    # Add to new date
    success, msg = add_recipe_to_plan(recipe_id, to_date)
    if not success:
        return False, f"Hinzufügen fehlgeschlagen: {msg}"
    
    return True, "Rezept verschoben"


# ─────────────────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────────────────

def load_weekplan() -> Optional[dict]:
    """Load weekplan from JSON file."""
    if not WEEKPLAN_JSON.exists():
        return None
    with open(WEEKPLAN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_weekplan(data: dict):
    """Save weekplan to JSON file."""
    with open(WEEKPLAN_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_plan_show(args):
    """Show the current Cookidoo weekplan."""
    data = load_weekplan()
    
    if not data:
        print("❌ Kein Wochenplan gefunden. Führe zuerst 'tmx plan sync' aus.")
        return
    
    if "error" in data:
        print(f"❌ {data['error']}")
        return
    
    timestamp = data.get("timestamp", "unbekannt")
    since_date = data.get("sinceDate", "unbekannt")
    weekplan = data.get("weekplan", {})
    days = weekplan.get("days", [])
    
    if not days:
        print("Keine Tage im Wochenplan gefunden.")
        return
    
    # Header
    print()
    print("╔" + "═" * 58 + "╗")
    print("║  🍳 COOKIDOO WOCHENPLAN" + " " * 34 + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  Stand: {timestamp[:16].replace('T', ' ')} UTC" + " " * 24 + "║")
    print(f"║  Ab: {since_date}" + " " * 42 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    for day in days:
        date = day.get("date", "")
        day_name = day.get("dayName", "")
        day_number = day.get("dayNumber", "")
        is_today = day.get("isToday", False)
        recipes = day.get("recipes", [])
        
        # Day header
        if is_today:
            print(f"▶ \033[1m{day_name} {day_number}.\033[0m  ({date})  ← heute")
        else:
            print(f"  {day_name} {day_number}.  ({date})")
        
        if recipes:
            for recipe in recipes:
                title = recipe.get("title", "Unbekannt")
                print(f"    • {title}")
        else:
            print("    (keine Rezepte)")
        
        print()
    
    print("─" * 60)
    print("  Sync: python3 tmx_cli.py plan sync")
    print()


def cmd_plan_sync(args):
    """Sync weekplan from Cookidoo via HTTP."""
    since = getattr(args, 'since', None) or dt.date.today().isoformat()
    days_count = getattr(args, 'days', 14)
    
    print()
    print(f"🔄 Synchronisiere Wochenplan ({days_count} Tage ab {since})...")
    print()
    
    cookies = load_cookies()
    if not is_authenticated(cookies):
        print("❌ Keine Session-Cookies gefunden.")
        print()
        answer = input("Jetzt einloggen? [J/n] ").strip().lower()
        if answer in ("", "j", "ja", "y", "yes"):
            print()
            email = input("E-Mail: ").strip()
            password = getpass.getpass("Passwort: ")
            print()
            success, message = do_login(email, password)
            print()
            if not success:
                print(f"❌ {message}")
                return
            print(f"✅ {message}")
            print()
        else:
            print("Abgebrochen. Führe 'tmx login' aus um dich einzuloggen.")
            return
    
    data = sync_weekplan(since, days_count)
    
    if "error" in data:
        print()
        print(f"❌ {data['error']}")
        return
    
    save_weekplan(data)
    
    days = data.get("weekplan", {}).get("days", [])
    recipe_count = sum(len(d.get("recipes", [])) for d in days)
    
    print()
    print(f"✅ {len(days)} Tage mit {recipe_count} Rezepten synchronisiert!")
    print()
    
    cmd_plan_show(args)


def cmd_today(args):
    """Show today's recipes."""
    data = load_weekplan()
    
    if not data:
        print("❌ Kein Wochenplan gefunden. Führe zuerst 'tmx plan sync' aus.")
        return
    
    days = data.get("weekplan", {}).get("days", [])
    today_str = dt.date.today().isoformat()
    today = None
    
    for day in days:
        if day.get("date") == today_str or day.get("isToday"):
            today = day
            break
    
    if not today:
        print("Keine Rezepte für heute gefunden.")
        print(f"(Letzter Sync vielleicht veraltet? Heute: {today_str})")
        return
    
    print()
    print("╔" + "═" * 50 + "╗")
    print("║  🍳 HEUTE" + " " * 40 + "║")
    print("╚" + "═" * 50 + "╝")
    print()
    
    recipes = today.get("recipes", [])
    if recipes:
        for recipe in recipes:
            title = recipe.get("title", "Unbekannt")
            url = recipe.get("url", "")
            print(f"  • {title}")
            if url:
                print(f"    {url}")
            print()
    else:
        print("  Keine Rezepte für heute geplant.")
        print()


def cmd_search(args):
    """Search Cookidoo recipes via Algolia."""
    query = args.query
    limit = getattr(args, 'limit', 10)
    
    print()
    print(f"🔍 Suche in Cookidoo: '{query}'")
    print("─" * 50)
    
    cookies = load_cookies()
    if not is_authenticated(cookies):
        print("❌ Nicht eingeloggt. Führe zuerst 'tmx login' aus.")
        return
    
    results, total = search_recipes(query, limit)
    
    if not results:
        print("Keine Rezepte gefunden.")
        print()
        return
    
    print(f"Gefunden: {total} Rezepte (zeige {len(results)})")
    print()
    
    for i, r in enumerate(results, 1):
        title = r.get("title", "Unbekannt")
        time_str = format_time(r.get("totalTime"))
        rating = r.get("rating")
        url = r.get("url", "")
        
        # Format: number, title, time, rating
        info_parts = []
        if time_str:
            info_parts.append(f"⏱ {time_str}")
        if rating:
            info_parts.append(f"⭐ {rating:.1f}")
        info = "  ".join(info_parts)
        
        print(f"  {i:2}. {title}")
        if info:
            print(f"      {info}")
        print(f"      {url}")
        print()


def cmd_status(args):
    """Show status of CLI and cookies."""
    print()
    print("📊 TMX-CLI Status")
    print("─" * 40)
    
    # Cookies
    cookies = load_cookies()
    if is_authenticated(cookies):
        print(f"✅ Session-Cookies: {len(cookies)} geladen")
    else:
        print("❌ Keine gültigen Session-Cookies")
    
    # Weekplan
    if WEEKPLAN_JSON.exists():
        data = load_weekplan()
        if data:
            ts = data.get("timestamp", "?")[:16].replace("T", " ")
            days = len(data.get("weekplan", {}).get("days", []))
            print(f"✅ Wochenplan: {days} Tage (Stand: {ts})")
        else:
            print("⚠ Wochenplan-Datei leer")
    else:
        print("❌ Kein Wochenplan gespeichert")
    
    print()
    print(f"Cookies: {COOKIES_FILE}")
    print(f"Daten:   {WEEKPLAN_JSON}")
    print()


def cmd_login(args):
    """Login to Cookidoo interactively."""
    print()
    print("🔐 Cookidoo Login")
    print("─" * 40)
    
    # Get credentials
    email = getattr(args, 'email', None)
    password = getattr(args, 'password', None)
    
    if not email:
        email = input("E-Mail: ").strip()
    if not password:
        password = getpass.getpass("Passwort: ")
    
    if not email or not password:
        print("❌ E-Mail und Passwort erforderlich.")
        return
    
    print()
    success, message = do_login(email, password)
    
    print()
    if success:
        print(f"✅ {message}")
        print()
        print("Du kannst jetzt den Wochenplan synchronisieren:")
        print("  python3 tmx_cli.py plan sync")
    else:
        print(f"❌ {message}")
    print()


def cmd_plan_add(args):
    """Add a recipe to the plan."""
    recipe_id = args.recipe_id
    date = args.date or dt.date.today().isoformat()
    
    # Validate date format
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        print(f"❌ Ungültiges Datum: {date} (Format: YYYY-MM-DD)")
        return
    
    print()
    print(f"➕ Füge Rezept {recipe_id} zu {date} hinzu...")
    
    success, message = add_recipe_to_plan(recipe_id, date)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


def cmd_plan_remove(args):
    """Remove a recipe from the plan."""
    recipe_id = args.recipe_id
    date = args.date
    
    if not date:
        print("❌ Datum erforderlich (--date YYYY-MM-DD)")
        return
    
    print()
    print(f"➖ Entferne Rezept {recipe_id} von {date}...")
    
    success, message = remove_recipe_from_plan(recipe_id, date)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


def cmd_plan_move(args):
    """Move a recipe to another date."""
    recipe_id = args.recipe_id
    from_date = args.from_date
    to_date = args.to_date
    
    if not from_date or not to_date:
        print("❌ --from und --to Datum erforderlich")
        return
    
    print()
    print(f"📦 Verschiebe Rezept {recipe_id} von {from_date} nach {to_date}...")
    
    success, message = move_recipe_in_plan(recipe_id, from_date, to_date)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI Parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="🍳 Thermomix/Cookidoo CLI - Wochenplan & Rezepte",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    
    # plan command with subcommands
    plan_parser = sub.add_parser("plan", help="Wochenplan verwalten")
    plan_sub = plan_parser.add_subparsers(dest="plan_action", required=True)
    
    plan_show = plan_sub.add_parser("show", help="Wochenplan anzeigen")
    plan_show.set_defaults(func=cmd_plan_show)
    
    plan_sync = plan_sub.add_parser("sync", help="Wochenplan von Cookidoo synchronisieren")
    plan_sync.add_argument(
        "--since", "-s",
        default=dt.date.today().isoformat(),
        help="Startdatum (YYYY-MM-DD, default: heute)"
    )
    plan_sync.add_argument(
        "--days", "-d",
        type=int,
        default=14,
        help="Anzahl Tage (default: 14)"
    )
    plan_sync.set_defaults(func=cmd_plan_sync)
    
    # plan add
    plan_add = plan_sub.add_parser("add", help="Rezept zum Plan hinzufügen")
    plan_add.add_argument("recipe_id", help="Rezept-ID (z.B. r130616)")
    plan_add.add_argument("--date", "-d", help="Datum (YYYY-MM-DD, default: heute)")
    plan_add.set_defaults(func=cmd_plan_add)
    
    # plan remove
    plan_remove = plan_sub.add_parser("remove", help="Rezept aus dem Plan entfernen")
    plan_remove.add_argument("recipe_id", help="Rezept-ID (z.B. r130616)")
    plan_remove.add_argument("--date", "-d", required=True, help="Datum (YYYY-MM-DD)")
    plan_remove.set_defaults(func=cmd_plan_remove)
    
    # plan move
    plan_move = plan_sub.add_parser("move", help="Rezept verschieben")
    plan_move.add_argument("recipe_id", help="Rezept-ID (z.B. r130616)")
    plan_move.add_argument("--from", "-f", dest="from_date", required=True, help="Von Datum")
    plan_move.add_argument("--to", "-t", dest="to_date", required=True, help="Nach Datum")
    plan_move.set_defaults(func=cmd_plan_move)
    
    # search command
    search_parser = sub.add_parser("search", help="Rezepte in Cookidoo suchen")
    search_parser.add_argument("query", help="Suchbegriff")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="Anzahl Ergebnisse (default: 10)")
    search_parser.set_defaults(func=cmd_search)
    
    # today command
    today_parser = sub.add_parser("today", help="Heutige Rezepte anzeigen")
    today_parser.set_defaults(func=cmd_today)
    
    # status command
    status_parser = sub.add_parser("status", help="Status anzeigen")
    status_parser.set_defaults(func=cmd_status)
    
    # login command
    login_parser = sub.add_parser("login", help="Bei Cookidoo einloggen")
    login_parser.add_argument("--email", "-e", help="E-Mail-Adresse")
    login_parser.add_argument("--password", "-p", help="Passwort")
    login_parser.set_defaults(func=cmd_login)
    
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
