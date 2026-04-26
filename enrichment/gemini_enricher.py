"""
Gemini AI Enricher
Uses Google Gemini API to extract structured data from unstructured website text.
Free tier: 60 requests/minute, 1500 requests/day.
Updated to use the new google-genai SDK.
"""
from google import genai
import json
import re


class GeminiEnricher:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"

    def enrich_from_text(self, raw_text, business_name="", existing_data=None):
        """
        Send raw website text to Gemini and extract structured contact info.
        Only fills in fields that are missing from existing_data.
        """
        if existing_data is None:
            existing_data = {}

        # Build a prompt that asks for only missing fields
        missing_fields = []
        if not existing_data.get("owner_name"):
            missing_fields.append("owner_name (the owner, founder, lead doctor, or managing partner)")
        if not existing_data.get("email"):
            missing_fields.append("email (the best business contact email)")
        if not existing_data.get("phone"):
            missing_fields.append("phone (the main business phone number)")
        if not existing_data.get("facebook"):
            missing_fields.append("facebook (Facebook page URL)")
        if not existing_data.get("instagram"):
            missing_fields.append("instagram (Instagram profile URL)")
        if not existing_data.get("twitter"):
            missing_fields.append("twitter (Twitter/X profile URL)")
        if not existing_data.get("linkedin"):
            missing_fields.append("linkedin (LinkedIn profile URL)")

        if not missing_fields:
            return {}  # Nothing to enrich

        # Truncate text to avoid token limits
        truncated = raw_text[:6000]

        prompt = f"""You are a data extraction assistant. From the following website text for the business "{business_name}", extract these missing contact details:

{chr(10).join(f'- {f}' for f in missing_fields)}

Website text:
---
{truncated}
---

Return ONLY a JSON object with the fields you found. Use empty string "" for fields you cannot find. Do not include any other text, markdown, or explanation. Just the raw JSON object.

Example format:
{{"owner_name": "John Smith", "email": "john@example.com", "phone": "(555) 123-4567", "facebook": "", "instagram": "", "twitter": "", "linkedin": ""}}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = response.text.strip()

            # Try to extract JSON from response
            # Sometimes Gemini wraps in ```json ... ```
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                # Only return non-empty values
                return {k: v for k, v in data.items() if v and v.strip()}
            else:
                return {}

        except Exception:
            return {}

    def analyze_website_quality(self, raw_text, business_name=""):
        """
        Analyze a website's quality and suitability for CodeSlayer's services.
        Returns a brief assessment.
        """
        truncated = raw_text[:4000]

        prompt = f"""Analyze this business website text for "{business_name}" and determine:

1. Does this business likely receive daily customer inquiries? (yes/no)
2. Does their website look modern/professional? (yes/no)
3. Do they have online booking/scheduling? (yes/no)
4. Do they have a chatbot or live chat? (yes/no)
5. Would they benefit from an AI receptionist? (yes/no)
6. One-sentence pitch: Why they need CodeSlayer's services.

Website text:
---
{truncated}
---

Return ONLY a JSON object. Example:
{{"daily_inquiries": true, "modern_website": false, "has_booking": false, "has_chatbot": false, "needs_ai_receptionist": true, "pitch": "Your clinic is missing after-hours bookings — an AI receptionist could capture those leads 24/7."}}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = response.text.strip()

            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}

        except Exception:
            return {}
