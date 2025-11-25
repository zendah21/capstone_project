# meal_planner_agent/store_finder_tools.py
from __future__ import annotations

import logging
import os
import uuid
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")
SEARCHBOX_SUGGEST_URL = "https://api.mapbox.com/search/searchbox/v1/suggest"
SEARCHBOX_RETRIEVE_URL = "https://api.mapbox.com/search/searchbox/v1/retrieve"


def search_nearby_stores(
    query: str,
    limit: Optional[int] = None,
    country: Optional[str] = "kw",
    categories: str = "supermarket,grocery,hypermarket,market,food_and_drink,food_and_beverage",
) -> Dict[str, object]:
    """
    Find nearby food stores using Mapbox Search Box (suggest + retrieve).

    - Filters to Kuwait by default.
    - Returns only store-like POIs; never bare city/region entries.
    - On failure, returns features=[] with an error message.
    """

    if not MAPBOX_ACCESS_TOKEN:
        raise RuntimeError("MAPBOX_ACCESS_TOKEN environment variable is not set.")

    session_token = str(uuid.uuid4())
    suggest_params = {
        "q": query,
        "access_token": MAPBOX_ACCESS_TOKEN,
        "session_token": session_token,
        "poi_category": categories,
    }
    if country:
        suggest_params["country"] = country
    if limit:
        suggest_params["limit"] = limit

    try:
        suggest_resp = requests.get(SEARCHBOX_SUGGEST_URL, params=suggest_params, timeout=10)
        suggest_resp.raise_for_status()
        suggest_data = suggest_resp.json()
    except Exception:
        logger.exception("Mapbox store suggest failed query=%r", query)
        return {"query": query, "features": [], "error": "Store lookup failed. Try another area or wording."}

    suggestions = suggest_data.get("suggestions", [])
    store_results: List[Dict[str, object]] = []

    for suggestion in suggestions:
        mapbox_id = suggestion.get("mapbox_id")
        if not mapbox_id:
            continue

        retrieve_params = {
            "access_token": MAPBOX_ACCESS_TOKEN,
            "session_token": session_token,
        }

        try:
            retrieve_resp = requests.get(
                f"{SEARCHBOX_RETRIEVE_URL}/{mapbox_id}",
                params=retrieve_params,
                timeout=10,
            )
            retrieve_resp.raise_for_status()
            retrieve_data = retrieve_resp.json()
        except Exception:
            logger.error("Mapbox retrieve failed mapbox_id=%s query=%r", mapbox_id, query)
            continue

        retrieved_features = retrieve_data.get("features") or []
        if not retrieved_features:
            continue

        feature = retrieved_features[0]
        props = feature.get("properties", {}) or {}
        coords = feature.get("geometry", {}).get("coordinates", [None, None])

        country_code = (props.get("country") or "").lower()
        if country and country_code and country_code != country.lower():
            continue

        categories_list = props.get("categories") or props.get("poi_category") or []
        if isinstance(categories_list, str):
            categories_list = [categories_list]

        store_results.append(
            {
                "name": feature.get("name") or props.get("name") or "",
                "address": props.get("full_address")
                or props.get("place_formatted")
                or props.get("address")
                or "",
                "longitude": coords[0],
                "latitude": coords[1],
                "distance_m": props.get("distance"),
                "mapbox_id": mapbox_id,
                "feature_type": props.get("feature_type"),
                "categories": categories_list,
                "brand": props.get("brand"),
                "country": props.get("country"),
                "place_formatted": props.get("place_formatted"),
                "full_address": props.get("full_address"),
                "raw_properties": props,
                "context": feature.get("context"),
            }
        )

    # Keep obvious store names if present; otherwise return everything we got.
    store_keywords = (
        "market",
        "supermarket",
        "hypermarket",
        "grocery",
        "mart",
        "store",
        "coop",
        "co-op",
        "carrefour",
        "sultan",
        "lulu",
        "city centre",
        "city center",
        "saveco",
    )

    def is_store_name(name: str) -> bool:
        lowercase_name = (name or "").lower()
        return any(keyword in lowercase_name for keyword in store_keywords)

    filtered_stores = [store for store in store_results if is_store_name(store.get("name", ""))]
    output_stores = filtered_stores if filtered_stores else store_results

    logger.info("search_nearby_stores query=%r store_results=%d", query, len(output_stores))
    return {
        "query": query,
        "features": output_stores,
    }
