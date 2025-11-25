import os
import requests
from dotenv import load_dotenv
load_dotenv()

ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")

GEOCODE_URL = "https://api.mapbox.com/search/geocode/v6/forward"

KUWAIT_STORE_KEYWORDS = [
    "sultan", "lulu", "carrefour", "saveco", "city centre",
    "city center", "oncost", "coop", "co-op", "market",
    "hypermarket", "supermarket", "center"
]

def is_store(name: str):
    if not name:
        return False
    lower = name.lower()
    return any(k in lower for k in KUWAIT_STORE_KEYWORDS)

def search_kuwait_stores(query: str, area_hint: str = None):
    if not ACCESS_TOKEN:
        raise RuntimeError("MAPBOX_ACCESS_TOKEN not set!")

    q = f"{query}"
    if area_hint:
        q += f" in {area_hint}"

    params = {
        "q": q,
        "country": "kw",
        "types": "poi",
        "limit": 20,
        "access_token": ACCESS_TOKEN,
    }

    resp = requests.get(GEOCODE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for feat in data.get("features", []):
        name = feat.get("properties", {}).get("name")
        if not is_store(name):
            continue

        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [])

        results.append({
            "name": name,
            "address": props.get("full_address") or props.get("place_formatted"),
            "coords": coords,
            "brands": props.get("categories"),
            "distance": props.get("distance"),
        })

    return results


if __name__ == "__main__":
    stores = search_kuwait_stores("supermarket", "Salmiya")
    if not stores:
        print("❌ No real stores found")
    else:
        for s in stores:
            print("✔️", s)
