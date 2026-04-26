"""
Yelp Fusion API Scraper
Finds businesses by niche + location using Yelp's free API.
Free tier: 5000 API calls/day. No credit card required.
Sign up: https://www.yelp.com/developers/v3/manage_app
"""
import requests
import time


class YelpScraper:
    BASE_URL = "https://api.yelp.com/v3"

    # Map our niche IDs to Yelp category aliases
    NICHE_CATEGORIES = {
        "dental": "dentists,cosmeticdentists,generaldentistry,pediatricdentists",
        "law": "lawyers,bankruptcy,criminaldefense,familylaw,personalinjury,realestatelaw",
        "realestate": "realestate,realestateagents,propertymgmt,commercialrealestate",
    }

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def search_businesses(self, niche, location, max_results=30):
        """
        Search for businesses using Yelp Business Search.
        Returns list of business dicts with basic info.
        """
        results = []
        url = f"{self.BASE_URL}/businesses/search"

        categories = self.NICHE_CATEGORIES.get(niche, "")
        # Yelp returns max 50 per request, supports offset for pagination
        limit = min(max_results, 50)

        params = {
            "location": location,
            "categories": categories,
            "limit": limit,
            "sort_by": "best_match",
        }

        # If no category mapping, use term-based search
        if not categories:
            params.pop("categories")
            params["term"] = niche

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)

            if response.status_code == 401:
                return {"error": "YELP_AUTH_FAILED", "results": []}
            if response.status_code == 429:
                return {"error": "YELP_RATE_LIMIT", "results": []}
            if response.status_code != 200:
                return {"error": f"YELP_ERROR_{response.status_code}", "results": []}

            data = response.json()
            businesses = data.get("businesses", [])

            for biz in businesses:
                business = self._parse_business(biz)
                results.append(business)

            # Paginate if we need more results
            total = data.get("total", 0)
            offset = limit
            while len(results) < max_results and offset < min(total, 1000):
                time.sleep(0.2)  # Be polite
                params["offset"] = offset
                params["limit"] = min(max_results - len(results), 50)

                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                if response.status_code != 200:
                    break

                data = response.json()
                for biz in data.get("businesses", []):
                    if len(results) >= max_results:
                        break
                    business = self._parse_business(biz)
                    results.append(business)

                offset += params["limit"]

        except requests.exceptions.RequestException as e:
            return {"error": str(e), "results": []}

        return {"error": None, "results": results[:max_results]}

    def get_business_details(self, business_id):
        """
        Get detailed info for a specific Yelp business.
        Includes hours, photos, and more.
        """
        url = f"{self.BASE_URL}/businesses/{business_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return None

            biz = response.json()
            return {
                "phone": biz.get("display_phone", ""),
                "website": biz.get("url", ""),  # Yelp page URL
                "full_address": ", ".join(biz.get("location", {}).get("display_address", [])),
                "hours": self._parse_hours(biz.get("hours", [])),
                "photos": biz.get("photos", []),
                "is_open": not biz.get("is_closed", True),
            }

        except requests.exceptions.RequestException:
            return None

    def search_and_enrich(self, niche, location, max_results=30):
        """
        Search for businesses AND get detailed info for each.
        This is the main method to use.
        """
        search_result = self.search_businesses(niche, location, max_results)

        if search_result.get("error"):
            return search_result

        enriched = []
        for business in search_result["results"]:
            biz_id = business.get("yelp_id")
            if biz_id:
                details = self.get_business_details(biz_id)
                if details:
                    # Don't overwrite website if we already have a real one
                    if business.get("website") and details.get("website"):
                        details["yelp_url"] = details.pop("website")
                    business.update(details)
                time.sleep(0.15)  # Rate limit protection

            enriched.append(business)

        return {"error": None, "results": enriched}

    def _parse_business(self, biz):
        """Parse a business from Yelp search results."""
        location = biz.get("location", {})
        categories = biz.get("categories", [])
        category_names = ", ".join(c.get("title", "") for c in categories)

        return {
            "business_name": biz.get("name", "Unknown"),
            "yelp_id": biz.get("id", ""),
            "phone": biz.get("display_phone", ""),
            "website": "",  # Yelp search doesn't include website, detail does
            "address": ", ".join(location.get("display_address", [])),
            "city": location.get("city", ""),
            "state": location.get("state", ""),
            "country": location.get("country", ""),
            "rating": biz.get("rating", 0),
            "review_count": biz.get("review_count", 0),
            "yelp_url": biz.get("url", ""),
            "categories": category_names,
            "source": "yelp",
            "is_closed": biz.get("is_closed", False),
        }

    def _parse_hours(self, hours_data):
        """Parse Yelp hours into readable format."""
        if not hours_data:
            return ""
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        result = []
        for h in hours_data:
            if h.get("hours_type") == "REGULAR":
                for slot in h.get("open", []):
                    day = days[slot.get("day", 0)]
                    start = slot.get("start", "")
                    end = slot.get("end", "")
                    if start and end:
                        result.append(f"{day}: {start[:2]}:{start[2:]}-{end[:2]}:{end[2:]}")
        return " | ".join(result) if result else ""
