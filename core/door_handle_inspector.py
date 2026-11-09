"""
Door Handle Specific Sub-checks Engine.
Performs deterministic geometric and structural checks on canonically aligned door handles:
1. Rosette Mounting Screw Holes (Top & Bottom: presence, clear circular opening, no burr blockage)
2. Spindle Hole (Central square hole for lock spindle: presence, clearance)
3. Lever Curvature / Straightness (Detects bent or deformed handle arms)
"""

from typing import Dict, Any, List, Tuple
import cv2
import numpy as np


class DoorHandleSubInspector:
    def __init__(self, target_width: int = 600, target_height: int = 300):
        self.target_width = target_width
        self.target_height = target_height

    def run_subchecks(self, aligned_handle: np.ndarray) -> Dict[str, Any]:
        """
        Runs all domain-specific door handle subchecks on canonically aligned image.
        Returns dictionary with pass/fail status, detailed metrics, and annotated view.
        """
        annotated = aligned_handle.copy()
        gray = cv2.cvtColor(aligned_handle, cv2.COLOR_BGR2GRAY)

        hole_res = self._check_rosette_holes(gray, annotated)
        curvature_res = self._check_lever_curvature(gray, annotated)

        all_passed = (
            hole_res["top_screw"]
            and hole_res["bot_screw"]
            and hole_res["spindle"]
            and curvature_res["passed"]
        )

        return {
            "all_passed": all_passed,
            "details": {
                "Üst Montaj Vida Deliği": hole_res["top_screw"],
                "Alt Montaj Vida Deliği": hole_res["bot_screw"],
                "Kare Mil Yuvası": hole_res["spindle"],
                "Kol Düzgünlüğü (Eğiklik)": curvature_res["passed"],
            },
            "metrics": {
                "holes": hole_res,
                "curvature": curvature_res,
            },
            "annotated_view": annotated,
        }

    def _check_rosette_holes(self, gray: np.ndarray, annotated: np.ndarray) -> Dict[str, Any]:
        """
        Detects internal through-holes inside the rosette (x: 140..260)
        using contour topology (RETR_CCOMP internal contours).
        """
        metal = (gray > 90).astype(np.uint8)
        cnts, hierarchy = cv2.findContours(metal, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

        holes: List[Tuple[int, int, float]] = []
        if hierarchy is not None:
            for i, c in enumerate(cnts):
                if hierarchy[0][i][3] != -1:
                    area = cv2.contourArea(c)
                    if 50 < area < 1000:
                        M = cv2.moments(c)
                        if M["m00"] > 0:
                            hx = int(M["m10"] / M["m00"])
                            hy = int(M["m01"] / M["m00"])
                            if 140 <= hx <= 260:
                                holes.append((hx, hy, area))

        # Classify holes
        spindle_candidates = [h for h in holes if 350 < h[2] < 800 and 130 < h[1] < 170]
        screw_candidates = [h for h in holes if 100 < h[2] < 350]
        top_screw = [h for h in screw_candidates if h[1] < 130]
        bot_screw = [h for h in screw_candidates if h[1] > 170]

        has_spindle = len(spindle_candidates) > 0
        has_top = len(top_screw) > 0
        has_bot = len(bot_screw) > 0

        # Annotations
        # 1. Top screw
        if has_top:
            hx, hy, _ = top_screw[0]
            cv2.circle(annotated, (hx, hy), 12, (0, 255, 0), 2)
            cv2.putText(annotated, "Ust Vida: OK", (hx - 35, hy - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1)
        else:
            cv2.circle(annotated, (196, 103), 12, (0, 0, 255), 2)
            cv2.putText(annotated, "Ust Vida: NOK", (161, 87), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1)

        # 2. Spindle
        if has_spindle:
            hx, hy, _ = spindle_candidates[0]
            cv2.rectangle(annotated, (hx - 12, hy - 12), (hx + 12, hy + 12), (0, 255, 0), 2)
            cv2.putText(annotated, "Mil: OK", (hx - 20, hy + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1)
        else:
            cv2.rectangle(annotated, (184, 136), (208, 160), (0, 0, 255), 2)
            cv2.putText(annotated, "Mil: NOK", (176, 174), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1)

        # 3. Bottom screw
        if has_bot:
            hx, hy, _ = bot_screw[0]
            cv2.circle(annotated, (hx, hy), 12, (0, 255, 0), 2)
            cv2.putText(annotated, "Alt Vida: OK", (hx - 35, hy + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 0), 1)
        else:
            cv2.circle(annotated, (196, 193), 12, (0, 0, 255), 2)
            cv2.putText(annotated, "Alt Vida: NOK", (161, 219), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1)

        return {
            "top_screw": has_top,
            "bot_screw": has_bot,
            "spindle": has_spindle,
            "holes_detected": len(holes),
        }

    def _check_lever_curvature(self, gray: np.ndarray, annotated: np.ndarray) -> Dict[str, Any]:
        """Checks whether the lever arm profile has straight linear form without excessive curvature."""
        x_start, x_end = 260, 500
        xs, ys = [], []

        for x in range(x_start, x_end, 15):
            col = gray[:, x]
            metal_indices = np.where(col > 70)[0]
            if len(metal_indices) > 5:
                xs.append(x)
                ys.append((metal_indices[0] + metal_indices[-1]) / 2.0)

        if len(xs) < 5:
            return {"passed": False, "max_deflection": 999.0}

        xs_arr = np.array(xs, dtype=np.float32)
        ys_arr = np.array(ys, dtype=np.float32)

        poly = np.polyfit(xs_arr, ys_arr, 1)
        fitted = np.polyval(poly, xs_arr)
        max_deviation = float(np.max(np.abs(ys_arr - fitted)))

        is_straight = max_deviation <= 1.5
        color = (0, 255, 0) if is_straight else (0, 0, 255)

        for i in range(len(xs) - 1):
            pt1 = (int(xs[i]), int(ys[i]))
            pt2 = (int(xs[i + 1]), int(ys[i + 1]))
            cv2.line(annotated, pt1, pt2, color, 1)

        cv2.putText(
            annotated,
            f"Kol Duzgunlugu: {max_deviation:.2f}px {'(OK)' if is_straight else '(NOK)'}",
            (260, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            color,
            1,
            cv2.LINE_AA,
        )

        return {
            "passed": is_straight,
            "max_deflection": round(max_deviation, 2),
            "threshold": 1.5,
        }
