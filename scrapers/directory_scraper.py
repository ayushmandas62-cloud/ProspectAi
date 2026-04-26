"""
Free Business Directory Scraper
Uses DuckDuckGo search to find businesses — completely free.
NO API key needed. NO billing. NO card.

Pipeline:
1. Search DuckDuckGo for businesses in the target niche + location
2. Filter results to business websites only (skip directories)
3. Return structured data for the enrichment pipeline
"""
import re
import time
import random
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


class DirectoryScraper:
    """Finds businesses via DuckDuckGo search — no API keys needed."""

    # Map niche IDs to search queries
    NICHE_QUERIES = {
        "dental": [
            "dentist {location} phone",
            "dental clinic {location} address",
            "dental office {location} contact",
        ],
        "law": [
            "law firm {location} phone",
            "attorney {location} address",
            "lawyer office {location} contact",
        ],
        "realestate": [
            "real estate agent {location} phone",
            "realtor {location} address",
            "real estate office {location} contact",
        ],
    }

    # Domains to skip (directories, not actual businesses)
    SKIP_DOMAINS = {
        "yelp.com", "yellowpages.com", "bbb.org", "angi.com",
        "thumbtack.com", "google.com", "facebook.com", "instagram.com",
        "wikipedia.org", "reddit.com", "youtube.com", "twitter.com",
        "linkedin.com", "tripadvisor.com", "healthgrades.com",
        "zocdoc.com", "vitals.com", "webmd.com", "nerdwallet.com",
        "avvo.com", "findlaw.com", "justia.com", "martindale.com",
        "realtor.com", "zillow.com", "trulia.com", "redfin.com",
        "apartments.com", "x.com", "tiktok.com", "pinterest.com",
        "amazon.com", "ebay.com", "craigslist.org",
    }

    def __init__(self):
        if DDGS is None:
            print("[DirectoryScraper] WARNING: ddgs package not installed. Run: pip install ddgs")

    def search_and_enrich(self, niche, location, max_results=30):
        """
        Main entry point. Search DuckDuckGo for businesses.
        Returns same format as Google Maps scraper.
        """
        if DDGS is None:
            return {"error": "DDGS_NOT_INSTALLED", "results": []}

        results = []
        seen_domains = set()

        queries = self.NICHE_QUERIES.get(niche, ["{niche} {location} phone".replace("{niche}", niche)])

        for query_template in queries:
            if len(results) >= max_results:
                break

            query = query_template.replace("{location}", location)
            try:
                ddgs = DDGS()
                search_results = list(ddgs.text(query, max_results=min(max_results * 2, 30)))

                for r in search_results:
                    if len(results) >= max_results:
                        break

                    biz = self._parse_search_result(r, niche, location)
                    if biz:
                        # Deduplicate by domain
                        domain = urlparse(biz.get("website", "")).netloc
                        if domain and domain not in seen_domains:
                            seen_domains.add(domain)
                            results.append(biz)

                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                print(f"[DirectoryScraper] Search error: {e}")
                continue

        if results:
            return {"error": None, "results": results}

        return {"error": "NO_RESULTS", "results": []}

    def _parse_search_result(self, result, niche, location):
        """Parse a DuckDuckGo search result into a business record."""
        title = result.get("title", "")
        url = result.get("href", "")
        body = result.get("body", "")

        if not url or not url.startswith("http"):
            return None

        # Skip directory sites — we only want actual business websites
        domain = urlparse(url).netloc.lower()
        base_domain = ".".join(domain.split(".")[-2:])  # Get "example.com" from "www.example.com"

        if base_domain in self.SKIP_DOMAINS:
            return None

        # Clean up business name from title
        # Titles often look like "Business Name | Dentist in Austin"
        # or "Business Name - General Dentistry"
        business_name = title
        for separator in [" | ", " - ", " :: ", " -- ", " : "]:
            if separator in business_name:
                business_name = business_name.split(separator)[0]

        # Remove common suffixes
        for suffix in [" LLC", " Inc", " Corp", " PC", " PLLC", " PA", " DDS",
                       " MD", " Esq", " JD", ".com", ".net", ".org"]:
            if business_name.endswith(suffix):
                business_name = business_name[:-len(suffix)]

        business_name = business_name.strip()
        if not business_name or len(business_name) < 3:
            return None

        # Extract phone number from body/snippet
        phone = ""
        phone_match = re.search(r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}', body)
        if phone_match:
            phone = phone_match.group()

        # Extract address hints from body
        address = ""
        # Look for patterns like "123 Main St" or "Suite 100"
        addr_match = re.search(
            r'(\d{1,5}\s+[A-Z][a-zA-Z\s]+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Ct|Pkwy|Hwy|Loop|Circle|Pl)\.?'
            r'(?:\s*(?:#|Suite|Ste|Apt|Unit)\s*\w+)?)',
            body
        )
        if addr_match:
            address = addr_match.group().strip()

        return {
            "business_name": business_name,
            "phone": phone,
            "website": url,
            "address": address,
            "city": "",  # Will be enriched via website scraping
            "state": "",
            "country": "",
            "rating": 0,
            "review_count": 0,
            "categories": "",
            "yelp_url": "",
            "source": "web_search",
        }
