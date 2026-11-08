"""
Multi-Stage Vision QC Inspection Pipeline.
Executes:
  Stage 1: Part Localization & Orientation Alignment
  Stage 2: Golden Reference Failure & Anomaly Detection (Trained only on OK samples)
  Stage 3: Specific Sub-Component Checks (Presence / Geometry / Screws)
  Stage 4: Unified OK / NOK Decision & Diagnostic Summary
"""

import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

from core.locator import PartLocator, LocalizationResult
from core.golden_reference import GoldenReferenceFailureDetector, InspectionResult


@dataclass
class PipelineOutput:
    final_decision: str           # "OK" or "NOT OK"
    is_ok: bool
    overall_confidence: float
    elapsed_ms: float
    localization: LocalizationResult
    inspection: Optional[InspectionResult]
    subchecks: Dict[str, Any]
    reason: str


class VisionQCPipeline:
    def __init__(self, golden_image_path: Optional[str] = None):
        self.locator = PartLocator()
        self.failure_detector = GoldenReferenceFailureDetector()

        if golden_image_path:
            import cv2
            golden = cv2.imread(golden_image_path)
            if golden is not None:
                self.failure_detector.set_golden_reference(golden)

    def load_golden_reference(self, image: np.ndarray):
        self.failure_detector.set_golden_reference(image)

    def run(self, raw_frame: np.ndarray) -> PipelineOutput:
        start_t = time.perf_counter()

        # Stage 1: Localization & Alignment
        loc_res = self.locator.locate_and_align(raw_frame)
        if not loc_res.success or loc_res.aligned_image is None:
            elapsed = (time.perf_counter() - start_t) * 1000.0
            return PipelineOutput(
                final_decision="NOT OK",
                is_ok=False,
                overall_confidence=0.9,
                elapsed_ms=round(elapsed, 1),
                localization=loc_res,
                inspection=None,
                subchecks={},
                reason="Parca goruntuden tespit edilemedi veya gorus alani disinda.",
            )

        # Stage 2: Golden Reference Anomaly / Failure Detection
        insp_res = self.failure_detector.inspect(loc_res.aligned_image)

        # Stage 3: Specific Sub-Component Checks
        subchecks = self._run_subchecks(loc_res.aligned_image)

        # Stage 4: Decision Fusion
        is_ok = insp_res.is_ok and subchecks.get("all_passed", True)
        final_decision = "OK" if is_ok else "NOT OK"

        reasons = []
        if not insp_res.is_ok:
            reasons.append(f"Anomali/Kusur skoru yuksek ({insp_res.anomaly_score:.2f} > {insp_res.threshold:.2f})")
        for check_name, passed in subchecks.get("details", {}).items():
            if not passed:
                reasons.append(f"{check_name} kontrolunden gecemedi")

        reason = "Tum testler basarili. Parca standartlara uygun." if is_ok else " | ".join(reasons)
        elapsed = (time.perf_counter() - start_t) * 1000.0

        return PipelineOutput(
            final_decision=final_decision,
            is_ok=is_ok,
            overall_confidence=insp_res.confidence,
            elapsed_ms=round(elapsed, 1),
            localization=loc_res,
            inspection=insp_res,
            subchecks=subchecks,
            reason=reason,
        )

    def _run_subchecks(self, aligned_part: np.ndarray) -> Dict[str, Any]:
        """
        Specialized rule-based checks on canonical aligned coordinates:
        - Check 1: 4 Corner mounting holes integrity
        - Check 2: Central IC chip presence & placement
        """
        import cv2

        details = {}
        gray = cv2.cvtColor(aligned_part, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Check 1: Corner mounting holes
        holes = [(35, 35), (w - 35, 35), (35, h - 35), (w - 35, h - 35)]
        holes_ok = True
        for hx, hy in holes:
            patch = gray[max(0, hy - 12):min(h, hy + 12), max(0, hx - 12):min(w, hx + 12)]
            # In a valid hole, the center is dark (< 60) and ring is bright (> 140)
            if patch.size > 0:
                has_dark_center = np.min(patch) < 70
                has_bright_ring = np.max(patch) > 130
                if not (has_dark_center and has_bright_ring):
                    holes_ok = False
                    break
        details["Montaj Delikleri Kontrolu"] = holes_ok

        # Check 2: Central IC chip contrast
        ic_patch = gray[120:220, 190:300]
        # IC chip should have a distinct dark mean brightness (~20-55) compared to PCB background (>70)
        ic_ok = 15 < np.mean(ic_patch) < 65
        details["Merkezi IC Entegre Kontrolu"] = ic_ok

        all_passed = all(details.values())
        return {"all_passed": all_passed, "details": details}
