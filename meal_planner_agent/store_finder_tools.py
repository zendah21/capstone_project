# store_finder_tools.py
from typing import Dict, Any, List, Optional
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")


async def search_nearby_stores(
    tool_context,
    query: str,
    user_location: Optional[Dict[str, float]] = None,
    max_results: int = 8,
) -> Dict[str, Any]:
    """
    ADK tool: search_nearby_stores

    Parameters (from agent):
      - query:
          Free-text like:
            "supermarket in Sabah Al Salem, Mubarak Al-Kabeer, Kuwait"
            "hypermarket near Fahaheel, Kuwait"
            "butcher in Salmiya, Kuwait"
      - user_location (optional):
          {
            "lat": <float>,
            "lng": <float>
          }
        If provided and numeric, we pass it as a Mapbox proximity hint.
        If None or invalid, we just search by query text.
      - max_results: max number of places to return.

    Returns:
      {"results": [ {name, address, lat, lng, distance_meters, source, raw}, ... ]}
    """

    # Guard: if the token is missing at runtime, fail gracefully instead of crashing import
    if not MAPBOX_TOKEN:
        return {"results": []}

    base_url = "https://api.mapbox.com/search/geocode/v6/forward"

    # Base params: query + limit + token
    params = {
        "q": query,
        "limit": max_results,
        "access_token": MAPBOX_TOKEN,
        "types": "poi",  # points of interest (supermarkets, shops, etc.)
    }

    # If we have usable lat/lng, add 'proximity' (Mapbox uses lon,lat)
    if user_location is not None:
        lat = user_location.get("lat")
        lng = user_location.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            params["proximity"] = f"{lng},{lat}"

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(base_url, params=params)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])

    normalized: List[Dict[str, Any]] = []
    for f in features:
        props = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [None, None])
        lng_f, lat_f = coords[0], coords[1]

        normalized.append(
            {
                "name": props.get("name") or f.get("place_name"),
                "address": props.get("full_address") or f.get("place_name"),
                "lat": lat_f,
                "lng": lng_f,
                "distance_meters": props.get("distance"),
                "source": "mapbox",
                "raw": props,  # optional: extra metadata
            }
        )

    return {"results": normalized}
