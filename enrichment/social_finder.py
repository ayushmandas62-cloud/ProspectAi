"""
Social Media Finder — Checks common URL patterns for social profiles.
"""
import requests
from urllib.parse import urlparse


class SocialFinder:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def find_profiles(self, business_name, website_url=""):
        domain = ""
        if website_url:
            try:
                if not website_url.startswith("http"):
                    website_url = "https://" + website_url
                domain = urlparse(website_url).netloc.replace("www.", "")
            except Exception:
                pass

        slug = business_name.lower().replace(" ", "").replace("'", "").replace("&", "and")
        slug_dash = business_name.lower().replace(" ", "-").replace("'", "").replace("&", "and")
        domain_slug = domain.split(".")[0] if domain else slug

        candidates = {
            "facebook": [
                f"https://www.facebook.com/{slug}",
                f"https://www.facebook.com/{domain_slug}",
                f"https://www.facebook.com/{slug_dash}",
            ],
            "instagram": [
                f"https://www.instagram.com/{slug}",
                f"https://www.instagram.com/{domain_slug}",
                f"https://www.instagram.com/{slug_dash}",
            ],
            "linkedin": [
                f"https://www.linkedin.com/company/{slug}",
                f"https://www.linkedin.com/company/{slug_dash}",
                f"https://www.linkedin.com/company/{domain_slug}",
            ],
        }

        results = {}
        for platform, urls in candidates.items():
            for url in urls:
                if self._url_exists(url):
                    results[platform] = url
                    break
            if platform not in results:
                results[platform] = ""

        return results

    def _url_exists(self, url):
        try:
            resp = requests.head(url, headers=self.HEADERS, timeout=5, allow_redirects=True)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False
