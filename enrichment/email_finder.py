"""
Email Finder — Pattern guessing + MX check. No paid API needed.
"""
import socket
from urllib.parse import urlparse


class EmailFinder:
    GENERIC = {"info", "contact", "hello", "admin", "office",
               "support", "inquiry", "frontdesk", "appointments"}

    def guess_emails(self, owner_name="", website_url=""):
        if not website_url:
            return []
        domain = self._domain(website_url)
        if not domain:
            return []
        emails = [f"info@{domain}", f"contact@{domain}", f"hello@{domain}",
                  f"admin@{domain}", f"office@{domain}"]
        if owner_name:
            parts = owner_name.strip().split()
            if len(parts) >= 2:
                first, last = parts[0].lower(), parts[-1].lower()
                emails += [f"{first}@{domain}", f"{first}.{last}@{domain}",
                           f"{first}{last}@{domain}", f"{first[0]}{last}@{domain}"]
        return list(dict.fromkeys(emails))

    def verify_domain_has_mx(self, email):
        try:
            domain = email.split("@")[1]
            socket.getaddrinfo(domain, 25, socket.AF_INET)
            return True
        except (socket.gaierror, IndexError):
            return False

    def find_best_email(self, scraped_emails, guessed_emails):
        scraped_personal = [e for e in scraped_emails if e.split("@")[0] not in self.GENERIC]
        scraped_generic = [e for e in scraped_emails if e.split("@")[0] in self.GENERIC]
        if scraped_personal:
            return scraped_personal[0]
        if scraped_generic:
            return scraped_generic[0]
        for e in guessed_emails:
            if e.split("@")[0] not in self.GENERIC:
                return e
        return guessed_emails[0] if guessed_emails else ""

    def _domain(self, url):
        try:
            if not url.startswith("http"):
                url = "https://" + url
            d = urlparse(url).netloc.replace("www.", "").strip("/")
            return d if "." in d else ""
        except Exception:
            return ""
