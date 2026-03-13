"""
Fetches weather (yr.no) and road conditions (HAK) data.
Saves as static JSON files in data/ for GitHub Pages.
"""

import json
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {"User-Agent": "TeslaDashboard/1.0 github.com/stanwrites"}


def fetch_weather():
    """Fetch yr.no compact forecast for Zagreb and Rab."""
    cities = {
        "zagreb": {"lat": 45.8131, "lon": 15.9775},
        "rab": {"lat": 44.7561, "lon": 14.7603},
    }
    for city, coords in cities.items():
        url = (
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact"
            f"?lat={coords['lat']}&lon={coords['lon']}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            with open(os.path.join(DATA_DIR, f"weather_{city}.json"), "w") as f:
                json.dump(data, f, separators=(",", ":"))
            print(f"Weather {city}: OK")
        except Exception as e:
            print(f"Weather {city}: FAILED - {e}")


def fetch_hak():
    """Scrape HAK road conditions page."""
    url = "https://hak.hr/info/stanje-na-cestama/"
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; TeslaDashboard/1.0)",
            "Accept": "text/html",
        }, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        summary = ""
        details = ""

        # Try common content selectors
        content = (
            soup.select_one("div.field--name-body")
            or soup.select_one("article .content")
            or soup.select_one("div.view-content")
            or soup.select_one("main")
            or soup.select_one("#content")
        )

        if content:
            paragraphs = content.find_all("p")
            if paragraphs:
                summary = paragraphs[0].get_text(strip=True)
                detail_parts = []
                for p in paragraphs[1:30]:
                    text = p.get_text(strip=True)
                    if len(text) > 10:
                        detail_parts.append(text)
                details = "\n\n".join(detail_parts)
            else:
                full_text = content.get_text(" ", strip=True)
                summary = full_text[:300] + "..."
                details = full_text

        # Filter for relevant routes
        relevant = [
            "Zagreb", "Rab", "A1 ", "A6 ", "A7 ", "Senj", "Stinica",
            "Jablanac", "Kvarner", "Lika", "Gorski kotar", "bura",
            "magla", "zabran",
        ]
        if details:
            sections = details.split("\n\n")
            filtered = []
            for section in sections:
                for kw in relevant:
                    if kw.lower() in section.lower():
                        filtered.append(section)
                        break
            if filtered:
                details = "\n\n".join(filtered)

        if not summary:
            summary = "Nije moguce parsirati stranicu. Otvorite HAK.hr za detalje."

        result = {
            "summary": summary,
            "details": details,
            "timestamp": datetime.now().strftime("%H:%M, %d.%m.%Y."),
        }
        with open(os.path.join(DATA_DIR, "hak.json"), "w") as f:
            json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        print("HAK: OK")
    except Exception as e:
        print(f"HAK: FAILED - {e}")


def fetch_tesla():
    """Fetch Tesla vehicle state and recent drives from Tessie API."""
    api_key = os.environ.get("TESSIE_API_KEY", "")
    vin = os.environ.get("TESSIE_VIN", "")
    if not api_key or not vin:
        print("Tesla: SKIPPED - no TESSIE_API_KEY or TESSIE_VIN env var")
        return

    headers = {"Authorization": f"Bearer {api_key}"}

    # Vehicle state
    try:
        r = requests.get(
            f"https://api.tessie.com/{vin}/state",
            headers=headers, timeout=15,
        )
        r.raise_for_status()
        d = r.json()
        cs = d.get("charge_state", {})
        vs = d.get("vehicle_state", {})
        cl = d.get("climate_state", {})
        result = {
            "battery_level": cs.get("battery_level"),
            "battery_range_km": round(cs.get("battery_range", 0) * 1.60934, 1),
            "charging_state": cs.get("charging_state"),
            "charge_limit": cs.get("charge_limit_soc"),
            "charger_power": cs.get("charger_power"),
            "locked": vs.get("locked"),
            "odometer_km": round(vs.get("odometer", 0) * 1.60934, 1),
            "inside_temp": cl.get("inside_temp"),
            "outside_temp": cl.get("outside_temp"),
            "sentry_mode": vs.get("sentry_mode"),
            "timestamp": datetime.now().strftime("%H:%M, %d.%m.%Y."),
        }
        with open(os.path.join(DATA_DIR, "tesla.json"), "w") as f:
            json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        print("Tesla state: OK")
    except Exception as e:
        print(f"Tesla state: FAILED - {e}")

    # Recent drives
    try:
        r = requests.get(
            f"https://api.tessie.com/{vin}/drives?limit=5",
            headers=headers, timeout=15,
        )
        r.raise_for_status()
        d = r.json()
        drives = []
        for trip in d.get("results", []):
            drives.append({
                "started_at": trip.get("started_at"),
                "from": trip.get("starting_location", ""),
                "to": trip.get("ending_location", ""),
                "distance_km": round(trip.get("odometer_distance", 0) * 1.60934, 1),
                "energy_kwh": trip.get("energy_used"),
                "start_bat": trip.get("starting_battery"),
                "end_bat": trip.get("ending_battery"),
            })
        with open(os.path.join(DATA_DIR, "tesla_drives.json"), "w") as f:
            json.dump(drives, f, ensure_ascii=False, separators=(",", ":"))
        print("Tesla drives: OK")
    except Exception as e:
        print(f"Tesla drives: FAILED - {e}")


if __name__ == "__main__":
    fetch_weather()
    fetch_hak()
    fetch_tesla()
