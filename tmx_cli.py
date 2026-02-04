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
import sys
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
# Shopping List
# ─────────────────────────────────────────────────────────────────────────────

def get_shopping_list() -> Optional[dict]:
    """Get the current shopping list from Cookidoo."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return None
    
    url = f"{COOKIDOO_BASE}/shopping/{LOCALE}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Accept": "application/json",
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except:
        return None


def add_recipes_to_shopping_list(recipe_ids: list[str]) -> tuple[bool, str]:
    """Add recipes to the shopping list."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = f"{COOKIDOO_BASE}/shopping/{LOCALE}/add-recipes"
    
    data = json.dumps({"recipeIDs": recipe_ids}).encode("utf-8")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": COOKIDOO_BASE,
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("message", f"{len(recipe_ids)} Rezept(e) hinzugefügt")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def remove_recipe_from_shopping_list(recipe_id: str) -> tuple[bool, str]:
    """Remove a recipe from the shopping list."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = f"{COOKIDOO_BASE}/shopping/{LOCALE}/recipe/{recipe_id}/remove"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="DELETE")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("message", "Rezept entfernt")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def clear_shopping_list() -> tuple[bool, str]:
    """Clear the entire shopping list (recipes and additional items)."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = "https://cookidoo.de/shopping/de-DE"
    headers = {
        "Cookie": format_cookie_header(cookies),
        "Accept": "application/json",
    }
    
    try:
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            if resp.status == 200:
                return True, "Einkaufsliste geleert"
            return False, f"Unerwarteter Status: {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP-Fehler: {e.code}"
    except Exception as e:
        return False, str(e)


def add_custom_item_to_shopping_list(item_name: str) -> tuple[bool, str]:
    """Add a custom item (not from a recipe) to the shopping list."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return False, "Nicht eingeloggt"
    
    url = "https://cookidoo.de/shopping/de-DE/additional-item"
    headers = {
        "Cookie": format_cookie_header(cookies),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    payload = json.dumps({"itemValue": item_name}).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            if resp.status in (200, 201):
                return True, f"'{item_name}' hinzugefügt"
            return False, f"Unerwarteter Status: {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP-Fehler: {e.code}"
    except Exception as e:
        return False, str(e)


def parse_shopping_ingredients(shopping_data: dict) -> list[dict]:
    """Parse shopping list data into a flat ingredient list."""
    ingredients = []
    seen = set()  # To avoid duplicates
    
    for recipe in shopping_data.get("recipes", []):
        recipe_title = recipe.get("title", "Unbekannt")
        
        for ing in recipe.get("recipeIngredientGroups", []):
            name = ing.get("ingredientNotation", "")
            quantity = ing.get("quantity", {}).get("value", 0)
            unit = ing.get("unitNotation", "")
            preparation = ing.get("preparation", "")
            is_owned = ing.get("isOwned", False)
            optional = ing.get("optional", False)
            category = ing.get("shoppingCategory_ref", "")
            
            # Create unique key for deduplication
            key = f"{name}_{unit}"
            
            if key in seen:
                # Aggregate quantities for same ingredient
                for existing in ingredients:
                    if existing["name"] == name and existing["unit"] == unit:
                        existing["quantity"] += quantity
                        if recipe_title not in existing["recipes"]:
                            existing["recipes"].append(recipe_title)
                        break
            else:
                seen.add(key)
                ingredients.append({
                    "name": name,
                    "quantity": quantity,
                    "unit": unit,
                    "preparation": preparation,
                    "is_owned": is_owned,
                    "optional": optional,
                    "category": category,
                    "recipes": [recipe_title],
                })
    
    # Add additional items (manually added)
    for item in shopping_data.get("additionalItems", []):
        ingredients.append({
            "name": item.get("name", ""),
            "quantity": 1,
            "unit": "",
            "preparation": "",
            "is_owned": item.get("isOwned", False),
            "optional": False,
            "category": "manual",
            "recipes": ["Manuell hinzugefügt"],
        })
    
    return ingredients


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
        print("📅 Kein Wochenplan gefunden. Synchronisiere...")
        cmd_plan_sync(args, quiet=True)
        data = load_weekplan()
        if not data:
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
                rid = recipe.get("id", "")
                print(f"    • {title}  [{rid}]")
        else:
            print("    (keine Rezepte)")
        
        print()
    
    print("─" * 60)
    print("  Sync: python3 tmx_cli.py plan sync")
    print()


def cmd_plan_sync(args, quiet=False):
    """Sync weekplan from Cookidoo via HTTP."""
    since = getattr(args, 'since', None) or dt.date.today().isoformat()
    days_count = getattr(args, 'days', 14)
    
    if not quiet:
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
    
    if not quiet:
        print()
        print(f"✅ {len(days)} Tage mit {recipe_count} Rezepten synchronisiert!")
        print()
        cmd_plan_show(args)
    else:
        print(f"✅ Wochenplan synchronisiert ({len(days)} Tage, {recipe_count} Rezepte)")
        print()


def cmd_today(args):
    """Show today's recipes."""
    data = load_weekplan()
    
    if not data:
        print("📅 Kein Wochenplan gefunden. Synchronisiere...")
        cmd_plan_sync(args, quiet=True)
        data = load_weekplan()
        if not data:
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
            rid = recipe.get("id", "")
            url = recipe.get("url", "")
            print(f"  • {title}  [{rid}]")
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


def get_recipe_details(recipe_id: str) -> Optional[dict]:
    """Fetch recipe details from Cookidoo API."""
    cookies = load_cookies()
    if not is_authenticated(cookies):
        return None
    
    url = f"{COOKIDOO_BASE}/recipes/recipe/{LOCALE}/{recipe_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Cookie": format_cookie_header(cookies),
        "Accept": "application/json",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        return {"error": str(e)}


def cmd_recipe(args):
    """Show recipe details."""
    recipe_id = args.recipe_id
    
    # Ensure recipe_id starts with 'r'
    if not recipe_id.startswith('r'):
        recipe_id = f'r{recipe_id}'
    
    print()
    print(f"🍳 Lade Rezept {recipe_id}...")
    
    data = get_recipe_details(recipe_id)
    
    if not data:
        print("❌ Nicht eingeloggt. Führe 'tmx login' aus.")
        return
    
    if "error" in data:
        print(f"❌ Fehler: {data['error']}")
        return
    
    # Title and basic info
    title = data.get("title", "Unbekannt")
    difficulty = data.get("difficulty", "")
    difficulty_map = {"easy": "Einfach", "medium": "Mittel", "hard": "Schwer"}
    difficulty_str = difficulty_map.get(difficulty, difficulty)
    
    # Times
    times = data.get("times", [])
    active_time = None
    total_time = None
    for t in times:
        if t.get("type") == "activeTime":
            active_time = t.get("quantity", {}).get("value", 0) // 60
        elif t.get("type") == "totalTime":
            total_time = t.get("quantity", {}).get("value", 0) // 60
    
    # Servings
    serving_size = data.get("servingSize", {})
    servings = serving_size.get("quantity", {}).get("value", "")
    servings_unit = serving_size.get("unitNotation", "")
    
    # Header
    print()
    print("╔" + "═" * 58 + "╗")
    print(f"║  {title[:54]:<54}  ║")
    print("╠" + "═" * 58 + "╣")
    
    info_line = []
    if difficulty_str:
        info_line.append(f"📊 {difficulty_str}")
    if total_time:
        info_line.append(f"⏱ {total_time} Min")
    if servings:
        info_line.append(f"🍽 {servings} {servings_unit}")
    
    info_str = "  │  ".join(info_line)
    print(f"║  {info_str:<54}  ║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    # URL
    print(f"🔗 https://cookidoo.de/recipes/recipe/{LOCALE}/{recipe_id}")
    print()
    
    # Ingredients
    print("📝 ZUTATEN")
    print("─" * 40)
    for group in data.get("recipeIngredientGroups", []):
        group_title = group.get("title", "")
        if group_title:
            print(f"\n  {group_title}:")
        
        for ing in group.get("recipeIngredients", []):
            qty = ing.get("quantity", {}).get("value", "")
            unit = ing.get("unitNotation", "")
            name = ing.get("ingredientNotation", "")
            prep = ing.get("preparation", "")
            optional = ing.get("optional", False)
            
            # Format quantity
            if qty:
                if qty == int(qty):
                    qty_str = str(int(qty))
                else:
                    qty_str = f"{qty:.1f}"
            else:
                qty_str = ""
            
            # Build ingredient line
            parts = []
            if qty_str:
                parts.append(qty_str)
            if unit:
                parts.append(unit)
            parts.append(name)
            if prep:
                parts.append(f"({prep})")
            if optional:
                parts.append("(optional)")
            
            print(f"  • {' '.join(parts)}")
    print()
    
    # Steps
    print("👨‍🍳 ZUBEREITUNG")
    print("─" * 40)
    step_num = 1
    for group in data.get("recipeStepGroups", []):
        group_title = group.get("title", "")
        if group_title:
            print(f"\n  {group_title}:")
        
        for step in group.get("recipeSteps", []):
            text = step.get("formattedText", "")
            # Clean up HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('&nbsp;', ' ').strip()
            
            # Wrap long text
            if len(text) > 60:
                words = text.split()
                lines = []
                current_line = []
                for word in words:
                    if len(' '.join(current_line + [word])) > 55:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        current_line.append(word)
                if current_line:
                    lines.append(' '.join(current_line))
                
                print(f"\n  {step_num}. {lines[0]}")
                for line in lines[1:]:
                    print(f"     {line}")
            else:
                print(f"\n  {step_num}. {text}")
            
            step_num += 1
    print()
    
    # Nutrition (if available)
    nutrition_groups = data.get("nutritionGroups", [])
    if nutrition_groups:
        print("🥗 NÄHRWERTE (pro Portion)")
        print("─" * 40)
        for ng in nutrition_groups:
            for item in ng.get("nutritionItems", []):
                name = item.get("title", "")
                value = item.get("value", "")
                unit = item.get("unit", "")
                if name and value:
                    print(f"  • {name}: {value} {unit}")
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


def cmd_cache_clear(args):
    """Clear cached data files."""
    import os
    
    files = [
        ("Wochenplan", WEEKPLAN_JSON),
        ("Such-Token", SEARCH_TOKEN_FILE),
    ]
    
    # Optional: also clear cookies
    if getattr(args, 'all', False):
        files.append(("Session-Cookies", COOKIES_FILE))
    
    print()
    print("🗑️  Cache löschen")
    print("─" * 40)
    
    deleted = 0
    for name, path in files:
        if path.exists():
            os.remove(path)
            print(f"  ✅ {name} gelöscht")
            deleted += 1
        else:
            print(f"  ⏭️  {name} (nicht vorhanden)")
    
    print()
    if deleted:
        print(f"✅ {deleted} Datei(en) gelöscht.")
    else:
        print("ℹ️  Nichts zu löschen.")
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


def cmd_shopping_show(args):
    """Show the current shopping list."""
    by_recipe = getattr(args, 'by_recipe', False)
    
    print()
    print("🛒 Einkaufsliste")
    print("─" * 50)
    
    data = get_shopping_list()
    if not data:
        print("❌ Konnte Einkaufsliste nicht laden.")
        return
    
    recipes = data.get("recipes", [])
    if not recipes and not data.get("additionalItems"):
        print("Die Einkaufsliste ist leer.")
        print()
        print("Rezepte hinzufügen:")
        print("  tmx shopping add r123456")
        print("  tmx shopping from-plan")
        return
    
    if by_recipe:
        # Show ingredients grouped by recipe
        for recipe in recipes:
            rid = recipe.get('id', '')
            title = recipe.get('title', 'Unbekannt')
            print(f"\n📖 {title}  [{rid}]")
            print()
            
            for ing in recipe.get("recipeIngredientGroups", []):
                name = ing.get("ingredientNotation", "")
                qty = ing.get("quantity", {}).get("value", 0)
                unit = ing.get("unitNotation", "")
                prep = ing.get("preparation", "")
                is_owned = ing.get("isOwned", False)
                optional = ing.get("optional", False)
                
                prep_str = f" ({prep})" if prep else ""
                opt_str = " (optional)" if optional else ""
                
                if qty == int(qty):
                    qty_str = str(int(qty))
                else:
                    qty_str = f"{qty:.1f}"
                
                check = "✓" if is_owned else " "
                print(f"  [{check}] {qty_str} {unit} {name}{prep_str}{opt_str}")
        
        # Additional items
        additional = data.get("additionalItems", [])
        if additional:
            print(f"\n📝 Manuell hinzugefügt")
            print()
            for item in additional:
                check = "✓" if item.get("isOwned", False) else " "
                print(f"  [{check}] {item.get('name', '')}")
    else:
        # Show aggregated list (default)
        print(f"\n📖 Rezepte ({len(recipes)}):")
        for recipe in recipes:
            rid = recipe.get('id', '')
            print(f"  • {recipe.get('title')}  [{rid}]")
        
        # Parse and show ingredients
        ingredients = parse_shopping_ingredients(data)
        
        if ingredients:
            print(f"\n🥕 Zutaten ({len(ingredients)}):")
            print()
            
            # Group by owned status
            needed = [i for i in ingredients if not i["is_owned"]]
            owned = [i for i in ingredients if i["is_owned"]]
            
            for ing in needed:
                qty = ing["quantity"]
                unit = ing["unit"]
                name = ing["name"]
                prep = f" ({ing['preparation']})" if ing["preparation"] else ""
                opt = " (optional)" if ing["optional"] else ""
                
                # Format quantity nicely
                if qty == int(qty):
                    qty_str = str(int(qty))
                else:
                    qty_str = f"{qty:.1f}"
                
                print(f"  [ ] {qty_str} {unit} {name}{prep}{opt}")
            
            if owned:
                print(f"\n  ✓ {len(owned)} Zutaten bereits vorhanden")
    
    print()


def cmd_shopping_add(args):
    """Add recipes to the shopping list."""
    recipe_ids = args.recipe_ids
    
    print()
    print(f"🛒 Füge {len(recipe_ids)} Rezept(e) zur Einkaufsliste hinzu...")
    
    success, message = add_recipes_to_shopping_list(recipe_ids)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


def cmd_shopping_add_item(args):
    """Add a custom item to the shopping list."""
    items = args.items
    
    print()
    print(f"🛒 Füge {len(items)} Artikel zur Einkaufsliste hinzu...")
    
    added = 0
    for item in items:
        success, message = add_custom_item_to_shopping_list(item)
        if success:
            print(f"  ✅ {item}")
            added += 1
        else:
            print(f"  ❌ {item}: {message}")
    
    print()
    if added:
        print(f"✅ {added} Artikel hinzugefügt")
    print()


def cmd_shopping_remove(args):
    """Remove a recipe from the shopping list."""
    recipe_id = args.recipe_id
    
    print()
    print(f"🗑️ Entferne {recipe_id} von der Einkaufsliste...")
    
    success, message = remove_recipe_from_shopping_list(recipe_id)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


def cmd_shopping_clear(args):
    """Clear the entire shopping list."""
    print()
    print("🗑️ Leere die Einkaufsliste...")
    
    success, message = clear_shopping_list()
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
    print()


def cmd_shopping_export(args):
    """Export shopping list to various formats."""
    fmt = getattr(args, 'format', 'text')
    by_recipe = getattr(args, 'by_recipe', False)
    output_file = getattr(args, 'output', None)
    
    data = get_shopping_list()
    if not data:
        print("❌ Konnte Einkaufsliste nicht laden.", file=sys.stderr)
        return
    
    recipes = data.get("recipes", [])
    if not recipes and not data.get("additionalItems"):
        print("❌ Einkaufsliste ist leer.", file=sys.stderr)
        return
    
    lines = []
    
    if fmt == "json":
        import json as json_module
        output = json_module.dumps(data, indent=2, ensure_ascii=False)
    elif fmt == "markdown":
        if by_recipe:
            for recipe in recipes:
                title = recipe.get('title', 'Unbekannt')
                rid = recipe.get('id', '')
                lines.append(f"## {title} [{rid}]")
                lines.append("")
                for ing in recipe.get("recipeIngredientGroups", []):
                    name = ing.get("ingredientNotation", "")
                    qty = ing.get("quantity", {}).get("value", 0)
                    unit = ing.get("unitNotation", "")
                    qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
                    is_owned = ing.get("isOwned", False)
                    check = "x" if is_owned else " "
                    lines.append(f"- [{check}] {qty_str} {unit} {name}")
                lines.append("")
        else:
            ingredients = parse_shopping_ingredients(data)
            lines.append("# Einkaufsliste")
            lines.append("")
            for ing in ingredients:
                if ing["is_owned"]:
                    continue
                qty = ing["quantity"]
                qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
                lines.append(f"- [ ] {qty_str} {ing['unit']} {ing['name']}")
        
        # Additional items
        additional = data.get("additionalItems", [])
        if additional:
            lines.append("")
            lines.append("## Sonstiges")
            lines.append("")
            for item in additional:
                check = "x" if item.get("isOwned", False) else " "
                lines.append(f"- [{check}] {item.get('name', '')}")
        
        output = "\n".join(lines)
    else:  # text
        if by_recipe:
            for recipe in recipes:
                title = recipe.get('title', 'Unbekannt')
                lines.append(f"=== {title} ===")
                for ing in recipe.get("recipeIngredientGroups", []):
                    name = ing.get("ingredientNotation", "")
                    qty = ing.get("quantity", {}).get("value", 0)
                    unit = ing.get("unitNotation", "")
                    qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
                    lines.append(f"  {qty_str} {unit} {name}")
                lines.append("")
        else:
            ingredients = parse_shopping_ingredients(data)
            for ing in ingredients:
                if ing["is_owned"]:
                    continue
                qty = ing["quantity"]
                qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
                lines.append(f"{qty_str} {ing['unit']} {ing['name']}")
        
        # Additional items
        additional = data.get("additionalItems", [])
        if additional:
            lines.append("")
            lines.append("--- Sonstiges ---")
            for item in additional:
                lines.append(f"  {item.get('name', '')}")
        
        output = "\n".join(lines)
    
    # Output
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ Exportiert nach: {output_file}", file=sys.stderr)
    else:
        print(output)


def cmd_shopping_from_plan(args):
    """Add all recipes from the current plan to the shopping list."""
    days = getattr(args, 'days', 7)
    
    print()
    
    # Load current plan
    data = load_weekplan()
    if not data:
        print("📅 Kein Wochenplan gefunden. Synchronisiere...")
        cmd_plan_sync(args, quiet=True)
        data = load_weekplan()
        if not data:
            return
    
    print(f"🛒 Füge Rezepte der nächsten {days} Tage zur Einkaufsliste hinzu...")
    
    # Collect recipe IDs from plan
    recipe_ids = []
    today = dt.date.today()
    end_date = today + dt.timedelta(days=days)
    
    for day in data.get("weekplan", {}).get("days", []):
        date_str = day.get("date", "")
        try:
            day_date = dt.date.fromisoformat(date_str)
            if today <= day_date < end_date:
                for recipe in day.get("recipes", []):
                    rid = recipe.get("id")
                    if rid and rid not in recipe_ids:
                        recipe_ids.append(rid)
        except:
            continue
    
    if not recipe_ids:
        print("Keine Rezepte im Plan für die nächsten Tage gefunden.")
        return
    
    print(f"  → {len(recipe_ids)} Rezepte gefunden")
    
    success, message = add_recipes_to_shopping_list(recipe_ids)
    
    if success:
        print(f"✅ {message}")
        print()
        # Show the list
        cmd_shopping_show(args)
    else:
        print(f"❌ {message}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Shell Completion
# ─────────────────────────────────────────────────────────────────────────────

BASH_COMPLETION = '''
_tmx_completion() {
    local cur prev words cword
    _init_completion || return

    local commands="plan search recipe today shopping status cache login completion"
    local plan_cmds="show sync add remove move"
    local shopping_cmds="show add add-item from-plan remove clear export"
    local cache_cmds="clear"

    # Get the main command and subcommand
    local cmd="" subcmd=""
    for ((i=1; i < cword; i++)); do
        if [[ "${words[i]}" != -* ]]; then
            if [[ -z "$cmd" ]]; then
                cmd="${words[i]}"
            elif [[ -z "$subcmd" ]]; then
                subcmd="${words[i]}"
                break
            fi
        fi
    done

    # Complete options if current word starts with -
    if [[ "${cur}" == -* ]]; then
        case "$cmd" in
            plan)
                case "$subcmd" in
                    sync) COMPREPLY=($(compgen -W "--days -d --since -s --help" -- "${cur}")) ;;
                    add) COMPREPLY=($(compgen -W "--date -d --help" -- "${cur}")) ;;
                    remove) COMPREPLY=($(compgen -W "--date -d --help" -- "${cur}")) ;;
                    move) COMPREPLY=($(compgen -W "--from -f --to -t --help" -- "${cur}")) ;;
                    *) COMPREPLY=($(compgen -W "--help" -- "${cur}")) ;;
                esac ;;
            shopping)
                case "$subcmd" in
                    show) COMPREPLY=($(compgen -W "--by-recipe -r --help" -- "${cur}")) ;;
                    export) COMPREPLY=($(compgen -W "--format -f --by-recipe -r --output -o --help" -- "${cur}")) ;;
                    from-plan) COMPREPLY=($(compgen -W "--days -d --help" -- "${cur}")) ;;
                    *) COMPREPLY=($(compgen -W "--help" -- "${cur}")) ;;
                esac ;;
            search) COMPREPLY=($(compgen -W "--limit -n --help" -- "${cur}")) ;;
            cache)
                case "$subcmd" in
                    clear) COMPREPLY=($(compgen -W "--all -a --help" -- "${cur}")) ;;
                    *) COMPREPLY=($(compgen -W "--help" -- "${cur}")) ;;
                esac ;;
            login) COMPREPLY=($(compgen -W "--email -e --password -p --help" -- "${cur}")) ;;
            *) COMPREPLY=($(compgen -W "--help" -- "${cur}")) ;;
        esac
        return
    fi

    # Complete option values
    case "$prev" in
        --format|-f) COMPREPLY=($(compgen -W "text markdown json" -- "${cur}")); return ;;
    esac

    # Complete commands and subcommands
    case "${cword}" in
        1)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
        *)
            if [[ -z "$subcmd" ]]; then
                case "$cmd" in
                    plan) COMPREPLY=($(compgen -W "${plan_cmds}" -- "${cur}")) ;;
                    shopping) COMPREPLY=($(compgen -W "${shopping_cmds}" -- "${cur}")) ;;
                    cache) COMPREPLY=($(compgen -W "${cache_cmds}" -- "${cur}")) ;;
                    completion) COMPREPLY=($(compgen -W "bash zsh fish" -- "${cur}")) ;;
                esac
            fi
            ;;
    esac
}

complete -F _tmx_completion tmx
'''

ZSH_COMPLETION = '''
#compdef tmx

_tmx() {
    local curcontext="$curcontext" state line
    typeset -A opt_args

    _arguments -C \\
        '1: :->command' \\
        '*:: :->args'

    case "$state" in
        command)
            local -a commands
            commands=(
                'plan:Wochenplan verwalten'
                'search:Rezepte in Cookidoo suchen'
                'recipe:Rezeptdetails anzeigen'
                'today:Heutige Rezepte anzeigen'
                'shopping:Einkaufsliste verwalten'
                'status:Status anzeigen'
                'cache:Cache verwalten'
                'login:Bei Cookidoo einloggen'
                'completion:Shell-Completion ausgeben'
            )
            _describe 'command' commands
            ;;
        args)
            case "$line[1]" in
                plan)
                    _arguments -C '1: :->plan_cmd' '*:: :->plan_args'
                    case "$state" in
                        plan_cmd)
                            local -a plan_cmds
                            plan_cmds=(show sync add remove move)
                            _describe 'plan command' plan_cmds
                            ;;
                        plan_args)
                            case "$line[1]" in
                                sync) _arguments '--days[Anzahl Tage]:days' '-d[Anzahl Tage]:days' '--since[Startdatum]:date' '-s[Startdatum]:date' ;;
                                add) _arguments '1:recipe_id' '--date[Datum]:date' '-d[Datum]:date' ;;
                                remove) _arguments '1:recipe_id' '--date[Datum]:date' '-d[Datum]:date' ;;
                                move) _arguments '1:recipe_id' '--from[Von Datum]:date' '-f[Von Datum]:date' '--to[Nach Datum]:date' '-t[Nach Datum]:date' ;;
                            esac
                            ;;
                    esac
                    ;;
                shopping)
                    _arguments -C '1: :->shop_cmd' '*:: :->shop_args'
                    case "$state" in
                        shop_cmd)
                            local -a shop_cmds
                            shop_cmds=(show add add-item from-plan remove clear export)
                            _describe 'shopping command' shop_cmds
                            ;;
                        shop_args)
                            case "$line[1]" in
                                show) _arguments '--by-recipe[Pro Rezept]' '-r[Pro Rezept]' ;;
                                export) _arguments '--format[Format]:format:(text markdown json)' '-f[Format]:format:(text markdown json)' '--by-recipe[Pro Rezept]' '-r[Pro Rezept]' '--output[Datei]:file:_files' '-o[Datei]:file:_files' ;;
                                from-plan) _arguments '--days[Anzahl Tage]:days' '-d[Anzahl Tage]:days' ;;
                                add) _arguments '*:recipe_id' ;;
                                remove) _arguments '1:recipe_id' ;;
                            esac
                            ;;
                    esac
                    ;;
                cache)
                    _arguments -C '1: :->cache_cmd' '*:: :->cache_args'
                    case "$state" in
                        cache_cmd)
                            local -a cache_cmds
                            cache_cmds=(clear)
                            _describe 'cache command' cache_cmds
                            ;;
                        cache_args)
                            case "$line[1]" in
                                clear) _arguments '--all[Auch Cookies]' '-a[Auch Cookies]' ;;
                            esac
                            ;;
                    esac
                    ;;
                search)
                    _arguments '1:query' '--limit[Anzahl]:limit' '-n[Anzahl]:limit'
                    ;;
                recipe)
                    _arguments '1:recipe_id'
                    ;;
                login)
                    _arguments '--email[E-Mail]:email' '-e[E-Mail]:email' '--password[Passwort]:password' '-p[Passwort]:password'
                    ;;
                completion)
                    _arguments '1:shell:(bash zsh fish)'
                    ;;
            esac
            ;;
    esac
}

compdef _tmx tmx
'''

FISH_COMPLETION = '''
# tmx completions for fish

set -l commands plan search recipe today shopping status cache login completion
set -l plan_cmds show sync add remove move
set -l shopping_cmds show add add-item from-plan remove clear export
set -l cache_cmds clear

complete -c tmx -f
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "plan" -d "Wochenplan verwalten"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "search" -d "Rezepte suchen"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "recipe" -d "Rezeptdetails"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "today" -d "Heutige Rezepte"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "shopping" -d "Einkaufsliste"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "status" -d "Status anzeigen"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "cache" -d "Cache verwalten"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "login" -d "Einloggen"
complete -c tmx -n "not __fish_seen_subcommand_from $commands" -a "completion" -d "Shell-Completion"

# plan subcommands and options
complete -c tmx -n "__fish_seen_subcommand_from plan; and not __fish_seen_subcommand_from $plan_cmds" -a "show" -d "Anzeigen"
complete -c tmx -n "__fish_seen_subcommand_from plan; and not __fish_seen_subcommand_from $plan_cmds" -a "sync" -d "Synchronisieren"
complete -c tmx -n "__fish_seen_subcommand_from plan; and not __fish_seen_subcommand_from $plan_cmds" -a "add" -d "Hinzufügen"
complete -c tmx -n "__fish_seen_subcommand_from plan; and not __fish_seen_subcommand_from $plan_cmds" -a "remove" -d "Entfernen"
complete -c tmx -n "__fish_seen_subcommand_from plan; and not __fish_seen_subcommand_from $plan_cmds" -a "move" -d "Verschieben"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from sync" -l days -s d -d "Anzahl Tage"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from sync" -l since -s s -d "Startdatum"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from add" -l date -s d -d "Datum"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from remove" -l date -s d -d "Datum"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from move" -l from -s f -d "Von Datum"
complete -c tmx -n "__fish_seen_subcommand_from plan; and __fish_seen_subcommand_from move" -l to -s t -d "Nach Datum"

# shopping subcommands and options
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "show" -d "Anzeigen"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "add" -d "Rezepte hinzufügen"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "add-item" -d "Eigene Artikel"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "from-plan" -d "Aus Plan"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "remove" -d "Entfernen"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "clear" -d "Leeren"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and not __fish_seen_subcommand_from $shopping_cmds" -a "export" -d "Exportieren"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and __fish_seen_subcommand_from show" -l by-recipe -s r -d "Pro Rezept"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and __fish_seen_subcommand_from export" -l format -s f -d "Format" -a "text markdown json"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and __fish_seen_subcommand_from export" -l by-recipe -s r -d "Pro Rezept"
complete -c tmx -n "__fish_seen_subcommand_from shopping; and __fish_seen_subcommand_from export" -l output -s o -d "Datei" -r
complete -c tmx -n "__fish_seen_subcommand_from shopping; and __fish_seen_subcommand_from from-plan" -l days -s d -d "Anzahl Tage"

# cache subcommands and options
complete -c tmx -n "__fish_seen_subcommand_from cache; and not __fish_seen_subcommand_from $cache_cmds" -a "clear" -d "Löschen"
complete -c tmx -n "__fish_seen_subcommand_from cache; and __fish_seen_subcommand_from clear" -l all -s a -d "Auch Cookies"

# search options
complete -c tmx -n "__fish_seen_subcommand_from search" -l limit -s n -d "Anzahl Ergebnisse"

# login options
complete -c tmx -n "__fish_seen_subcommand_from login" -l email -s e -d "E-Mail"
complete -c tmx -n "__fish_seen_subcommand_from login" -l password -s p -d "Passwort"

# completion
complete -c tmx -n "__fish_seen_subcommand_from completion" -a "bash zsh fish" -d "Shell"
'''


def cmd_completion(args):
    """Output shell completion script."""
    shell = args.shell
    
    if shell == "bash":
        print(BASH_COMPLETION.strip())
    elif shell == "zsh":
        print(ZSH_COMPLETION.strip())
    elif shell == "fish":
        print(FISH_COMPLETION.strip())


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
    
    # recipe command
    recipe_parser = sub.add_parser("recipe", help="Rezeptdetails anzeigen")
    recipe_parser.add_argument("recipe_id", help="Rezept-ID (z.B. r130616)")
    recipe_parser.set_defaults(func=cmd_recipe)
    
    # today command
    today_parser = sub.add_parser("today", help="Heutige Rezepte anzeigen")
    today_parser.set_defaults(func=cmd_today)
    
    # shopping command with subcommands
    shopping_parser = sub.add_parser("shopping", help="Einkaufsliste verwalten")
    shopping_sub = shopping_parser.add_subparsers(dest="shopping_action", required=True)
    
    shopping_show = shopping_sub.add_parser("show", help="Einkaufsliste anzeigen")
    shopping_show.add_argument("--by-recipe", "-r", action="store_true", help="Zutaten pro Rezept anzeigen")
    shopping_show.set_defaults(func=cmd_shopping_show)
    
    shopping_add = shopping_sub.add_parser("add", help="Rezepte zur Einkaufsliste hinzufügen")
    shopping_add.add_argument("recipe_ids", nargs="+", help="Rezept-IDs (z.B. r130616 r123456)")
    shopping_add.set_defaults(func=cmd_shopping_add)
    
    shopping_add_item = shopping_sub.add_parser("add-item", help="Eigene Artikel hinzufügen (ohne Rezept)")
    shopping_add_item.add_argument("items", nargs="+", help="Artikelname(n) (z.B. 'Milch' 'Brot')")
    shopping_add_item.set_defaults(func=cmd_shopping_add_item)
    
    shopping_from_plan = shopping_sub.add_parser("from-plan", help="Rezepte aus dem Wochenplan hinzufügen")
    shopping_from_plan.add_argument("--days", "-d", type=int, default=7, help="Anzahl Tage (default: 7)")
    shopping_from_plan.set_defaults(func=cmd_shopping_from_plan)
    
    shopping_remove = shopping_sub.add_parser("remove", help="Rezept von der Einkaufsliste entfernen")
    shopping_remove.add_argument("recipe_id", help="Rezept-ID (z.B. r130616)")
    shopping_remove.set_defaults(func=cmd_shopping_remove)
    
    shopping_clear = shopping_sub.add_parser("clear", help="Einkaufsliste leeren")
    shopping_clear.set_defaults(func=cmd_shopping_clear)
    
    shopping_export = shopping_sub.add_parser("export", help="Einkaufsliste exportieren")
    shopping_export.add_argument("--format", "-f", choices=["text", "markdown", "json"], default="text", help="Format (default: text)")
    shopping_export.add_argument("--by-recipe", "-r", action="store_true", help="Nach Rezept gruppieren")
    shopping_export.add_argument("--output", "-o", help="Ausgabedatei (sonst stdout)")
    shopping_export.set_defaults(func=cmd_shopping_export)
    
    # status command
    status_parser = sub.add_parser("status", help="Status anzeigen")
    status_parser.set_defaults(func=cmd_status)
    
    # cache command
    cache_parser = sub.add_parser("cache", help="Cache verwalten")
    cache_sub = cache_parser.add_subparsers(dest="cache_action", required=True)
    
    cache_clear = cache_sub.add_parser("clear", help="Cache löschen")
    cache_clear.add_argument("--all", "-a", action="store_true", help="Auch Session-Cookies löschen")
    cache_clear.set_defaults(func=cmd_cache_clear)
    
    # login command
    login_parser = sub.add_parser("login", help="Bei Cookidoo einloggen")
    login_parser.add_argument("--email", "-e", help="E-Mail-Adresse")
    login_parser.add_argument("--password", "-p", help="Passwort")
    login_parser.set_defaults(func=cmd_login)
    
    # completion command
    completion_parser = sub.add_parser("completion", help="Shell-Completion ausgeben")
    completion_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell-Typ")
    completion_parser.set_defaults(func=cmd_completion)
    
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
