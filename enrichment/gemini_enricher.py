"""
Gemini AI Enricher (PRO FIXED VERSION)
Uses Google Gemini API to extract structured data from website text.
"""

import json
import re
import os
import google.generativeai as genai


class GeminiEnricher:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def enrich_from_text(self, raw_text, business_name="", existing_data=None):
        if existing_data is None:
            existing_data = {}

        missing_fields = []
        if not existing_data.get("owner_name"):
            missing_fields.append("owner_name")
        if not existing_data.get("email"):
            missing_fields.append("email")
        if not existing_data.get("phone"):
            missing_fields.append("phone")
        if not existing_data.get("facebook"):
            missing_fields.append("facebook")
        if not existing_data.get("instagram"):
            missing_fields.append("instagram")
        if not existing_data.get("twitter"):
            missing_fields.append("twitter")
        if not existing_data.get("linkedin"):
            missing_fields.append("linkedin")

        if not missing_fields:
            return {}

        truncated = raw_text[:6000]

        prompt = f"""
Extract the following details for business "{business_name}":

{", ".join(missing_fields)}

Text:
{truncated}

Return ONLY JSON like:
{{"owner_name": "", "email": "", "phone": "", "facebook": "", "instagram": "", "twitter": "", "linkedin": ""}}
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {k: v for k, v in data.items() if v}
            return {}

        except Exception as e:
            print("Gemini error:", e)
            return {}

    def analyze_website_quality(self, raw_text, business_name=""):
        truncated = raw_text[:4000]

        prompt = f"""
Analyze this business "{business_name}" and return JSON:

{{
"daily_inquiries": true/false,
"modern_website": true/false,
"has_booking": true/false,
"has_chatbot": true/false,
"needs_ai_receptionist": true/false,
"pitch": "short sentence"
}}

Text:
{truncated}
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return {}

        except Exception as e:
            print("Gemini analysis error:", e)
            return {}