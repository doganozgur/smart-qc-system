"""
Automated Integration and Verification Test for Vision QC Pipeline & Active Learner.
"""

import os
import glob
import cv2

from core.pipeline import VisionQCPipeline
from core.active_learner import ActiveLearner

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.join(PROJECT_ROOT, "mock_data")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_learning.db")
GOLDEN_PATH = os.path.join(MOCK_DIR, "golden_reference.png")


def run_tests():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    print("=== 1. Vision Pipeline Initializing ===")
    pipeline = VisionQCPipeline(GOLDEN_PATH, mode="pcb")
    learner = ActiveLearner(DB_PATH, pipeline)
    print("Pipeline ready with golden reference.")

    print("\n=== 2. Running Inspection on All Samples ===")
    samples = sorted(glob.glob(os.path.join(MOCK_DIR, "sample_*.png")))
    results = {}

    for s_path in samples:
        name = os.path.basename(s_path)
        img = cv2.imread(s_path)
        out = pipeline.run(img)
        results[name] = out
        status_sym = "✔ OK" if out.is_ok else "✖ NOK"
        anomaly_str = f"{out.inspection.anomaly_score:.3f}" if out.inspection else "N/A"
        print(f"[{status_sym}] {name:25} | Decision: {out.final_decision:6} | Anomaly: {anomaly_str} | Time: {out.elapsed_ms:.1f}ms | Reason: {out.reason}")

    # Assertions
    assert results["sample_ok_01.png"].is_ok is True, "sample_ok_01 should be OK"
    assert results["sample_ok_02.png"].is_ok is True, "sample_ok_02 should be OK"
    assert results["sample_nok_scratch.png"].is_ok is False, "sample_nok_scratch should be NOT OK"
    assert results["sample_nok_missing.png"].is_ok is False, "sample_nok_missing should be NOT OK"
    assert results["sample_nok_stain.png"].is_ok is False, "sample_nok_stain should be NOT OK"

    print("\n=== 3. Testing Active Learning & Operator Feedback ===")
    # Simulate an operator confirming an OK sample
    ok_out = results["sample_ok_01.png"]
    learner.process_feedback(
        aligned_image=ok_out.localization.aligned_image,
        model_decision="OK",
        operator_decision="OK",
        anomaly_score=ok_out.inspection.anomaly_score,
        notes="Standard verification test"
    )

    # Simulate an operator correcting a sample (teaching a new acceptable variation)
    learner.process_feedback(
        aligned_image=results["sample_ok_03.png"].localization.aligned_image,
        model_decision="NOT OK",
        operator_decision="OK",
        anomaly_score=0.16,
        notes="Operator teaches new acceptable tolerance"
    )

    stats = learner.get_stats()
    print(f"Learner Stats -> Total: {stats.total_inspections}, Corrections: {stats.total_corrections}, OK Memory Bank: {len(pipeline.failure_detector.ok_memory_bank)}, Threshold: {stats.current_threshold}")
    assert stats.total_inspections == 2, "Expected 2 inspections recorded in DB"
    assert stats.learned_ok_count == 1, "Expected 1 learned OK event"

    print("\n✅ ALL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
