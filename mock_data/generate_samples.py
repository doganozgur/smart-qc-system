"""
Mock Data Generator for Smart Vision QC Inspection System.
Generates synthetic industrial components (Golden OK, normal variations, and various defect/failure types).
"""

import os
import cv2
import numpy as np


def draw_pcb_base(w=500, h=350):
    """Draws a base industrial PCB component."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (28, 55, 34)  # Industrial PCB green

    # Draw circuit traces (copper lines)
    traces = [
        [(40, 60), (120, 60), (160, 100), (320, 100)],
        [(40, 140), (100, 140), (140, 180), (300, 180)],
        [(40, 220), (150, 220), (200, 260), (350, 260)],
        [(220, 40), (220, 80), (260, 120), (260, 200)],
        [(360, 80), (440, 80), (440, 250)],
        [(180, 280), (280, 280), (320, 310), (440, 310)],
    ]
    for pts in traces:
        for i in range(len(pts) - 1):
            cv2.line(img, pts[i], pts[i + 1], (15, 140, 175), 2, cv2.LINE_AA)

    # 4 Corner mounting holes with shiny metallic rings
    holes = [(35, 35), (w - 35, 35), (35, h - 35), (w - 35, h - 35)]
    for hx, hy in holes:
        cv2.circle(img, (hx, hy), 14, (120, 120, 120), -1)
        cv2.circle(img, (hx, hy), 10, (180, 195, 200), -1)
        cv2.circle(img, (hx, hy), 6, (15, 15, 15), -1)

    # Main Microcontroller IC chip (center)
    ic_x1, ic_y1, ic_x2, ic_y2 = 180, 110, 310, 230
    cv2.rectangle(img, (ic_x1, ic_y1), (ic_x2, ic_y2), (25, 25, 25), -1)
    cv2.rectangle(img, (ic_x1, ic_y1), (ic_x2, ic_y2), (60, 60, 60), 1)

    # IC chip pins
    for py in range(ic_y1 + 10, ic_y2 - 5, 12):
        cv2.line(img, (ic_x1 - 8, py), (ic_x1, py), (170, 170, 170), 2)
        cv2.line(img, (ic_x2, py), (ic_x2 + 8, py), (170, 170, 170), 2)

    # IC chip label text
    cv2.putText(img, "AGY-MCU32", (ic_x1 + 12, ic_y1 + 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

    # Test pads / capacitors
    pads = [(80, 100), (80, 180), (120, 280), (390, 140), (390, 200)]
    for px, py in pads:
        cv2.rectangle(img, (px, py), (px + 20, py + 12), (180, 140, 40), -1)
        cv2.circle(img, (px + 10, py + 6), 3, (210, 210, 210), -1)

    # QR / Serial box
    cv2.rectangle(img, (370, 20), (450, 55), (230, 230, 230), -1)
    cv2.putText(img, "QC-PASS", (375, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 10, 10), 1, cv2.LINE_AA)

    return img


def place_in_camera_view(part_img, angle=0.0, shift_x=0, shift_y=0, bg_val=15):
    """Embeds the aligned part onto a conveyor belt camera frame with rotation & translation without clipping."""
    frame_h, frame_w = 600, 800
    frame = np.ones((frame_h, frame_w, 3), dtype=np.uint8) * bg_val

    # Add conveyor texture/noise
    noise = np.random.normal(0, 3, (frame_h, frame_w, 3)).astype(np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    ph, pw = part_img.shape[:2]
    cx = (frame_w - pw) // 2 + shift_x
    cy = (frame_h - ph) // 2 + shift_y

    # Embed unclipped part
    frame[cy:cy + ph, cx:cx + pw] = part_img

    # Rotate around part center
    if abs(angle) > 0.01:
        center = (cx + pw / 2.0, cy + ph / 2.0)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        frame = cv2.warpAffine(
            frame, M, (frame_w, frame_h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(bg_val, bg_val, bg_val)
        )

    return frame


def generate_all_samples(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    golden_base = draw_pcb_base()

    # 1. Save Golden Reference (Canonical OK)
    golden_path = os.path.join(output_dir, "golden_reference.png")
    cv2.imwrite(golden_path, golden_base)

    # 2. Generate Camera Views (OK samples with angle/position variation)
    ok_variations = [
        ("sample_ok_01.png", 0.0, 5, -8),
        ("sample_ok_02.png", 3.5, -12, 10),
        ("sample_ok_03.png", -4.0, 15, 14),
        ("sample_ok_04.png", 1.8, -5, -15),
    ]
    for name, ang, sx, sy in ok_variations:
        img = place_in_camera_view(golden_base, ang, sx, sy)
        cv2.imwrite(os.path.join(output_dir, name), img)

    # 3. Generate NOK Sample: Scratch / Crack defect
    scratch_part = golden_base.copy()
    cv2.line(scratch_part, (210, 130), (280, 210), (240, 240, 240), 3, cv2.LINE_AA)
    cv2.line(scratch_part, (220, 170), (250, 195), (255, 255, 255), 2, cv2.LINE_AA)
    img_scratch = place_in_camera_view(scratch_part, angle=-2.5, shift_x=8, shift_y=-6)
    cv2.imwrite(os.path.join(output_dir, "sample_nok_scratch.png"), img_scratch)

    # 4. Generate NOK Sample: Missing component / broken solder pad
    missing_part = golden_base.copy()
    # Missing IC chip pin and missing corner screw
    cv2.circle(missing_part, (35, 35), 14, (30, 60, 35), -1)  # Mounting hole missing/damaged
    cv2.rectangle(missing_part, (170, 140), (185, 180), (30, 60, 35), -1)  # Pins obliterated
    img_missing = place_in_camera_view(missing_part, angle=4.0, shift_x=-10, shift_y=12)
    cv2.imwrite(os.path.join(output_dir, "sample_nok_missing.png"), img_missing)

    # 5. Generate NOK Sample: Contamination / Burn stain
    stain_part = golden_base.copy()
    overlay = stain_part.copy()
    cv2.circle(overlay, (330, 160), 28, (20, 30, 80), -1)
    cv2.addWeighted(overlay, 0.75, stain_part, 0.25, 0, stain_part)
    img_stain = place_in_camera_view(stain_part, angle=-1.2, shift_x=-15, shift_y=-8)
    cv2.imwrite(os.path.join(output_dir, "sample_nok_stain.png"), img_stain)

    print(f"Generated {len(ok_variations) + 4} synthetic test images in {output_dir}")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    generate_all_samples(out_dir)
