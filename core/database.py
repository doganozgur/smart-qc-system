"""
Comprehensive SQLite Inspection Database Manager.
Logs every inspection event with timestamp, sample name, camera source,
OK/NOK decision, anomaly score, defect details, and operator overrides.
"""

import os
import sqlite3
import datetime
from typing import List, Dict, Any, Optional


class InspectionDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT,
                    sample_name TEXT,
                    decision TEXT NOT NULL,
                    anomaly_score REAL,
                    threshold REAL,
                    confidence REAL,
                    defect_count INTEGER DEFAULT 0,
                    defect_summary TEXT,
                    elapsed_ms REAL,
                    operator_override INTEGER DEFAULT 0,
                    operator_decision TEXT,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision ON inspections(decision);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON inspections(created_at);
            """)
            conn.commit()

    def log_inspection(
        self,
        sample_name: str,
        decision: str,
        anomaly_score: float,
        threshold: float,
        confidence: float,
        defect_count: int,
        defect_summary: str,
        elapsed_ms: float,
        source: str = "ETHERNET_CAMERA",
        notes: str = ""
    ) -> int:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspections (
                    created_at, source, sample_name, decision, anomaly_score,
                    threshold, confidence, defect_count, defect_summary,
                    elapsed_ms, operator_override, operator_decision, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                now_str, source, sample_name, decision, anomaly_score,
                threshold, confidence, defect_count, defect_summary,
                elapsed_ms, decision, notes
            ))
            conn.commit()
            return cursor.lastrowid

    def update_feedback(
        self,
        inspection_id: Optional[int],
        sample_name: str,
        model_decision: str,
        operator_decision: str,
        notes: str = ""
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            is_override = 1 if model_decision != operator_decision else 0
            if inspection_id:
                cursor.execute("""
                    UPDATE inspections
                    SET operator_override = ?, operator_decision = ?, notes = ?
                    WHERE id = ?
                """, (is_override, operator_decision, notes, inspection_id))
            else:
                # Update latest inspection matching sample_name
                cursor.execute("""
                    UPDATE inspections
                    SET operator_override = ?, operator_decision = ?, notes = ?
                    WHERE id = (
                        SELECT id FROM inspections
                        WHERE sample_name = ?
                        ORDER BY id DESC LIMIT 1
                    )
                """, (is_override, operator_decision, notes, sample_name))
            conn.commit()

    def get_recent_inspections(self, limit: int = 150, filter_status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if filter_status and filter_status != "ALL":
                cursor.execute("""
                    SELECT * FROM inspections
                    WHERE decision = ?
                    ORDER BY id DESC LIMIT ?
                """, (filter_status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM inspections
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_statistics(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inspections")
            total = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE decision = 'OK'")
            ok_count = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE decision = 'NOT OK'")
            nok_count = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE operator_override = 1")
            overrides = cursor.fetchone()[0] or 0

            acc = round(((total - overrides) / total * 100.0), 1) if total > 0 else 100.0

            return {
                "total": total,
                "ok_count": ok_count,
                "nok_count": nok_count,
                "overrides": overrides,
                "accuracy_pct": acc
            }

    def export_csv(self, target_csv_path: str):
        import csv
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspections ORDER BY id ASC")
            rows = cursor.fetchall()
            if not rows:
                return 0
            field_names = rows[0].keys()
            with open(target_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(field_names)
                for r in rows:
                    writer.writerow(list(r))
            return len(rows)
