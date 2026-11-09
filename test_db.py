"""
Test SQLite Inspection Database Logging & CSV Export.
"""

import os
from core.database import InspectionDatabase

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_qc_inspections.db")
CSV_PATH = os.path.join(PROJECT_ROOT, "data", "test_report.csv")


def test_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    db = InspectionDatabase(DB_PATH)
    print("✔ DB initialized at", DB_PATH)

    # 1. Log OK inspection
    id1 = db.log_inspection(
        sample_name="sample_ok_01.png",
        decision="OK",
        anomaly_score=0.012,
        threshold=0.15,
        confidence=0.98,
        defect_count=0,
        defect_summary="Tum testler basarili",
        elapsed_ms=4.1,
        source="ETHERNET_IP_192.168.1.100"
    )
    assert id1 == 1, "Expected ID 1"

    # 2. Log NOK inspection
    id2 = db.log_inspection(
        sample_name="sample_nok_scratch.png",
        decision="NOT OK",
        anomaly_score=0.450,
        threshold=0.15,
        confidence=0.95,
        defect_count=2,
        defect_summary="Cizik kusuru tespit edildi",
        elapsed_ms=4.8,
        source="ETHERNET_IP_192.168.1.100"
    )
    assert id2 == 2, "Expected ID 2"

    # 3. Update with operator override
    db.update_feedback(
        inspection_id=id2,
        sample_name="sample_nok_scratch.png",
        model_decision="NOT OK",
        operator_decision="OK",
        notes="Operator tolerans dahilinde onayladi"
    )

    # 4. Query recent
    rows = db.get_recent_inspections()
    assert len(rows) == 2, "Expected 2 rows"
    print(f"✔ Retrieved {len(rows)} inspection rows from DB")
    for r in rows:
        print(f"  [{r['created_at']}] ID={r['id']} | {r['sample_name']} | Decision={r['decision']} | Override={r['operator_override']} ({r['operator_decision']})")

    # 5. Stats
    stats = db.get_statistics()
    print("✔ Statistics:", stats)
    assert stats["total"] == 2
    assert stats["overrides"] == 1

    # 6. CSV Export
    count = db.export_csv(CSV_PATH)
    assert count == 2, "Expected 2 exported rows"
    assert os.path.exists(CSV_PATH), "CSV file should exist"
    print(f"✔ Successfully exported {count} records to CSV ({CSV_PATH})")

    print("\n✅ DATABASE VERIFICATION TESTS PASSED 100%!")


if __name__ == "__main__":
    test_db()
