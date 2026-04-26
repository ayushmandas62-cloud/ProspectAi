"""
Google Maps Places API Scraper
Finds businesses by niche + location using Places API.
Free tier: $200/month credit (auto-applied with billing enabled).
"""
import requests
import time


class GoogleMapsScraper:
    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self, api_key):
        self.api_key = api_key

    def search_businesses(self, query, location, max_results=30):
        """
        Search for businesses using Google Places Text Search.
        Returns list of business dicts with basic info.
        """
        results = []
        url = f"{self.BASE_URL}/textsearch/json"
        params = {
            "query": f"{query} in {location}",
            "key": self.api_key,
            "type": "establishment",
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if data.get("status") != "OK":
                return {"error": data.get("status", "Unknown error"), "results": []}

            for place in data.get("results", []):
                business = self._parse_place(place, location)
                results.append(business)

            # Handle pagination (Google returns 20 per page)
            next_token = data.get("next_page_token")
            while next_token and len(results) < max_results:
                time.sleep(2)  # Google requires delay before using next_page_token
                params = {"pagetoken": next_token, "key": self.api_key}
                response = requests.get(url, params=params, timeout=15)
                data = response.json()

                for place in data.get("results", []):
                    if len(results) >= max_results:
                        break
                    business = self._parse_place(place, location)
                    results.append(business)

                next_token = data.get("next_page_token")

        except requests.exceptions.RequestException as e:
            return {"error": str(e), "results": []}

        return {"error": None, "results": results[:max_results]}

    def get_place_details(self, place_id):
        """
        Get detailed info for a specific place (phone, website, hours).
        """
        url = f"{self.BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_phone_number,international_phone_number,"
                      "website,url,formatted_address,address_components,"
                      "rating,user_ratings_total,opening_hours,business_status,"
                      "types",
            "key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if data.get("status") != "OK":
                return None

            result = data.get("result", {})
            address_parts = self._parse_address(result.get("address_components", []))

            return {
                "phone": result.get("formatted_phone_number", ""),
                "international_phone": result.get("international_phone_number", ""),
                "website": result.get("website", ""),
                "google_maps_url": result.get("url", ""),
                "full_address": result.get("formatted_address", ""),
                "city": address_parts.get("city", ""),
                "state": address_parts.get("state", ""),
                "country": address_parts.get("country", ""),
                "rating": result.get("rating", 0),
                "review_count": result.get("user_ratings_total", 0),
                "is_open": result.get("business_status") == "OPERATIONAL",
                "hours": self._parse_hours(result.get("opening_hours", {})),
            }

        except requests.exceptions.RequestException:
            return None

    def search_and_enrich(self, query, location, max_results=30):
        """
        Search for businesses AND get detailed info for each.
        This is the main method to use.
        """
        search_result = self.search_businesses(query, location, max_results)

        if search_result.get("error"):
            return search_result

        enriched = []
        for business in search_result["results"]:
            place_id = business.get("place_id")
            if place_id:
                details = self.get_place_details(place_id)
                if details:
                    business.update(details)
                    # Determine if they have a website
                    business["has_website"] = 1 if business.get("website") else 0
                time.sleep(0.1)  # Be polite to API

            enriched.append(business)

        return {"error": None, "results": enriched}

    def _parse_place(self, place, search_location):
        """Parse a place result from Text Search."""
        return {
            "business_name": place.get("name", "Unknown"),
            "address": place.get("formatted_address", ""),
            "place_id": place.get("place_id", ""),
            "rating": place.get("rating", 0),
            "review_count": place.get("user_ratings_total", 0),
            "source": "google_maps",
            "search_location": search_location,
        }

    def _parse_address(self, components):
        """Extract city, state, country from address components."""
        result = {"city": "", "state": "", "country": ""}
        for comp in components:
            types = comp.get("types", [])
            if "locality" in types:
                result["city"] = comp.get("long_name", "")
            elif "administrative_area_level_1" in types:
                result["state"] = comp.get("short_name", "")
            elif "country" in types:
                result["country"] = comp.get("long_name", "")
        return result

    def _parse_hours(self, hours_data):
        """Parse opening hours into readable format."""
        if not hours_data:
            return ""
        weekday_text = hours_data.get("weekday_text", [])
        return " | ".join(weekday_text) if weekday_text else ""
