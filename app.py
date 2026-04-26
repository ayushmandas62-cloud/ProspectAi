"""
ProspectAI — Flask API Server
Main entry point for the lead generation backend.
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

sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from database.db import Database
from scrapers.google_maps import GoogleMapsScraper
from scrapers.geoapify_scraper import GeoapifyScraper
from scrapers.directory_scraper import DirectoryScraper
from scrapers.website_scraper import WebsiteScraper
from enrichment.gemini_enricher import GeminiEnricher
from enrichment.email_finder import EmailFinder
from enrichment.social_finder import SocialFinder
from scoring.lead_scorer import LeadScorer

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

db = Database(Config.DB_PATH)
scorer = LeadScorer()
website_scraper = WebsiteScraper()
email_finder = EmailFinder()

# Initialize services — priority: Geoapify (free) > Google Maps (needs billing) > DDG scraper (fallback)
geoapify_scraper = GeoapifyScraper(Config.GEOAPIFY_API_KEY) if Config.has_geoapify() else None
maps_scraper = GoogleMapsScraper(Config.GOOGLE_MAPS_API_KEY) if Config.has_google_maps() else None
directory_scraper = DirectoryScraper()  # Always available — no API key needed
gemini = GeminiEnricher(Config.GEMINI_API_KEY) if Config.has_gemini() else None


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
    return jsonify(Config.api_status())


# ── Niche Config ─────────────────────────────────────────
@app.route("/api/niches")
def get_niches():
    data = Config.get_niches()
    return jsonify(data)


# ── Friendly error messages ──────────────────────────────
API_ERROR_MESSAGES = {
    "REQUEST_DENIED": "Google Maps API: Billing not enabled. Go to console.cloud.google.com > Billing > Link a billing account (free $200/month credit applies automatically).",
    "OVER_QUERY_LIMIT": "Google Maps API: Daily query limit reached. Try again tomorrow or upgrade your plan.",
    "INVALID_REQUEST": "Google Maps API: Invalid request. Check your search query and location.",
    "ZERO_RESULTS": "No businesses found for this search. Try a different location or niche.",
}


# ── Search for Leads ─────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search_leads():
    body = request.json or {}
    niche = body.get("niche", "dental")
    location = body.get("location", "New York, NY")
    max_results = min(int(body.get("max_results", 30)), 60)
    # FIX: JS event listener was passing the MouseEvent object as use_demo
    # which Python sees as a truthy dict. Only accept explicit True boolean.
    use_demo = body.get("use_demo", False) is True

    # Get niche config
    niches_data = Config.get_niches()
    niche_config = None
    for n in niches_data.get("niches", []):
        if n["id"] == niche:
            niche_config = n
            break

    if not niche_config:
        return jsonify({"error": "Invalid niche"}), 400

    # Use demo data if explicitly requested or demo mode
    if use_demo or Config.DEMO_MODE:
        leads = _generate_demo_leads(niche_config, location, max_results)
        for lead in leads:
            score_result = scorer.score(lead)
            lead.update(score_result)
            lead["niche"] = niche
            result = db.insert_lead(lead)
            lead["id"] = result.get("id")
        db.log_search(niche, location, len(leads))
        return jsonify({"results": leads, "count": len(leads), "source": "demo"})

    # Real search — priority: Geoapify (free) > Google Maps (billing) > DDG scraper
    try:
        search_result = None
        source_name = "unknown"

        # Strategy 1: Geoapify (free, 3000 req/day, no card!)
        if geoapify_scraper:
            print(f"[ProspectAI] Searching Geoapify for {niche} in {location}...")
            search_result = geoapify_scraper.search_and_enrich(niche, location, max_results)
            source_name = "geoapify"

            if search_result.get("error"):
                print(f"[ProspectAI] Geoapify failed ({search_result['error']}), trying next source...")
                search_result = None

        # Strategy 2: Google Maps (requires billing)
        if not search_result and maps_scraper:
            query = niche_config["search_queries"][0]
            search_result = maps_scraper.search_and_enrich(query, location, max_results)
            source_name = "google_maps"

            if search_result.get("error"):
                print(f"[ProspectAI] Google Maps failed ({search_result['error']}), trying next source...")
                search_result = None

        # Strategy 3: Free web search scraper (no API key needed)
        if not search_result and directory_scraper:
            print(f"[ProspectAI] Using web search for {niche} in {location}...")
            search_result = directory_scraper.search_and_enrich(niche, location, max_results)
            source_name = "web_search"

        # No data source worked
        if not search_result or search_result.get("error"):
            error_code = search_result.get("error", "NO_SOURCE") if search_result else "NO_SOURCE"
            return jsonify({
                "error": "Could not find businesses. This may be a network issue. Try again or use demo data.",
                "error_code": error_code,
                "can_use_demo": True
            })

        if not search_result.get("results"):
            return jsonify({
                "error": "No businesses found. Try a different location.",
                "error_code": "ZERO_RESULTS",
                "can_use_demo": True
            })

        # Build leads directly from search results (FAST — no website scraping)
        # Website scraping happens lazily when user clicks "Enrich" on individual leads
        leads = []
        for biz in search_result["results"]:
            website_url = biz.get("website", "")

            # Build lead record from API data only
            lead = {
                "business_name": biz.get("business_name", ""),
                "owner_name": "",
                "email": biz.get("email", ""),
                "phone": biz.get("phone", ""),
                "website": website_url,
                "address": biz.get("full_address", biz.get("address", "")),
                "city": biz.get("city", ""),
                "state": biz.get("state", ""),
                "country": biz.get("country", ""),
                "niche": niche,
                "rating": biz.get("rating", 0),
                "review_count": biz.get("review_count", 0),
                "google_maps_url": biz.get("google_maps_url", biz.get("yelp_url", "")),
                "facebook": "",
                "instagram": "",
                "twitter": "",
                "linkedin": "",
                "has_chatbot": 0,
                "has_booking": 0,
                "is_mobile_friendly": 0,
                "has_website": 1 if website_url else 0,
                "source": source_name,
                "enriched": 0,
            }


            # Email finding deferred to enrichment step (faster search)

            # Score the lead
            score_result = scorer.score(lead)
            lead.update(score_result)

            # Save to DB
            result = db.insert_lead(lead)
            lead["id"] = result.get("id")
            leads.append(lead)

        db.log_search(niche, location, len(leads))
        return jsonify({"results": leads, "count": len(leads), "source": source_name})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Unexpected error during search: {str(e)}",
            "can_use_demo": True
        })


# ── Enrich a Lead with Gemini AI ─────────────────────────
@app.route("/api/enrich/<int:lead_id>", methods=["POST"])
def enrich_lead(lead_id):
    lead = db.get_lead(lead_id)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    if not gemini:
        return jsonify({"error": "Gemini API key not configured"}), 400

    if not lead.get("website"):
        return jsonify({"error": "No website to enrich from"}), 400

    try:
        import requests as req
        resp = req.get(lead["website"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        raw_text = soup.get_text(separator=" ", strip=True)[:6000]
    except Exception:
        return jsonify({"error": "Could not fetch website"}), 500

    enriched = gemini.enrich_from_text(raw_text, lead["business_name"], lead)
    if enriched:
        enriched["enriched"] = 1
        score_result = scorer.score({**lead, **enriched})
        enriched.update(score_result)
        db.update_lead(lead_id, enriched)

    updated = db.get_lead(lead_id)
    return jsonify({"lead": updated, "enriched_fields": list(enriched.keys())})


# ── Get All Leads ────────────────────────────────────────
@app.route("/api/leads")
def get_leads():
    filters = {
        "niche": request.args.get("niche"),
        "city": request.args.get("city"),
        "score_label": request.args.get("score_label"),
        "min_score": request.args.get("min_score"),
        "source": request.args.get("source"),
    }
    filters = {k: v for k, v in filters.items() if v}
    leads = db.get_leads(filters if filters else None)
    return jsonify({"leads": leads, "count": len(leads)})


# ── Get Single Lead ──────────────────────────────────────
@app.route("/api/leads/<int:lead_id>")
def get_lead(lead_id):
    lead = db.get_lead(lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    return jsonify(lead)


# ── Delete Lead ──────────────────────────────────────────
@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    db.delete_lead(lead_id)
    return jsonify({"status": "deleted"})


# ── Dashboard Stats ──────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    return jsonify(db.get_stats())


# ── Export CSV ───────────────────────────────────────────
@app.route("/api/export/csv")
def export_csv():
    leads = db.get_leads()
    if not leads:
        return jsonify({"error": "No leads to export"}), 400

    output = io.StringIO()
    fields = ["business_name", "owner_name", "email", "phone", "website",
              "address", "city", "state", "country", "niche", "rating",
              "review_count", "facebook", "instagram", "twitter", "linkedin",
              "score", "score_label", "source"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for lead in leads:
        writer.writerow(lead)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=prospectai_leads_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


# ── Clear All Leads ──────────────────────────────────────
@app.route("/api/leads/clear", methods=["POST"])
def clear_leads():
    db.clear_all()
    return jsonify({"status": "cleared"})


# ── Demo Data Generator ──────────────────────────────────
def _generate_demo_leads(niche_config, location, count):
    """Generate realistic demo leads for testing without API keys."""
    demo_data = {
        "dental": {
            "names": ["Bright Smile Dental", "City Dental Care", "Premier Dentistry",
                      "Sunshine Family Dental", "Elite Dental Studio", "Happy Teeth Clinic",
                      "Downtown Dental Group", "Gentle Care Dentistry", "Summit Dental Arts",
                      "Pacific Dental Center", "Lakeside Family Dental", "Heritage Dental",
                      "Modern Smile Dentistry", "Valley Dental Associates", "Parkview Dental"],
            "owners": ["Dr. Sarah Mitchell", "Dr. James Chen", "Dr. Emily Rodriguez",
                       "Dr. Michael Park", "Dr. Lisa Thompson", "Dr. Robert Kim",
                       "Dr. Jennifer Walsh", "Dr. David Patel", "Dr. Amanda Foster",
                       "Dr. Kevin Moore", "Dr. Rachel Green", "Dr. Thomas Lee",
                       "Dr. Maria Santos", "Dr. Andrew Blake", "Dr. Nicole Harris"],
            "domains": ["brightsmile", "citydentalcare", "premierdentistry",
                        "sunshinedental", "elitedentalstudio", "happyteeth",
                        "downtowndental", "gentlecaredentist", "summitdental",
                        "pacificdental", "lakesidedental", "heritagedental",
                        "modernsmile", "valleydental", "parkviewdental"],
        },
        "law": {
            "names": ["Johnson & Associates Law", "Sterling Legal Group", "Apex Law Partners",
                      "Chambers & White Attorneys", "Liberty Legal Services", "Titan Law Firm",
                      "Blackwell & Moore LLP", "Crestview Legal", "Paramount Law Office",
                      "Sullivan Legal Group", "Cedar Point Law", "Meridian Attorneys",
                      "Benchmark Legal", "Pinnacle Law Group", "Cornerstone Law Firm"],
            "owners": ["Attorney Mark Johnson", "Attorney Diana Sterling", "Attorney Richard Apex",
                       "Attorney Claire Chambers", "Attorney Nathan White", "Attorney Karen Brooks",
                       "Attorney David Blackwell", "Attorney Sara Cole", "Attorney John Paramount",
                       "Attorney Michelle Sullivan", "Attorney Greg Turner", "Attorney Helen Park",
                       "Attorney Frank Russo", "Attorney Laura Bennett", "Attorney Paul Davidson"],
            "domains": ["johnsonlaw", "sterlinglegal", "apexlawpartners",
                        "chamberswhite", "libertylegal", "titanlaw",
                        "blackwellmoore", "crestviewlegal", "paramountlaw",
                        "sullivanlegal", "cedarpointlaw", "meridianattorneys",
                        "benchmarklegal", "pinnaclelawgroup", "cornerstonelaw"],
        },
        "realestate": {
            "names": ["Prime Realty Group", "Horizon Real Estate", "Keystone Properties",
                      "BlueSky Realty", "Coastal Homes Group", "Summit Real Estate",
                      "Goldcrest Properties", "Metro Living Realty", "Evergreen Homes",
                      "Sapphire Real Estate", "Atlas Property Group", "Lighthouse Realty",
                      "Crown Properties", "Riverstone Homes", "Platinum Realty"],
            "owners": ["Agent Victoria Hayes", "Agent Marcus Reed", "Agent Sarah Brennan",
                       "Agent Daniel Cruz", "Agent Amy Foster", "Agent Robert Lang",
                       "Agent Jennifer Moss", "Agent William Tate", "Agent Laura Chen",
                       "Agent Christopher Bell", "Agent Nicole Grant", "Agent Brian Walsh",
                       "Agent Megan Riley", "Agent Kevin Shaw", "Agent Rachel Adams"],
            "domains": ["primerealty", "horizonre", "keystoneprops",
                        "blueskyrealty", "coastalhomes", "summitrealestate",
                        "goldcrestprops", "metroliving", "evergreenhomes",
                        "sapphirere", "atlasproperty", "lighthouserealty",
                        "crownproperties", "riverstonehomes", "platinumrealty"],
        },
    }

    niche_id = niche_config["id"]
    data = demo_data.get(niche_id, demo_data["dental"])
    leads = []

    for i in range(min(count, len(data["names"]))):
        has_website = random.random() > 0.15
        domain = f"{data['domains'][i]}.com"
        has_chatbot = random.random() > 0.75
        has_booking = random.random() > 0.6
        is_mobile = random.random() > 0.3
        rating = round(random.uniform(3.0, 5.0), 1)
        reviews = random.randint(5, 400)
        has_email = random.random() > 0.2
        has_social = random.random() > 0.3

        lead = {
            "business_name": data["names"][i],
            "owner_name": data["owners"][i] if random.random() > 0.3 else "",
            "email": f"info@{domain}" if has_email and has_website else "",
            "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}" if random.random() > 0.1 else "",
            "website": f"https://www.{domain}" if has_website else "",
            "address": f"{random.randint(100,9999)} {random.choice(['Main','Oak','Elm','Park','Broadway','Market'])} St",
            "city": location.split(",")[0].strip() if "," in location else location,
            "state": location.split(",")[1].strip() if "," in location else "",
            "country": "United States",
            "rating": rating,
            "review_count": reviews,
            "google_maps_url": f"https://maps.google.com/?q={data['names'][i].replace(' ', '+')}",
            "facebook": f"https://facebook.com/{data['domains'][i]}" if has_social else "",
            "instagram": f"https://instagram.com/{data['domains'][i]}" if has_social and random.random() > 0.4 else "",
            "twitter": "",
            "linkedin": f"https://linkedin.com/company/{data['domains'][i]}" if random.random() > 0.6 else "",
            "has_chatbot": 1 if has_chatbot else 0,
            "has_booking": 1 if has_booking else 0,
            "is_mobile_friendly": 1 if is_mobile else 0,
            "has_website": 1 if has_website else 0,
            "source": "demo",
            "enriched": 0,
        }
        leads.append(lead)

    return leads


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  ProspectAI - Lead Generator for CodeSlayer")
    print("="*50)
    print(f"\n  Dashboard: http://localhost:{Config.FLASK_PORT}")
    print(f"  API Docs:  http://localhost:{Config.FLASK_PORT}/api/status\n")

    status = Config.api_status()
    print("  API Status:")
    for key, val in status.items():
        icon = "[OK]" if val else "[--]"
        print(f"    {icon} {key}: {val}")
    print()
    
    import os
     
    port = int(os.environ.get("PORT" ,10000))
    app.run(host="0.0.0.0", port=port)
