"""
PC Vision QC Inspection Server.
Hosts:
- External Ethernet IP Camera manager (RTSP / HTTP / TCP Socket / Industrial GigE)
- Image streaming endpoint (/api/stream/next)
- Golden Reference distribution (/api/golden)
- Inspection logging & Human-in-the-Loop Feedback synchronization
"""

import os
import sys
import glob
import base64
import time
from typing import Dict, Any, Optional
import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from server.camera_source import EthernetIPCamera
except ImportError:
    from camera_source import EthernetIPCamera

from core.database import InspectionDatabase

app = FastAPI(title="Industrial Vision QC PC Server with Ethernet IP Camera", version="2.0.0")
MOCK_DIR = os.path.join(BASE_DIR, "mock_data")
STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
DB_PATH = os.path.join(BASE_DIR, "data", "qc_inspections.db")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Persistent Database Manager
db = InspectionDatabase(DB_PATH)

# External Ethernet IP Camera instance
camera = EthernetIPCamera(camera_type="simulated", ip="192.168.1.100", port=554, stream_path="/stream1")

sample_index = 0
inspection_logs = []
feedback_logs = []


class CameraConfigPayload(BaseModel):
    camera_type: str            # "rtsp", "http", "tcp_socket", "simulated"
    ip: str
    port: int = 554
    stream_path: str = "/stream1"
    username: Optional[str] = ""
    password: Optional[str] = ""


class InspectionLogPayload(BaseModel):
    sample_name: str
    decision: str
    anomaly_score: float
    confidence: float
    elapsed_ms: float
    reason: str


class FeedbackPayload(BaseModel):
    sample_name: str
    model_decision: str
    operator_decision: str
    anomaly_score: float
    notes: Optional[str] = ""


def get_available_samples():
    return sorted(glob.glob(os.path.join(MOCK_DIR, "sample_*.png")))


@app.get("/api/health")
def health_check():
    return {
        "status": "ONLINE",
        "server_time": time.time(),
        "camera_connected": camera.is_connected,
        "camera_type": camera.camera_type,
        "camera_ip": camera.ip,
        "sample_count": len(get_available_samples())
    }


@app.post("/api/camera/config")
def set_camera_config(cfg: CameraConfigPayload):
    global camera
    camera.disconnect()
    camera = EthernetIPCamera(
        camera_type=cfg.camera_type,
        ip=cfg.ip,
        port=cfg.port,
        stream_path=cfg.stream_path,
        username=cfg.username or "",
        password=cfg.password or ""
    )
    success = camera.connect()
    return {
        "success": success,
        "camera_type": camera.camera_type,
        "ip": camera.ip,
        "port": camera.port,
        "status": "CONNECTED" if success else "CONNECTION_FAILED",
        "rtsp_url": camera.get_rtsp_url() if camera.camera_type == "rtsp" else None
    }


@app.get("/api/camera/status")
def get_camera_status():
    return {
        "connected": camera.is_connected,
        "camera_type": camera.camera_type,
        "ip": camera.ip,
        "port": camera.port,
        "stream_path": camera.stream_path,
        "frames_captured": camera.frame_count,
        "last_capture_time": camera.last_capture_time,
    }


@app.get("/api/golden")
def get_golden_reference():
    golden_path = os.path.join(MOCK_DIR, "golden_reference.png")
    if not os.path.exists(golden_path):
        raise HTTPException(status_code=404, detail="Golden reference not generated yet")
    return FileResponse(golden_path, media_type="image/png")


@app.get("/api/stream/next")
def get_next_camera_frame():
    global sample_index
    frame = None
    sample_name = "live_ethernet_camera.jpg"

    # If external Ethernet camera is connected, capture real frame
    if camera.is_connected and camera.camera_type != "simulated":
        ok, cam_frame, msg = camera.capture_frame()
        if ok and cam_frame is not None:
            frame = cam_frame
            sample_name = f"Ethernet_IP_{camera.ip}_{int(time.time()*1000)}.jpg"

    # Fallback to test samples if camera not ready or in simulated mode
    if frame is None:
        samples = get_available_samples()
        if not samples:
            raise HTTPException(status_code=404, detail="No camera frames found")
        current_path = samples[sample_index % len(samples)]
        sample_index += 1
        frame = cv2.imread(current_path)
        sample_name = os.path.basename(current_path)

    if frame is None:
        raise HTTPException(status_code=500, detail="Failed to acquire frame")

    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    b64_str = base64.b64encode(buffer).decode("utf-8")

    return {
        "frame_id": sample_index,
        "sample_name": sample_name,
        "source": "EXTERNAL_ETHERNET_IP" if (camera.is_connected and camera.camera_type != "simulated") else "SIMULATED_FEED",
        "timestamp": time.time(),
        "width": frame.shape[1],
        "height": frame.shape[0],
        "image_base64": b64_str,
    }


@app.post("/api/inspection/log")
def log_inspection(payload: InspectionLogPayload):
    log_entry = payload.dict()
    log_entry["timestamp"] = time.time()
    inspection_logs.append(log_entry)

    # Persist in SQLite Database
    db_id = db.log_inspection(
        sample_name=payload.sample_name,
        decision=payload.decision,
        anomaly_score=payload.anomaly_score,
        threshold=0.15,
        confidence=payload.confidence,
        defect_count=1 if payload.decision == "NOT OK" else 0,
        defect_summary=payload.reason,
        elapsed_ms=payload.elapsed_ms,
        source="ETHERNET_IP" if camera.is_connected and camera.camera_type != "simulated" else "SIMULATED",
        notes=""
    )

    return {"status": "logged", "db_id": db_id, "total_inspections": len(inspection_logs)}


@app.post("/api/feedback")
def log_feedback(payload: FeedbackPayload):
    feedback_entry = payload.dict()
    feedback_entry["timestamp"] = time.time()
    feedback_logs.append(feedback_entry)

    # Update in SQLite Database
    db.update_feedback(
        inspection_id=None,
        sample_name=payload.sample_name,
        model_decision=payload.model_decision,
        operator_decision=payload.operator_decision,
        notes=payload.notes or "Operator feedback"
    )

    return {
        "status": "feedback_saved",
        "total_feedbacks": len(feedback_logs),
        "is_correction": payload.model_decision != payload.operator_decision,
    }


@app.get("/api/inspections/history")
def get_inspection_history(limit: int = 100, filter_status: Optional[str] = "ALL"):
    rows = db.get_recent_inspections(limit=limit, filter_status=filter_status)
    return {"count": len(rows), "records": rows}


@app.get("/api/stats")
def get_stats():
    stats = db.get_statistics()
    return {
        "total_inspections": stats["total"],
        "ok_count": stats["ok_count"],
        "nok_count": stats["nok_count"],
        "operator_corrections": stats["overrides"],
        "accuracy_pct": stats["accuracy_pct"],
        "camera_connected": camera.is_connected,
        "camera_type": camera.camera_type,
        "camera_ip": camera.ip,
        "database_file": DB_PATH,
        "uptime_seconds": time.time(),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
