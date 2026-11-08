"""
Network Client for communicating with the PC Server and managing External Ethernet IP Cameras.
"""

import base64
import os
import glob
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np
import requests


class PCServerClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.is_connected = False
        self.fallback_index = 0

    def check_connection(self) -> bool:
        try:
            res = requests.get(f"{self.base_url}/api/health", timeout=1.5)
            self.is_connected = res.status_code == 200
            return self.is_connected
        except Exception:
            self.is_connected = False
            return False

    def get_camera_status(self) -> Dict[str, Any]:
        if not self.check_connection():
            return {"connected": False, "camera_type": "offline"}
        try:
            res = requests.get(f"{self.base_url}/api/camera/status", timeout=2.0)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return {"connected": False, "camera_type": "offline"}

    def configure_camera(
        self,
        camera_type: str,
        ip: str,
        port: int,
        stream_path: str = "/stream1",
        username: str = "",
        password: str = ""
    ) -> Dict[str, Any]:
        if not self.check_connection():
            return {"success": False, "message": "PC Sunucusuna ulasilamadi"}
        payload = {
            "camera_type": camera_type,
            "ip": ip,
            "port": port,
            "stream_path": stream_path,
            "username": username,
            "password": password
        }
        try:
            res = requests.post(f"{self.base_url}/api/camera/config", json=payload, timeout=4.0)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            return {"success": False, "message": str(e)}
        return {"success": False, "message": "Bilinmeyen sunucu yaniti"}

    def fetch_golden_reference(self, local_save_path: str) -> Optional[np.ndarray]:
        if self.check_connection():
            try:
                res = requests.get(f"{self.base_url}/api/golden", timeout=3.0)
                if res.status_code == 200:
                    with open(local_save_path, "wb") as f:
                        f.write(res.content)
                    return cv2.imread(local_save_path)
            except Exception:
                pass

        if os.path.exists(local_save_path):
            return cv2.imread(local_save_path)
        return None

    def fetch_next_frame(self, fallback_dir: str) -> Tuple[Optional[np.ndarray], str]:
        if self.check_connection():
            try:
                res = requests.get(f"{self.base_url}/api/stream/next", timeout=3.0)
                if res.status_code == 200:
                    data = res.json()
                    img_bytes = base64.b64decode(data["image_base64"])
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    src_tag = f"[{data.get('source', 'SERVER')}] {data.get('sample_name', 'frame.jpg')}"
                    return frame, src_tag
            except Exception:
                pass

        # Offline fallback
        files = sorted(glob.glob(os.path.join(fallback_dir, "sample_*.png")))
        if files:
            path = files[self.fallback_index % len(files)]
            self.fallback_index += 1
            return cv2.imread(path), f"[YEREL YEDEK] {os.path.basename(path)}"

        return None, "no_frame"

    def send_inspection_log(self, payload: Dict[str, Any]) -> bool:
        if not self.is_connected:
            return False
        try:
            requests.post(f"{self.base_url}/api/inspection/log", json=payload, timeout=2.0)
            return True
        except Exception:
            return False

    def send_feedback(self, payload: Dict[str, Any]) -> bool:
        if not self.is_connected:
            return False
        try:
            requests.post(f"{self.base_url}/api/feedback", json=payload, timeout=2.0)
            return True
        except Exception:
            return False
