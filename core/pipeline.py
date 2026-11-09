"""
Multi-Stage Vision QC Inspection Pipeline.
Executes:
  Stage 1: Part Localization & Orientation Alignment (OBB + Canonical Space)
  Stage 2: Golden Reference Failure & Anomaly Detection (Tolerances + Defect Heatmap)
  Stage 3: Specific Sub-Component Checks (Door Handle: Holes, Spindle, Curvature | PCB: Holes, IC)
  Stage 4: Unified OK / NOK Decision & Diagnostic Summary
"""

import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
import cv2
import numpy as np

from core.locator import PartLocator, LocalizationResult
from core.door_handle_locator import DoorHandleLocator, HandleLocalizationResult
from core.door_handle_inspector import DoorHandleSubInspector
from core.golden_reference import GoldenReferenceFailureDetector, InspectionResult


@dataclass
class PipelineOutput:
    final_decision: str           # "OK" or "NOT OK"
    is_ok: bool
    overall_confidence: float
    elapsed_ms: float
    localization: Any             # LocalizationResult or HandleLocalizationResult
    inspection: Optional[InspectionResult]
    subchecks: Dict[str, Any]
    reason: str


class VisionQCPipeline:
    def __init__(self, golden_image_path: Optional[str] = None, mode: str = "door_handle"):
        self.mode = mode

        if self.mode == "door_handle":
            self.locator = DoorHandleLocator(target_width=600, target_height=300)
            self.sub_inspector = DoorHandleSubInspector(target_width=600, target_height=300)
        else:
            self.locator = PartLocator(target_width=500, target_height=350)
            self.sub_inspector = None

        self.failure_detector = GoldenReferenceFailureDetector(default_threshold=0.15)

        if golden_image_path:
            golden = cv2.imread(golden_image_path)
            if golden is not None:
                self.load_golden_reference(golden, auto_align=True)

    def set_mode(self, mode: str):
        """Switches inspection mode between 'door_handle' and 'pcb'."""
        self.mode = mode
        if self.mode == "door_handle":
            self.locator = DoorHandleLocator(target_width=600, target_height=300)
            self.sub_inspector = DoorHandleSubInspector(target_width=600, target_height=300)
        else:
            self.locator = PartLocator(target_width=500, target_height=350)
            self.sub_inspector = None

    def load_golden_reference(self, image: np.ndarray, auto_align: bool = True):
        """
        Loads a golden reference image. If auto_align is True, automatically
        runs localization so the user can upload any raw image of the part.
        """
        ref_to_use = image
        if auto_align:
            tw = getattr(self.locator, "target_width", 600)
            th = getattr(self.locator, "target_height", 300)
            if image.shape[1] != tw or image.shape[0] != th:
                loc = self.locator.locate_and_align(image)
                if loc.success and loc.aligned_image is not None:
                    ref_to_use = loc.aligned_image
                else:
                    ref_to_use = cv2.resize(image, (tw, th))

        part_mask = None
        if self.mode == "door_handle":
            part_mask = (cv2.cvtColor(ref_to_use, cv2.COLOR_BGR2GRAY) > 40).astype(np.uint8)

        self.failure_detector.set_golden_reference(ref_to_use, part_mask=part_mask)

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
                reason="Parça görüntüden tespit edilemedi veya görüş alanı dışında.",
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
            reasons.append(f"Anomali/Kusur skoru yüksek ({insp_res.anomaly_score:.2f} > {insp_res.threshold:.2f})")
        for check_name, passed in subchecks.get("details", {}).items():
            if not passed:
                reasons.append(f"{check_name} kontrolünden geçemedi")

        reason = "Tüm testler başarılı. Parça standartlara uygun." if is_ok else " | ".join(reasons)
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
        """Runs subchecks according to current inspection mode."""
        if self.mode == "door_handle" and self.sub_inspector is not None:
            return self.sub_inspector.run_subchecks(aligned_part)

        # Legacy PCB checks
        details = {}
        gray = cv2.cvtColor(aligned_part, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        holes = [(35, 35), (w - 35, 35), (35, h - 35), (w - 35, h - 35)]
        holes_ok = True
        for hx, hy in holes:
            patch = gray[max(0, hy - 12):min(h, hy + 12), max(0, hx - 12):min(w, hx + 12)]
            if patch.size > 0:
                has_dark_center = np.min(patch) < 70
                has_bright_ring = np.max(patch) > 130
                if not (has_dark_center and has_bright_ring):
                    holes_ok = False
                    break
        details["Montaj Delikleri Kontrolu"] = holes_ok

        ic_patch = gray[120:220, 190:300]
        ic_ok = 15 < np.mean(ic_patch) < 65
        details["Merkezi IC Entegre Kontrolu"] = ic_ok

        all_passed = all(details.values())
        return {"all_passed": all_passed, "details": details}
