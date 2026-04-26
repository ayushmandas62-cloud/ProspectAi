"""
Geoapify Places Scraper
Uses Geoapify's free Places API to find businesses.
Free tier: 3000 requests/day. No credit card needed.
Sign up: https://myprojects.geoapify.com/register

Pipeline:
1. Geocode the location name to coordinates
2. Search for businesses in that area by category
3. Return structured data for the enrichment pipeline
"""
import requests
import time


class GeoapifyScraper:
    """Finds businesses via Geoapify Places API — free, no card needed."""

    BASE_URL = "https://api.geoapify.com"

    # Map niche IDs to Geoapify place categories
    # Full list: https://apidocs.geoapify.com/docs/places/#categories
    NICHE_CATEGORIES = {
        "dental": "healthcare.dentist",
        "law": "office.lawyer",
        "realestate": "office.estate_agent",
    }

    # Fallback category search terms for text-based search
    NICHE_CONDITIONS = {
        "dental": "dentist",
        "law": "lawyer,attorney,law firm",
        "realestate": "real estate,realtor,estate agent",
    }

    def __init__(self, api_key):
        self.api_key = api_key

    def search_and_enrich(self, niche, location, max_results=30):
        """
        Main entry point.
        1. Geocode location to get coordinates
        2. Search for businesses in category
        Returns same format as other scrapers.
        """
        # Step 1: Geocode the location
        coords = self._geocode(location)
        if not coords:
            return {"error": "GEOCODE_FAILED", "results": []}

        lat, lon = coords["lat"], coords["lon"]
        city = coords.get("city", "")
        state = coords.get("state", "")
        country = coords.get("country", "")

        # Step 2: Search for businesses
        category = self.NICHE_CATEGORIES.get(niche, "commercial")
        results = self._search_places(category, lat, lon, max_results)

        # If primary category returns too few, try with broader radius
        if len(results) < max_results // 2:
            more = self._search_places(category, lat, lon, max_results, radius=20000)
            seen = {r["business_name"] for r in results}
            for r in more:
                if r["business_name"] not in seen and len(results) < max_results:
                    results.append(r)
                    seen.add(r["business_name"])

        # Fill in city/state/country if missing
        for r in results:
            if not r.get("city"):
                r["city"] = city
            if not r.get("state"):
                r["state"] = state
            if not r.get("country"):
                r["country"] = country

        if results:
            return {"error": None, "results": results[:max_results]}

        return {"error": "ZERO_RESULTS", "results": []}

    def _geocode(self, location):
        """Convert location name to coordinates."""
        url = f"{self.BASE_URL}/v1/geocode/search"
        params = {
            "text": location,
            "apiKey": self.api_key,
            "limit": 1,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"[Geoapify] Geocode status {response.status_code}")
                return None

            data = response.json()
            features = data.get("features", [])
            if not features:
                return None

            props = features[0]["properties"]
            return {
                "lat": props.get("lat"),
                "lon": props.get("lon"),
                "city": props.get("city", props.get("county", "")),
                "state": props.get("state", ""),
                "country": props.get("country", ""),
            }

        except Exception as e:
            print(f"[Geoapify] Geocode error: {e}")
            return None

    def _search_places(self, category, lat, lon, max_results=30, radius=10000):
        """Search for places by category around coordinates."""
        results = []
        url = f"{self.BASE_URL}/v2/places"

        # Geoapify returns max 500 per request
        limit = min(max_results, 500)

        params = {
            "categories": category,
            "filter": f"circle:{lon},{lat},{radius}",
            "limit": limit,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 401:
                return []
            if response.status_code != 200:
                print(f"[Geoapify] Places status {response.status_code}")
                return []

            data = response.json()
            features = data.get("features", [])

            for feature in features:
                biz = self._parse_feature(feature)
                if biz:
                    results.append(biz)

        except Exception as e:
            print(f"[Geoapify] Places error: {e}")

        return results

    def _parse_feature(self, feature):
        """Parse a Geoapify feature into a business record."""
        props = feature.get("properties", {})
        contact = props.get("contact", {})
        datasource = props.get("datasource", {})
        raw = datasource.get("raw", {})

        name = props.get("name", "")
        if not name:
            return None

        # Extract phone — try multiple sources
        phone = contact.get("phone", "")
        if not phone:
            phone = raw.get("phone", "")

        # Extract website
        website = props.get("website", "")
        if not website:
            website = contact.get("website", "") or raw.get("website", "")

        # Extract email
        email = contact.get("email", "")
        if not email:
            email = raw.get("email", "")

        # Build address
        address = props.get("formatted", "")
        street = props.get("street", "")
        housenumber = props.get("housenumber", "")
        if street and housenumber:
            short_address = f"{housenumber} {street}"
        elif street:
            short_address = street
        else:
            short_address = address

        # Opening hours
        opening_hours = raw.get("opening_hours", "")

        return {
            "business_name": name,
            "phone": phone,
            "website": website,
            "email": email,
            "address": short_address if short_address else address,
            "full_address": address,
            "city": props.get("city", ""),
            "state": props.get("state", ""),
            "country": props.get("country", ""),
            "postcode": props.get("postcode", ""),
            "rating": 0,  # Geoapify doesn't provide ratings
            "review_count": 0,
            "categories": ", ".join(props.get("categories", [])),
            "opening_hours": opening_hours,
            "lat": props.get("lat", 0),
            "lon": props.get("lon", 0),
            "yelp_url": "",  # No directory URL
            "source": "geoapify",
        }
