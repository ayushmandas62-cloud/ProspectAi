"""
ProspectAI Configuration
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()


class Config:
    # API Keys
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "")
    APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ProspectAI/1.0")

    # App Settings
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    DB_PATH = os.path.join(os.path.dirname(__file__), "data", "leads.db")
    NICHES_PATH = os.path.join(os.path.dirname(__file__), "data", "niches.json")

    @classmethod
    def has_google_maps(cls):
        return bool(cls.GOOGLE_MAPS_API_KEY)

    @classmethod
    def has_gemini(cls):
        return bool(cls.GEMINI_API_KEY)

    @classmethod
    def has_geoapify(cls):
        return bool(cls.GEOAPIFY_API_KEY)

    @classmethod
    def has_apollo(cls):
        return bool(cls.APOLLO_API_KEY)

    @classmethod
    def has_reddit(cls):
        return bool(cls.REDDIT_CLIENT_ID and cls.REDDIT_CLIENT_SECRET)

    @classmethod
    def get_niches(cls):
        with open(cls.NICHES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def api_status(cls):
        return {
            "google_maps": cls.has_google_maps(),
            "geoapify": cls.has_geoapify(),
            "gemini": cls.has_gemini(),
            "apollo": cls.has_apollo(),
            "reddit": cls.has_reddit(),
            "demo_mode": cls.DEMO_MODE,
        }
