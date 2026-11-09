"""
Active Learning & Continual Adaptation Engine.
Enables the system to learn directly from operator decisions and feedback (Human-in-the-Loop).
- If an operator corrects a False Reject (marked OK): expands the Golden OK Memory Bank.
- If an operator corrects a False Accept (marked NOT OK): adapts the sensitivity threshold and archives the hard defect.
- Maintains persistent learning history and metrics in SQLite.
"""

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np


@dataclass
class LearningStats:
    total_inspections: int
    total_corrections: int
    learned_ok_count: int
    hard_defects_count: int
    current_threshold: float
    accuracy_rate: float


class ActiveLearner:
    def __init__(self, db_path: str, pipeline):
        self.db_path = db_path
        self.pipeline = pipeline
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inspection_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    model_decision TEXT,
                    operator_decision TEXT,
                    is_correction INTEGER,
                    anomaly_score REAL,
                    threshold REAL,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    event_type TEXT,
                    old_threshold REAL,
                    new_threshold REAL,
                    details TEXT
                )
            """)
            conn.commit()

    def process_feedback(
        self,
        aligned_image: np.ndarray,
        model_decision: str,
        operator_decision: str,
        anomaly_score: float,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Processes human feedback to update the model.
        Returns the learning impact summary.
        """
        is_correction = 1 if model_decision != operator_decision else 0
        old_threshold = self.pipeline.failure_detector.threshold
        new_threshold = old_threshold
        event_type = "CONFIRMATION"

        if is_correction:
            if operator_decision == "OK":
                # Model said NOT OK, but operator says OK (False Alarm)
                # Action: Teach model that this variation is acceptable
                event_type = "LEARN_OK_VARIATION"
                self.pipeline.failure_detector.learn_ok_variation(aligned_image)

                # Relax threshold slightly
                if anomaly_score > old_threshold and anomaly_score < old_threshold * 1.5:
                    new_threshold = min(0.30, old_threshold + 0.015)
                    self.pipeline.failure_detector.threshold = new_threshold

            elif operator_decision == "NOT OK":
                # Model said OK, but operator found a defect (False Accept)
                # Action: Increase model sensitivity
                event_type = "TIGHTEN_DEFECT_SENSITIVITY"
                new_threshold = max(0.08, min(old_threshold - 0.015, anomaly_score * 0.90))
                self.pipeline.failure_detector.threshold = new_threshold

        # Record in DB
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspection_history (timestamp, model_decision, operator_decision, is_correction, anomaly_score, threshold, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, model_decision, operator_decision, is_correction, anomaly_score, new_threshold, notes))

            if is_correction:
                cursor.execute("""
                    INSERT INTO learning_events (timestamp, event_type, old_threshold, new_threshold, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (now, event_type, old_threshold, new_threshold, f"Operator override: {model_decision} -> {operator_decision}"))
            conn.commit()

        return {
            "is_correction": bool(is_correction),
            "event_type": event_type,
            "old_threshold": round(old_threshold, 4),
            "new_threshold": round(new_threshold, 4),
            "ok_bank_size": len(self.pipeline.failure_detector.ok_memory_bank),
            "message": self._format_learning_message(event_type, old_threshold, new_threshold)
        }

    def _format_learning_message(self, event_type: str, old_th: float, new_th: float) -> str:
        if event_type == "LEARN_OK_VARIATION":
            return f"Yeni 'OK' örneği öğrenildi. Benzer parça varyasyonları artık tolerans dahilinde kabul edilecek (Eşik: {old_th:.2f} -> {new_th:.2f})."
        elif event_type == "TIGHTEN_DEFECT_SENSITIVITY":
            return f"Gözden kaçan kusur öğrenildi. Model hassasiyeti artırıldı (Eşik: {old_th:.2f} -> {new_th:.2f})."
        return "Karar onaylandı, istatistiklere eklendi."

    def get_stats(self) -> LearningStats:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(is_correction) FROM inspection_history")
            row = cursor.fetchone()
            total = row[0] or 0
            corrections = row[1] or 0

            cursor.execute("SELECT COUNT(*) FROM learning_events WHERE event_type = 'LEARN_OK_VARIATION'")
            learned_ok = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM learning_events WHERE event_type = 'TIGHTEN_DEFECT_SENSITIVITY'")
            hard_defects = cursor.fetchone()[0] or 0

        acc = ((total - corrections) / total * 100.0) if total > 0 else 100.0
        return LearningStats(
            total_inspections=total,
            total_corrections=corrections,
            learned_ok_count=learned_ok,
            hard_defects_count=hard_defects,
            current_threshold=round(self.pipeline.failure_detector.threshold, 4),
            accuracy_rate=round(acc, 1)
        )
