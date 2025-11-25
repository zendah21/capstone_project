"""
Interactive loop to query Mapbox for food-related stores and print results.

Usage:
  MAPBOX_ACCESS_TOKEN=<token> python mapbox_search_loop.py

Then type a query (e.g., "supermarket near Salmiya, Kuwait"). Press Enter on a
blank line to exit.
"""

from __future__ import annotations

import os
import sys

from meal_planner_agent.store_finder_tools import search_nearby_stores


if not os.getenv("MAPBOX_ACCESS_TOKEN"):
    sys.exit("MAPBOX_ACCESS_TOKEN is not set. Please export it and retry.")

print("Mapbox store search. Enter a query (blank line to quit).")
while True:
    try:
        query = input("> ").strip()
    except EOFError:
        break
    if not query:
        break

    result = search_nearby_stores(query=query)
    features = result.get("features", [])
    if not features:
        print("No results.")
        continue

    for idx, feat in enumerate(features, 1):
        print(f"{idx}. {feat.get('name')}")
        print(f"   address: {feat.get('address')}")
        print(f"   lon/lat: [{feat.get('longitude')}, {feat.get('latitude')}]")
        print(f"   distance_m: {feat.get('distance_m')}")
        print(f"   category: {feat.get('category')}")
        print(f"   categories: {feat.get('categories')}")
        print(f"   brand: {feat.get('brand')}")
        print("---")
