"""
Golden Reference Failure Detector.
Trained on 'OK' reference samples to detect deviations, anomalies, and failures:
- Morphological tolerance banding for micro-vibration invariance
- Multi-channel color & edge anomaly extraction
- Pixel-level defect heatmap generation and defect localization (BBoxes)
- Memory bank adaptation for learning from operator approvals
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import cv2
import numpy as np


@dataclass
class DefectBBox:
    x: int
    y: int
    w: int
    h: int
    severity: float
    defect_type: str


@dataclass
class InspectionResult:
    is_ok: bool
    anomaly_score: float         # 0.0 to 1.0
    threshold: float
    confidence: float
    defect_regions: List[DefectBBox] = field(default_factory=list)
    heatmap: np.ndarray = field(default_factory=lambda: np.zeros((10, 10, 3), dtype=np.uint8))
    composite_view: np.ndarray = field(default_factory=lambda: np.zeros((10, 10, 3), dtype=np.uint8))
    summary: str = ""


class GoldenReferenceFailureDetector:
    def __init__(self, default_threshold: float = 0.15):
        self.threshold = default_threshold
        self.golden_references: List[np.ndarray] = []
        self.ok_memory_bank: List[np.ndarray] = []
        self.dilated_ref: Optional[np.ndarray] = None
        self.eroded_ref: Optional[np.ndarray] = None
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    def set_golden_reference(self, reference_img: np.ndarray):
        self.golden_references = [reference_img.copy()]
        self.dilated_ref = cv2.dilate(reference_img, self.kernel)
        self.eroded_ref = cv2.erode(reference_img, self.kernel)
        self.learn_ok_variation(reference_img)

    def learn_ok_variation(self, ok_img: np.ndarray):
        """
        Active Learning: Incorporates confirmed OK sample to expand allowable variations.
        Updates morphological bounds to ensure this variation never triggers false alarm.
        """
        self.ok_memory_bank.append(ok_img.copy())
        if self.dilated_ref is not None:
            dil_sample = cv2.dilate(ok_img, self.kernel)
            ero_sample = cv2.erode(ok_img, self.kernel)
            self.dilated_ref = np.maximum(self.dilated_ref, dil_sample)
            self.eroded_ref = np.minimum(self.eroded_ref, ero_sample)

        if len(self.ok_memory_bank) > 30:
            self.ok_memory_bank.pop(0)

    def inspect(self, aligned_part: np.ndarray) -> InspectionResult:
        if not self.golden_references or self.dilated_ref is None:
            raise ValueError("No golden reference loaded. Please load or teach an OK sample first.")

        ref = self.golden_references[0]
        h, w = ref.shape[:2]
        test = cv2.resize(aligned_part, (w, h))

        # Morphological tolerance band difference
        over = np.maximum(0, test.astype(np.int16) - self.dilated_ref.astype(np.int16))
        under = np.maximum(0, self.eroded_ref.astype(np.int16) - test.astype(np.int16))
        band_diff = np.maximum(over, under).astype(np.uint8)

        # Max difference across color channels (captures color stains, dark holes, bright scratches)
        diff_max_ch = np.max(band_diff, axis=2)

        # Mask of defect pixels (diff > 25 on 0-255 scale)
        defect_mask = (diff_max_ch > 25).astype(np.uint8) * 255

        # Morphological clean up on defect mask (remove single noise speckles)
        clean_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        defect_clean = cv2.morphologyEx(defect_mask, cv2.MORPH_OPEN, clean_kernel)

        defect_pixel_count = np.sum(defect_clean > 0)
        # Anomaly score normalized: 0 pixels -> 0.0, 500+ pixels -> 1.0
        anomaly_score = float(np.clip(defect_pixel_count / 400.0, 0.0, 1.0))

        is_ok = anomaly_score < self.threshold
        dist = abs(anomaly_score - self.threshold)
        confidence = float(np.clip(0.60 + (dist / (self.threshold * 2.0)) * 0.39, 0.60, 0.99))

        # Defect Regions & BBoxes
        contours, _ = cv2.findContours(defect_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        defect_regions: List[DefectBBox] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= 30:  # Minimum meaningful defect cluster
                bx, by, bw, bh = cv2.boundingRect(cnt)
                crop_diff = diff_max_ch[by:by + bh, bx:bx + bw]
                severity = float(np.max(crop_diff) / 255.0)
                dtype = "Surface Scratch / Crack" if (bw > 2.2 * bh or bh > 2.2 * bw) else "Defect / Anomaly"
                defect_regions.append(DefectBBox(x=bx, y=by, w=bw, h=bh, severity=round(severity, 2), defect_type=dtype))

        # Visual Heatmap
        heatmap_gray = cv2.GaussianBlur(diff_max_ch, (15, 15), 0)
        heatmap_norm = np.clip((heatmap_gray.astype(np.float32) / 60.0) * 255, 0, 255).astype(np.uint8)
        heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)

        # Composite View
        composite = cv2.addWeighted(test, 0.70, heatmap_color, 0.30, 0)
        for d in defect_regions:
            cv2.rectangle(composite, (d.x, d.y), (d.x + d.w, d.y + d.h), (0, 0, 255), 2)
            cv2.putText(
                composite,
                f"{d.defect_type}",
                (d.x, max(15, d.y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )

        summary = (
            "Tum alanlar 'OK' referansi ile uyumlu."
            if is_ok
            else f"FAILURE: {len(defect_regions)} bolgede OK sablonundan sapma tespit edildi ({defect_pixel_count} kusurlu piksel)."
        )

        return InspectionResult(
            is_ok=is_ok,
            anomaly_score=round(anomaly_score, 3),
            threshold=round(self.threshold, 3),
            confidence=round(confidence, 2),
            defect_regions=defect_regions,
            heatmap=heatmap_color,
            composite_view=composite,
            summary=summary,
        )
