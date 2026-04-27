"""
ProspectAI — Flask API Server (PRO FIXED VERSION)
"""
import os
import sys
import json
import csv
import io
import random
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from database.db import Database
from scrapers.geoapify_scraper import GeoapifyScraper
from scrapers.directory_scraper import DirectoryScraper
from scrapers.website_scraper import WebsiteScraper
from enrichment.gemini_enricher import GeminiEnricher
from enrichment.email_finder import EmailFinder
from enrichment.social_finder import SocialFinder
from scoring.lead_scorer import LeadScorer

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# ── ENV CONFIG ───────────────────────────────────────────
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "leads.db"),
)

# ── INIT SERVICES ────────────────────────────────────────
db = Database(DB_PATH)
scorer = LeadScorer()
website_scraper = WebsiteScraper()
email_finder = EmailFinder()

geoapify_scraper = GeoapifyScraper(GEOAPIFY_API_KEY) if GEOAPIFY_API_KEY else None
maps_scraper = None
directory_scraper = DirectoryScraper()
gemini = GeminiEnricher(GEMINI_API_KEY) if GEMINI_API_KEY else None

# ── Static Files ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

# ── API Status ───────────────────────────────────────────
@app.route("/api/status")
def api_status():
    return jsonify({"status": "running"})

# ── Simple Niches ────────────────────────────────────────
NICHES = {
    "niches": [
        {"id": "dental"},
        {"id": "law"},
        {"id": "realestate"}
    ]
}

@app.route("/api/niches")
def get_niches():
    return jsonify(NICHES)

# ── Search Leads ─────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search_leads():
    body = request.json or {}
    niche = body.get("niche", "dental")
    location = body.get("location", "New York")
    max_results = min(int(body.get("max_results", 20)), 50)

    leads = []

    try:
        search_result = None

        if geoapify_scraper:
            search_result = geoapify_scraper.search_and_enrich(niche, location, max_results)

        if not search_result and maps_scraper:
            search_result = maps_scraper.search_and_enrich(niche, location, max_results)

        if not search_result:
            search_result = directory_scraper.search_and_enrich(niche, location, max_results)

        if not search_result or not search_result.get("results"):
            return jsonify({"error": "No results found"})

        for biz in search_result["results"]:
            lead = {
                "business_name": biz.get("business_name", ""),
                "email": biz.get("email", ""),
                "phone": biz.get("phone", ""),
                "website": biz.get("website", ""),
                "city": location,
                "niche": niche,
            }

            score_result = scorer.score(lead)
            lead.update(score_result)

            result = db.insert_lead(lead)
            lead["id"] = result.get("id")

            leads.append(lead)

        return jsonify({"results": leads, "count": len(leads)})

    except Exception as e:
        return jsonify({"error": str(e)})

# ── Get Leads ────────────────────────────────────────────
@app.route("/api/leads")
def get_leads():
    leads = db.get_leads()
    return jsonify({"leads": leads})

# ── Run Server ───────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 ProspectAI Running...")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
