"""
Website Scraper
Visits business websites to extract emails, phones, social handles,
and assess website quality (chatbot presence, mobile-friendliness, etc.)
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class WebsiteScraper:
    # Common email patterns to ignore (not real contacts)
    IGNORE_EMAILS = {
        "noreply", "no-reply", "donotreply", "mailer-daemon",
        "postmaster", "webmaster", "abuse", "support@wordpress",
        "email@example", "your@email", "name@domain",
        "wixpress.com", "sentry.io", "googleapis.com"
    }

    SOCIAL_PATTERNS = {
        "facebook": r'(?:https?://)?(?:www\.)?facebook\.com/[\w.\-]+/?',
        "instagram": r'(?:https?://)?(?:www\.)?instagram\.com/[\w.\-]+/?',
        "twitter": r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[\w.\-]+/?',
        "linkedin": r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/[\w.\-]+/?',
    }

    CHATBOT_INDICATORS = [
        "tawk.to", "tidio", "intercom", "drift", "hubspot",
        "livechat", "zendesk", "freshchat", "crisp.chat",
        "manychat", "chatbot", "chat-widget", "messenger-widget",
        "dialogflow", "botpress", "landbot"
    ]

    BOOKING_INDICATORS = [
        "calendly", "acuity", "book-online", "book-now",
        "schedule-appointment", "booking-widget", "zocdoc",
        "opencare", "appointy", "setmore", "square appointments",
        "mindbody", "vagaro", "booksy", "schedulicity"
    ]

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }

    def scrape(self, url, timeout=10):
        """
        Scrape a business website for all useful data.
        Returns a dict with extracted info.
        """
        result = {
            "emails": [],
            "phones": [],
            "facebook": "",
            "instagram": "",
            "twitter": "",
            "linkedin": "",
            "has_chatbot": False,
            "has_booking": False,
            "is_mobile_friendly": False,
            "owner_name": "",
            "page_title": "",
        }

        if not url:
            return result

        # Ensure URL has scheme
        if not url.startswith("http"):
            url = "https://" + url

        try:
            response = requests.get(url, headers=self.HEADERS, timeout=timeout, allow_redirects=True)
            if response.status_code != 200:
                return result

            html = response.text
            soup = BeautifulSoup(html, "lxml")
            html_lower = html.lower()

            # Extract page title
            title_tag = soup.find("title")
            result["page_title"] = title_tag.get_text(strip=True) if title_tag else ""

            # Extract emails from main page
            result["emails"] = self._extract_emails(html, url)

            # Extract phone numbers
            result["phones"] = self._extract_phones(html, soup)

            # Extract social media handles
            socials = self._extract_socials(html, soup)
            result.update(socials)

            # Check for chatbot
            result["has_chatbot"] = self._has_chatbot(html_lower)

            # Check for booking system
            result["has_booking"] = self._has_booking(html_lower)

            # Check mobile friendliness
            result["is_mobile_friendly"] = self._is_mobile_friendly(soup)

            # Try to find owner/contact name
            result["owner_name"] = self._find_owner_name(soup)

            # Also check /contact and /about pages for more data
            for path in ["/contact", "/contact-us", "/about", "/about-us", "/team", "/our-team"]:
                sub_url = urljoin(url, path)
                try:
                    sub_response = requests.get(
                        sub_url, headers=self.HEADERS, timeout=7, allow_redirects=True
                    )
                    if sub_response.status_code == 200:
                        sub_html = sub_response.text
                        sub_soup = BeautifulSoup(sub_html, "lxml")

                        # Merge emails
                        sub_emails = self._extract_emails(sub_html, url)
                        result["emails"] = list(set(result["emails"] + sub_emails))

                        # Merge phones
                        sub_phones = self._extract_phones(sub_html, sub_soup)
                        result["phones"] = list(set(result["phones"] + sub_phones))

                        # Try owner name if not found yet
                        if not result["owner_name"]:
                            result["owner_name"] = self._find_owner_name(sub_soup)

                        # Merge socials
                        sub_socials = self._extract_socials(sub_html, sub_soup)
                        for platform in ["facebook", "instagram", "twitter", "linkedin"]:
                            if not result[platform] and sub_socials.get(platform):
                                result[platform] = sub_socials[platform]

                except requests.exceptions.RequestException:
                    continue

        except requests.exceptions.RequestException:
            pass

        return result

    def _extract_emails(self, html, base_url):
        """Extract email addresses from HTML."""
        domain = urlparse(base_url).netloc.replace("www.", "")
        pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        raw_emails = re.findall(pattern, html)

        clean = []
        for email in raw_emails:
            email = email.lower().strip()
            # Filter out junk emails
            if any(ignore in email for ignore in self.IGNORE_EMAILS):
                continue
            if email.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js")):
                continue
            if len(email) > 80:
                continue
            clean.append(email)

        return list(set(clean))[:5]  # Max 5 emails

    def _extract_phones(self, html, soup):
        """Extract phone numbers from HTML."""
        phones = set()

        # From tel: links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
                phone = re.sub(r'[^\d+\-() ]', '', phone)
                if len(phone) >= 7:
                    phones.add(phone)

        # From text using regex patterns
        patterns = [
            r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}',  # US format
            r'\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}',  # International
            r'0\d{2,4}[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}',  # UK/AU format
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                phone = match.strip()
                if len(phone) >= 7:
                    phones.add(phone)

        return list(phones)[:3]  # Max 3 phone numbers

    def _extract_socials(self, html, soup):
        """Extract social media profile URLs."""
        socials = {"facebook": "", "instagram": "", "twitter": "", "linkedin": ""}

        # From links in the page
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower().strip()
            if "facebook.com/" in href and not socials["facebook"]:
                if "/sharer" not in href and "/share" not in href:
                    socials["facebook"] = a_tag["href"].strip()
            elif "instagram.com/" in href and not socials["instagram"]:
                socials["instagram"] = a_tag["href"].strip()
            elif ("twitter.com/" in href or "x.com/" in href) and not socials["twitter"]:
                if "/intent/" not in href and "/share" not in href:
                    socials["twitter"] = a_tag["href"].strip()
            elif "linkedin.com/" in href and not socials["linkedin"]:
                if "/share" not in href:
                    socials["linkedin"] = a_tag["href"].strip()

        # Fallback: regex on raw HTML
        for platform, pattern in self.SOCIAL_PATTERNS.items():
            if not socials[platform]:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    socials[platform] = matches[0]

        return socials

    def _has_chatbot(self, html_lower):
        """Check if the page has a chatbot widget."""
        return any(indicator in html_lower for indicator in self.CHATBOT_INDICATORS)

    def _has_booking(self, html_lower):
        """Check if the page has online booking."""
        return any(indicator in html_lower for indicator in self.BOOKING_INDICATORS)

    def _is_mobile_friendly(self, soup):
        """Check if the site has a viewport meta tag (basic mobile check)."""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        return viewport is not None

    def _find_owner_name(self, soup):
        """Try to find the owner/doctor/attorney name from the page."""
        # Look for common patterns
        patterns_to_search = [
            r'(?:Dr\.|Doctor|Attorney|Atty\.|Esq\.)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'(?:founded by|owner|principal|managing partner|lead attorney)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
        ]

        text = soup.get_text()
        for pattern in patterns_to_search:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # Look in structured data (schema.org)
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                import json
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    # Check for founder/owner
                    for key in ["founder", "author", "employee"]:
                        person = data.get(key)
                        if person and isinstance(person, dict):
                            name = person.get("name", "")
                            if name:
                                return name
            except (json.JSONDecodeError, TypeError):
                continue

        return ""
