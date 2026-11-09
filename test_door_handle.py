"""
Automated Integration and Verification Test for Door Handle Vision QC Pipeline & Active Learner.
"""

import os
import glob
import cv2

from core.pipeline import VisionQCPipeline
from core.active_learner import ActiveLearner

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DOOR_HANDLE_DIR = os.path.join(PROJECT_ROOT, "mock_data", "door_handles")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_door_handle_learning.db")
GOLDEN_PATH = os.path.join(DOOR_HANDLE_DIR, "golden_reference.png")


def run_door_handle_tests():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    print("=== 1. Initializing Door Handle Vision QC Pipeline ===")
    pipeline = VisionQCPipeline(mode="door_handle")
    golden_img = cv2.imread(GOLDEN_PATH)
    assert golden_img is not None, f"Could not read golden reference: {GOLDEN_PATH}"
    pipeline.load_golden_reference(golden_img, auto_align=True)

    learner = ActiveLearner(DB_PATH, pipeline)
    print("✔ Pipeline ready with Door Handle Golden Reference.")

    print("\n=== 2. Running Inspection on All Door Handle Samples ===")
    samples = sorted(glob.glob(os.path.join(DOOR_HANDLE_DIR, "sample_*.png")))
    results = {}

    for s_path in samples:
        name = os.path.basename(s_path)
        img = cv2.imread(s_path)
        out = pipeline.run(img)
        results[name] = out
        status_sym = "✔ OK " if out.is_ok else "✖ NOK"
        anomaly_str = f"{out.inspection.anomaly_score:.3f}" if out.inspection else "N/A"
        print(f"[{status_sym}] {name:28} | Decision: {out.final_decision:6} | Anomaly: {anomaly_str} | Time: {out.elapsed_ms:4.1f}ms | Reason: {out.reason}")

    # Assertions
    assert results["sample_ok_01.png"].is_ok is True, "sample_ok_01 should be OK"
    assert results["sample_ok_02.png"].is_ok is True, "sample_ok_02 should be OK"
    assert results["sample_nok_scratch.png"].is_ok is False, "sample_nok_scratch should be NOT OK (scratch)"
    assert results["sample_nok_stain.png"].is_ok is False, "sample_nok_stain should be NOT OK (stain)"
    assert results["sample_nok_blocked_hole.png"].is_ok is False, "sample_nok_blocked_hole should be NOT OK (blocked screw)"
    assert results["sample_nok_missing_hole.png"].is_ok is False, "sample_nok_missing_hole should be NOT OK (missing screw)"
    assert results["sample_nok_bent.png"].is_ok is False, "sample_nok_bent should be NOT OK (bent arm)"

    print("\n=== 3. Testing Active Learning on Door Handle ===")
    # Simulate an operator confirming sample_ok_03 variation (slight light variation)
    ok_sample = results["sample_ok_03.png"]
    learner.process_feedback(
        aligned_image=ok_sample.localization.aligned_image,
        model_decision=ok_sample.final_decision,
        operator_decision="OK",
        anomaly_score=ok_sample.inspection.anomaly_score if ok_sample.inspection else 0.05,
        notes="Operator confirmed acceptable brushed metal luster"
    )

    stats = learner.get_stats()
    print(f"Learner Stats -> Total: {stats.total_inspections}, Corrections: {stats.total_corrections}, OK Memory Bank: {len(pipeline.failure_detector.ok_memory_bank)}, Threshold: {stats.current_threshold}")
    assert stats.total_inspections == 1, "Expected 1 inspection record in DB"

    print("\n✅ ALL DOOR HANDLE TESTS PASSED WITH 100% SUCCESS!")


if __name__ == "__main__":
    run_door_handle_tests()
