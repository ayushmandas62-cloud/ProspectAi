"""
Lead Scorer — Ranks leads for CodeSlayer outreach.
Higher score = hotter lead = more likely to need your services.
"""


class LeadScorer:
    WEIGHTS = {
        "no_website": 30,
        "has_outdated_site": 20,
        "no_chatbot": 15,
        "no_booking": 15,
        "has_email": 10,
        "has_phone": 5,
        "high_rating": 10,
        "many_reviews": 10,
        "social_active": 5,
        "not_mobile_friendly": 10,
    }

    def score(self, lead):
        points = 0
        reasons = []

        # NO website = HOTTEST lead
        if not lead.get("website") and not lead.get("has_website"):
            points += self.WEIGHTS["no_website"]
            reasons.append("No website — desperately needs one")
        else:
            # Website exists — check quality
            if not lead.get("is_mobile_friendly"):
                points += self.WEIGHTS["not_mobile_friendly"]
                reasons.append("Website not mobile-friendly")

            if not lead.get("has_chatbot"):
                points += self.WEIGHTS["no_chatbot"]
                reasons.append("No chatbot on website")

            if not lead.get("has_booking"):
                points += self.WEIGHTS["no_booking"]
                reasons.append("No online booking system")

        # Contact availability
        if lead.get("email"):
            points += self.WEIGHTS["has_email"]
            reasons.append("Email available for outreach")

        if lead.get("phone"):
            points += self.WEIGHTS["has_phone"]
            reasons.append("Phone available for outreach")

        # Business quality indicators
        rating = float(lead.get("rating", 0))
        if rating >= 4.0:
            points += self.WEIGHTS["high_rating"]
            reasons.append(f"High rating ({rating}★)")

        reviews = int(lead.get("review_count", 0))
        if reviews >= 50:
            points += self.WEIGHTS["many_reviews"]
            reasons.append(f"Active business ({reviews} reviews)")

        # Social media presence
        has_social = any([
            lead.get("facebook"), lead.get("instagram"),
            lead.get("twitter"), lead.get("linkedin")
        ])
        if has_social:
            points += self.WEIGHTS["social_active"]
            reasons.append("Social media presence")

        # Determine label
        if points >= 70:
            label = "hot"
        elif points >= 40:
            label = "warm"
        else:
            label = "cold"

        return {
            "score": min(points, 100),
            "score_label": label,
            "reasons": reasons,
        }
