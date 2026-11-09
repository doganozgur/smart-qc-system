"""
Synthetic Industrial Door Handle Sample Generator.
Generates realistic inspection images for door handles (lever + rosette):
- Golden reference (OK pristine sample)
- OK variations with slight lighting/rotation variations
- NOK with surface scratch / crack
- NOK with coating stain / discoloration
- NOK with blocked / missing screw hole
- NOK with deformed / bent lever arm
"""

import os
import cv2
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mock_data", "door_handles")


def draw_brushed_metal_texture(w: int, h: int, base_color=(190, 195, 200)) -> np.ndarray:
    """Generates a realistic brushed metal texture (horizontal grain)."""
    tex = np.full((h, w, 3), base_color, dtype=np.uint8)
    noise = np.random.normal(0, 5, (h, w)).astype(np.float32)
    # Blur horizontally for brushed look
    grain = cv2.GaussianBlur(noise, (1, 15), 0)
    for c in range(3):
        col = tex[:, :, c].astype(np.float32) + grain
        tex[:, :, c] = np.clip(col, 0, 255).astype(np.uint8)
    return tex


def create_door_handle_base(
    width: int = 700,
    height: int = 400,
    angle_deg: float = 0.0,
    offset_xy: tuple = (0, 0),
    lever_bend_offset: int = 0,
    missing_screw: bool = False,
    screw_blocked: bool = False,
    scratch: bool = False,
    stain: bool = False,
    light_variation: float = 1.0,
) -> np.ndarray:
    """
    Creates a detailed synthetic door handle image on a dark conveyor inspection background.
    """
    np.random.seed(42 if not (scratch or stain or missing_screw or lever_bend_offset) else None)

    # Conveyor background (dark matte grey with subtle camera noise)
    frame = np.full((height, width, 3), (28, 30, 32), dtype=np.uint8)
    bg_noise = np.random.normal(0, 3, (height, width, 3)).astype(np.int16)
    frame = np.clip(frame.astype(np.int16) + bg_noise, 0, 255).astype(np.uint8)

    # Door Handle Canvas (at canonical orientation first, then rotated/translated)
    cw, ch = 600, 300
    canvas = np.zeros((ch, cw, 3), dtype=np.uint8)
    mask = np.zeros((ch, cw), dtype=np.uint8)

    # 1. Rosette (Circular base plate on the left)
    rosette_center = (140, 150)
    rosette_radius = 70

    # 2. Lever Arm (Extending from rosette towards the right)
    # Lever coordinates: neck attached to rosette, tapering towards right handle end
    lever_pts = [
        (140, 125),
        (220, 130),
        (480, 135 + lever_bend_offset),
        (510, 150 + lever_bend_offset),
        (480, 165 + lever_bend_offset),
        (220, 170),
        (140, 175)
    ]
    lever_poly = np.array(lever_pts, dtype=np.int32)

    # Fill mask
    cv2.circle(mask, rosette_center, rosette_radius, 255, -1)
    cv2.fillPoly(mask, [lever_poly], 255)

    # Create Brushed Metal Surface
    base_col = (int(190 * light_variation), int(195 * light_variation), int(200 * light_variation))
    metal_tex = draw_brushed_metal_texture(cw, ch, base_color=base_col)

    # Add gradient highlight (lighting reflection along the cylindrical lever)
    y_coords, x_coords = np.mgrid[0:ch, 0:cw]
    lever_grad = np.exp(-((y_coords - 148) ** 2) / (2 * 14 ** 2)) * 35.0
    for c in range(3):
        metal_tex[:, :, c] = np.clip(metal_tex[:, :, c].astype(np.float32) + lever_grad, 0, 255).astype(np.uint8)

    # Apply mask
    canvas[mask > 0] = metal_tex[mask > 0]

    # Draw Bevel & Edge Shadows on Door Handle
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(canvas, contours, -1, (130, 135, 140), 2)

    # 3. Features on the Rosette
    # A) Central Spindle Hole (Square 8x8mm / approx 24x24 px)
    sp_size = 22
    sp_top_left = (rosette_center[0] - sp_size // 2, rosette_center[1] - sp_size // 2)
    sp_bot_right = (rosette_center[0] + sp_size // 2, rosette_center[1] + sp_size // 2)
    cv2.rectangle(canvas, sp_top_left, sp_bot_right, (18, 20, 22), -1)
    cv2.rectangle(canvas, sp_top_left, sp_bot_right, (70, 75, 80), 1)

    # B) Two Screw Mounting Holes (Top & Bottom on Rosette)
    screw_top = (rosette_center[0], rosette_center[1] - 45)
    screw_bot = (rosette_center[0], rosette_center[1] + 45)
    screw_radius = 8

    # Top Screw Hole
    cv2.circle(canvas, screw_top, screw_radius, (15, 15, 15), -1)
    cv2.circle(canvas, screw_top, screw_radius + 2, (120, 125, 130), 1)

    # Bottom Screw Hole
    if missing_screw:
        # Completely absent or unmachined (solid metal)
        pass
    elif screw_blocked:
        # Blocked with burr / casting defect
        cv2.circle(canvas, screw_bot, screw_radius, (140, 145, 150), -1)
        # uneven burr
        cv2.circle(canvas, (screw_bot[0] + 2, screw_bot[1] - 1), 5, (90, 95, 100), -1)
    else:
        # Clean screw hole
        cv2.circle(canvas, screw_bot, screw_radius, (15, 15, 15), -1)
        cv2.circle(canvas, screw_bot, screw_radius + 2, (120, 125, 130), 1)

    # 4. Injected Defects
    if scratch:
        # Deep dark scratch across the lever arm
        scratch_pts = np.array([
            (320, 142), (345, 153), (380, 146), (410, 158)
        ], dtype=np.int32)
        cv2.polylines(canvas, [scratch_pts], False, (40, 45, 50), 3, cv2.LINE_AA)
        # bright reflection edge of scratch
        cv2.polylines(canvas, [scratch_pts + 1], False, (245, 250, 255), 1, cv2.LINE_AA)

    if stain:
        # Discoloration / chemical stain / oxidation spot
        stain_mask = np.zeros((ch, cw), dtype=np.uint8)
        cv2.circle(stain_mask, (280, 150), 22, 255, -1)
        cv2.circle(stain_mask, (295, 156), 16, 255, -1)
        stain_blur = cv2.GaussianBlur(stain_mask, (21, 21), 0).astype(np.float32) / 255.0
        stain_col = np.array([30, 60, 110], dtype=np.float32)  # brownish/burnt stain
        for c in range(3):
            canvas[:, :, c] = np.clip(
                canvas[:, :, c].astype(np.float32) * (1.0 - stain_blur * 0.7) + stain_col[c] * (stain_blur * 0.7),
                0, 255
            ).astype(np.uint8)

    # 5. Place on Conveyor with Rotation and Shift
    M = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle_deg, 1.0)
    M[0, 2] += (width / 2 - cw / 2) + offset_xy[0]
    M[1, 2] += (height / 2 - ch / 2) + offset_xy[1]

    # Warp canvas and mask
    warped_handle = cv2.warpAffine(canvas, M, (width, height), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    warped_mask = cv2.warpAffine(mask, M, (width, height), flags=cv2.INTER_NEAREST, borderValue=0)

    # Blend onto background
    final_img = frame.copy()
    final_img[warped_mask > 0] = warped_handle[warped_mask > 0]

    return final_img


def generate_all_door_handle_samples():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating door handle samples in: {OUTPUT_DIR}")

    samples = [
        # 1. Pristine Golden Reference
        ("golden_reference.png", {"angle_deg": 0.0, "offset_xy": (0, 0)}),

        # 2. Acceptable OK variations (slight conveyor drift, light change)
        ("sample_ok_01.png", {"angle_deg": 2.5, "offset_xy": (10, -5), "light_variation": 1.02}),
        ("sample_ok_02.png", {"angle_deg": -3.0, "offset_xy": (-15, 8), "light_variation": 0.98}),
        ("sample_ok_03.png", {"angle_deg": 4.5, "offset_xy": (5, 12), "light_variation": 1.05}),

        # 3. NOK - Surface Scratch on Lever
        ("sample_nok_scratch.png", {"angle_deg": -1.5, "offset_xy": (5, -4), "scratch": True}),

        # 4. NOK - Coating Stain / Discoloration
        ("sample_nok_stain.png", {"angle_deg": 2.0, "offset_xy": (-8, 6), "stain": True}),

        # 5. NOK - Blocked / Defective Screw Hole
        ("sample_nok_blocked_hole.png", {"angle_deg": 0.5, "offset_xy": (2, -2), "screw_blocked": True}),

        # 6. NOK - Missing Screw Hole
        ("sample_nok_missing_hole.png", {"angle_deg": -2.0, "offset_xy": (-4, 3), "missing_screw": True}),

        # 7. NOK - Bent / Deformed Lever Arm
        ("sample_nok_bent.png", {"angle_deg": 1.0, "offset_xy": (3, 5), "lever_bend_offset": -25}),
    ]

    for fname, kwargs in samples:
        img = create_door_handle_base(**kwargs)
        path = os.path.join(OUTPUT_DIR, fname)
        cv2.imwrite(path, img)
        print(f"  ✔ Created {fname}")

    print("Door handle test dataset successfully generated!")


if __name__ == "__main__":
    generate_all_door_handle_samples()
