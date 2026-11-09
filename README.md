# Smart Vision QC - Industrial Quality Control & Active Learning System

An intelligent, computer vision-based quality control (QC) desktop application engineered for industrial manufacturing lines. It performs automated defect and anomaly detection against **golden "OK" references**, features a modern operator interface, and continuously improves from operator feedback via **Human-in-the-Loop Active Learning**.

The system natively supports both **Door Handles** (casting, rosette holes, spindle aperture, straightness) and **Printed Circuit Boards (PCBs)**.

---

## 🚀 Key Features & Pipeline Architecture

```
[Camera / Image Upload]
         │
         ▼
[Stage 1: PCA Alignment & Canonical Normalization]
         │
         ▼
[Stage 2: Golden Reference Anomaly Detection (Heatmap)]
         │
         ▼
[Stage 3: Rule-Based Feature Sub-Inspections]
         │
         ▼
[Stage 4: Human-in-the-Loop Active Learning & SQLite Audit Trail]
```

### 1. Flexible Input Acquisition
- **Image File Upload (`📂 Upload Image & Inspect`):** Upload single or batch photos of parts directly from disk.
- **Golden Teaching (`⭐ Teach This Image as Golden Reference`):** Register any defect-free part as the active golden reference with a single click.
- **Industrial Camera Integration:** Connects to Ethernet IP cameras (RTSP / HTTP snapshot / TCP socket triggers / GigE) and simulated conveyor feeds.

### 2. Stage 1: Part Localization & Orientation Correction (`core/door_handle_locator.py` & `core/locator.py`)
- Computes rotation angle with sub-degree precision using **Principal Component Analysis (PCA)** and contour moments.
- Normalizes parts to a canonical coordinate frame (Door handles: 600×300 px, PCBs: 500×350 px) and aligns the rosette / handle orientation.

### 3. Stage 2: Golden Reference Failure & Anomaly Detection (`core/golden_reference.py`)
- Compares aligned parts against verified "OK" references using dynamic morphological tolerance bands to prevent false positives from micro-vibrations or lighting shifts.
- Detects scratches, cracks, porosity, plating blemishes, and impact dents, generating an **anomaly heatmap** and bounding boxes around defect regions.

### 4. Stage 3: Rule-Based Feature Sub-Inspections (`core/door_handle_inspector.py`)
- **Mounting Screw Holes (Top & Bottom):** Verifies rosette hole presence, shape integrity, and detects burr or swarf blockage.
- **Square Spindle Hole:** Checks existence, location, and dimensions of the spindle drive aperture.
- **Lever Curvature & Straightness:** Evaluates bending, deflection, or stamping deformation along the handle body.

### 5. Stage 4: Operator Feedback & Active Learning (`core/active_learner.py`)
- **False Rejection Correction (Model: NOK ➔ Operator: OK):** Adds the approved sample to the golden memory bank to tolerate similar surface variations without false alarms.
- **False Acceptance Correction (Model: OK ➔ Operator: NOK):** Automatically tightens the anomaly threshold and commits the hard negative to the training repository.
- Complete audit trail with timestamps, operator overrides, anomaly scores, and CSV export powered by an embedded SQLite database.

---

## 🛠 Installation & Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.11 and 3.14)
- OpenCV, PySide6, SciPy, Scikit-learn, NumPy

### Setup Environment
```bash
# Clone the repository
git clone https://github.com/doganozgur/smart-qc-system.git
cd smart-qc-system

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🧪 Running Tests

Verify the complete inspection pipeline and unit tests:

```bash
# Door Handle End-to-End Pipeline & Active Learning Test
python test_door_handle.py

# Golden Reference & PCB Pipeline Tests
python test_pipeline.py

# Database Logging & CSV Export Test
python test_db.py

# REST API Server Test
python test_server.py
```

---

## 🖥 Launching the Desktop Application

### Linux
```bash
./run_client.sh
# or directly:
python client/app.py
```

### Windows (Pre-built Executable)
1. Download **`SmartVisionQC-Windows.zip`** from the latest run on the [GitHub Actions tab](https://github.com/doganozgur/smart-qc-system/actions).
2. Right-click and choose **Extract All**.
3. Double-click **`RUN.bat`** or **`SmartVisionQC.exe`**.

### Building the Windows Executable from Source
```cmd
python build_windows_exe.py
```
This generates a standalone, portable bundle with a helper launcher in `dist/SmartVisionQC/` and an archive `dist/SmartVisionQC-Windows.zip`.

---

## 🌐 Optional: Edge/Server Mode
Run the standalone FastAPI backend for distributed camera processing or remote QC telemetry:

```bash
python server/server.py
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Documentation: `http://localhost:8000/docs`

---

## 📄 License
This project is licensed under the MIT License.
