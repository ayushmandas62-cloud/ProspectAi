"""
ProspectAI Database Layer — SQLite
"""
import sqlite3
import os
from datetime import datetime


class Database:
    def __init__(self, db_path):
    dir_name = os.path.dirname(db_path) if dir_name:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                owner_name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                website TEXT DEFAULT '',
                address TEXT DEFAULT '',
                city TEXT DEFAULT '',
                state TEXT DEFAULT '',
                country TEXT DEFAULT '',
                niche TEXT DEFAULT '',
                rating REAL DEFAULT 0,
                review_count INTEGER DEFAULT 0,
                google_maps_url TEXT DEFAULT '',
                facebook TEXT DEFAULT '',
                instagram TEXT DEFAULT '',
                twitter TEXT DEFAULT '',
                linkedin TEXT DEFAULT '',
                has_chatbot INTEGER DEFAULT 0,
                has_booking INTEGER DEFAULT 0,
                is_mobile_friendly INTEGER DEFAULT 0,
                has_website INTEGER DEFAULT 1,
                score INTEGER DEFAULT 0,
                score_label TEXT DEFAULT 'cold',
                source TEXT DEFAULT 'google_maps',
                enriched INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche TEXT,
                location TEXT,
                results_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def insert_lead(self, lead_data):
        conn = self._get_conn()
        cursor = conn.cursor()

        # Check for duplicate by business name + city
        existing = cursor.execute(
            "SELECT id FROM leads WHERE business_name = ? AND city = ?",
            (lead_data.get("business_name", ""), lead_data.get("city", ""))
        ).fetchone()

        if existing:
            return {"status": "duplicate", "id": existing["id"]}

        columns = []
        values = []
        placeholders = []

        valid_columns = [
            "business_name", "owner_name", "email", "phone", "website",
            "address", "city", "state", "country", "niche", "rating",
            "review_count", "google_maps_url", "facebook", "instagram",
            "twitter", "linkedin", "has_chatbot", "has_booking",
            "is_mobile_friendly", "has_website", "score", "score_label",
            "source", "enriched", "notes"
        ]

        for col in valid_columns:
            if col in lead_data:
                columns.append(col)
                values.append(lead_data[col])
                placeholders.append("?")

        sql = f"INSERT INTO leads ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql, values)
        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"status": "created", "id": lead_id}

    def get_leads(self, filters=None):
        conn = self._get_conn()
        query = "SELECT * FROM leads"
        params = []
        conditions = []

        if filters:
            if filters.get("niche"):
                conditions.append("niche = ?")
                params.append(filters["niche"])
            if filters.get("city"):
                conditions.append("city LIKE ?")
                params.append(f"%{filters['city']}%")
            if filters.get("score_label"):
                conditions.append("score_label = ?")
                params.append(filters["score_label"])
            if filters.get("min_score"):
                conditions.append("score >= ?")
                params.append(int(filters["min_score"]))
            if filters.get("source"):
                conditions.append("source = ?")
                params.append(filters["source"])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY score DESC, created_at DESC"

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_lead(self, lead_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_lead(self, lead_id, data):
        conn = self._get_conn()
        sets = []
        values = []
        for key, val in data.items():
            if key != "id":
                sets.append(f"{key} = ?")
                values.append(val)
        sets.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(lead_id)

        conn.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def delete_lead(self, lead_id):
        conn = self._get_conn()
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()

    def get_stats(self):
        conn = self._get_conn()
        stats = {
            "total": conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"],
            "hot": conn.execute("SELECT COUNT(*) as c FROM leads WHERE score_label = 'hot'").fetchone()["c"],
            "warm": conn.execute("SELECT COUNT(*) as c FROM leads WHERE score_label = 'warm'").fetchone()["c"],
            "cold": conn.execute("SELECT COUNT(*) as c FROM leads WHERE score_label = 'cold'").fetchone()["c"],
            "enriched": conn.execute("SELECT COUNT(*) as c FROM leads WHERE enriched = 1").fetchone()["c"],
            "with_email": conn.execute("SELECT COUNT(*) as c FROM leads WHERE email != ''").fetchone()["c"],
            "with_phone": conn.execute("SELECT COUNT(*) as c FROM leads WHERE phone != ''").fetchone()["c"],
            "today": conn.execute(
                "SELECT COUNT(*) as c FROM leads WHERE DATE(created_at) = DATE('now')"
            ).fetchone()["c"],
        }
        conn.close()
        return stats

    def log_search(self, niche, location, results_count):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO search_history (niche, location, results_count) VALUES (?, ?, ?)",
            (niche, location, results_count)
        )
        conn.commit()
        conn.close()

    def clear_all(self):
        conn = self._get_conn()
        conn.execute("DELETE FROM leads")
        conn.commit()
        conn.close()
