"""
Door Handle Localization and Canonical Alignment Engine.
Detects industrial door handles (lever + rosette), finds orientation via PCA,
ensures rosette is canonically on the left and lever arm on the right,
and rigidly transforms into a canonical 600x300 bounding workspace.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np


@dataclass
class HandleLocalizationResult:
    success: bool
    aligned_image: Optional[np.ndarray]
    bbox_corners: Optional[np.ndarray]
    center: Tuple[int, int]
    angle: float
    confidence: float
    debug_frame: np.ndarray


class DoorHandleLocator:
    def __init__(self, target_width: int = 600, target_height: int = 300, min_area: float = 20000.0):
        self.target_width = target_width
        self.target_height = target_height
        self.min_area = min_area

    def locate_and_align(self, frame: np.ndarray) -> HandleLocalizationResult:
        debug = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 45, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        cnts, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_cnts = [c for c in cnts if cv2.contourArea(c) >= self.min_area]

        if not valid_cnts:
            return HandleLocalizationResult(
                success=False,
                aligned_image=None,
                bbox_corners=None,
                center=(0, 0),
                angle=0.0,
                confidence=0.0,
                debug_frame=debug,
            )

        best_cnt = max(valid_cnts, key=cv2.contourArea)
        area = cv2.contourArea(best_cnt)

        # 1. Orientation via PCA (Principal Component Analysis on contour points)
        pts = best_cnt.reshape(-1, 2).astype(np.float32)
        mean, eigenvectors = cv2.PCACompute(pts, mean=np.empty((0)))
        cx, cy = mean[0]
        pca_angle = np.degrees(np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0]))

        # Oriented bounding box for visualization
        rect = cv2.minAreaRect(best_cnt)
        box = cv2.boxPoints(rect)
        box = np.int32(box)

        # 2. Euclidean Transform to Canonical Space
        M = cv2.getRotationMatrix2D((float(cx), float(cy)), float(pca_angle), 1.0)
        M[0, 2] += (self.target_width / 2.0 - cx)
        M[1, 2] += (self.target_height / 2.0 - cy)

        aligned = cv2.warpAffine(
            frame, M, (self.target_width, self.target_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(28, 30, 32)
        )

        # 3. Rosette Orientation Check (Ensure rosette is on the left)
        # Rosette has higher circular mass than the slender lever arm tip
        al_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        left_mass = np.sum(al_gray[:, :self.target_width // 2] > 45)
        right_mass = np.sum(al_gray[:, self.target_width // 2:] > 45)

        final_angle = pca_angle
        if left_mass < right_mass:
            final_angle = pca_angle + 180.0
            M_180 = cv2.getRotationMatrix2D((float(cx), float(cy)), float(final_angle), 1.0)
            M_180[0, 2] += (self.target_width / 2.0 - cx)
            M_180[1, 2] += (self.target_height / 2.0 - cy)
            aligned = cv2.warpAffine(
                frame, M_180, (self.target_width, self.target_height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(28, 30, 32)
            )

        # Overlay on debug frame
        cv2.drawContours(debug, [box], 0, (0, 255, 120), 2)
        cv2.circle(debug, (int(cx), int(cy)), 6, (0, 0, 255), -1)
        cv2.putText(
            debug,
            f"Kapi Kolu: ({int(cx)},{int(cy)}) | Aci: {final_angle:.1f} deg",
            (max(10, int(box[0][0])), max(25, int(box[0][1]) - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 120),
            2,
            cv2.LINE_AA,
        )

        confidence = float(min(1.0, area / (self.target_width * self.target_height * 0.40)))

        return HandleLocalizationResult(
            success=True,
            aligned_image=aligned,
            bbox_corners=box,
            center=(int(cx), int(cy)),
            angle=float(final_angle),
            confidence=round(confidence, 3),
            debug_frame=debug,
        )
