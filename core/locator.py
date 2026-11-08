"""
Part Localization and Alignment Engine.
Detects industrial components in camera frames, extracts center, oriented bounding box (OBB)
and rotation angle, then applies rigid Euclidean transformation (preserving scale=1.0)
into canonical aligned space for precise golden inspection.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np


@dataclass
class LocalizationResult:
    success: bool
    aligned_image: Optional[np.ndarray]
    bbox_corners: Optional[np.ndarray]
    center: Tuple[int, int]
    angle: float
    confidence: float
    debug_frame: np.ndarray


class PartLocator:
    def __init__(self, target_width: int = 500, target_height: int = 350, min_area: float = 50000.0):
        self.target_width = target_width
        self.target_height = target_height
        self.min_area = min_area

    def locate_and_align(self, frame: np.ndarray) -> LocalizationResult:
        debug = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Multi-threshold segmentation
        candidates = []
        for th_val in [22, 30]:
            _, bin_img = cv2.threshold(gray, th_val, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            cleaned = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel)
            cnts, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if area >= self.min_area:
                    candidates.append((area, c))

        if not candidates:
            return LocalizationResult(
                success=False,
                aligned_image=None,
                bbox_corners=None,
                center=(0, 0),
                angle=0.0,
                confidence=0.0,
                debug_frame=debug,
            )

        best_area, best_cnt = max(candidates, key=lambda x: x[0])
        rect = cv2.minAreaRect(best_cnt)
        (cx, cy), (rw, rh), angle = rect
        box = cv2.boxPoints(rect)
        box = np.int32(box)

        # Canonical horizontal orientation
        if rw < rh:
            rw, rh = rh, rw
            angle += 90.0

        # Rigid Euclidean Transform (Translation + Rotation without non-rigid scaling)
        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
        M[0, 2] += (self.target_width / 2.0 - cx)
        M[1, 2] += (self.target_height / 2.0 - cy)

        aligned = cv2.warpAffine(
            frame, M, (self.target_width, self.target_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(15, 15, 15)
        )

        # Overlays
        cv2.drawContours(debug, [box], 0, (0, 255, 120), 2)
        cv2.circle(debug, (int(cx), int(cy)), 5, (0, 0, 255), -1)
        cv2.putText(
            debug,
            f"Parca: ({int(cx)},{int(cy)}) | Aci: {angle:.1f} deg",
            (max(10, int(box[0][0])), max(25, int(box[0][1]) - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 120),
            2,
            cv2.LINE_AA,
        )

        confidence = float(min(1.0, best_area / (self.target_width * self.target_height * 0.95)))

        return LocalizationResult(
            success=True,
            aligned_image=aligned,
            bbox_corners=box,
            center=(int(cx), int(cy)),
            angle=float(angle),
            confidence=round(confidence, 3),
            debug_frame=debug,
        )
