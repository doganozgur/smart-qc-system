"""
Industrial External Ethernet IP Camera Interface.
Supports:
1. RTSP Stream (e.g. rtsp://192.168.1.100:554/stream1 - H.264/H.265/MJPEG)
2. HTTP IP Snapshot / MJPEG (e.g. http://192.168.1.100:8080/shot.jpg)
3. Industrial TCP/IP Triggered Socket Camera (Sends 'TRIG\n' over TCP, receives image buffer)
4. Zero-lag multi-threaded frame grabber (prevents RTSP buffer latency)
5. Automatic reconnection and fallback mode
"""

import os
import time
import socket
import threading
from typing import Optional, Tuple
import cv2
import numpy as np
import requests


class EthernetIPCamera:
    def __init__(
        self,
        camera_type: str = "rtsp",          # "rtsp", "http", "tcp_socket", "simulated"
        ip: str = "192.168.1.100",
        port: int = 554,
        stream_path: str = "/stream1",
        username: str = "",
        password: str = "",
        timeout_sec: float = 3.0,
    ):
        self.camera_type = camera_type.lower()
        self.ip = ip
        self.port = port
        self.stream_path = stream_path
        self.username = username
        self.password = password
        self.timeout_sec = timeout_sec

        self.is_connected = False
        self.last_frame: Optional[np.ndarray] = None
        self.last_capture_time = 0.0
        self.frame_count = 0

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()

    def get_rtsp_url(self) -> str:
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        path = self.stream_path if self.stream_path.startswith("/") else f"/{self.stream_path}"
        return f"rtsp://{auth}{self.ip}:{self.port}{path}"

    def get_http_url(self) -> str:
        path = self.stream_path if self.stream_path.startswith("/") else f"/{self.stream_path}"
        return f"http://{self.ip}:{self.port}{path}"

    def connect(self) -> bool:
        """Attempts to connect to the Ethernet IP Camera."""
        self.disconnect()

        if self.camera_type == "rtsp":
            url = self.get_rtsp_url()
            # Set OpenCV RTSP buffer size to minimum to avoid latency
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|buffer_size;102400|max_delay;500000"
            self._cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if self._cap.isOpened():
                self.is_connected = True
                self._start_grab_thread()
                return True
            else:
                self.is_connected = False
                return False

        elif self.camera_type == "http":
            try:
                auth = (self.username, self.password) if self.username else None
                res = requests.get(self.get_http_url(), auth=auth, timeout=self.timeout_sec)
                if res.status_code == 200:
                    self.is_connected = True
                    return True
            except Exception:
                pass
            self.is_connected = False
            return False

        elif self.camera_type == "tcp_socket":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.timeout_sec)
                s.connect((self.ip, self.port))
                s.close()
                self.is_connected = True
                return True
            except Exception:
                self.is_connected = False
                return False

        elif self.camera_type == "simulated":
            self.is_connected = True
            return True

        return False

    def _start_grab_thread(self):
        """Continuously pulls frames in background so OpenCV internal buffer is always fresh."""
        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()

    def _grab_loop(self):
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self.last_frame = frame
                    self.last_capture_time = time.time()
                    self.frame_count += 1
            else:
                time.sleep(0.01)

    def capture_frame(self) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        Captures the latest instantaneous frame from the Ethernet camera.
        Returns: (success, image_bgr, status_info)
        """
        if self.camera_type == "rtsp":
            with self._lock:
                if self.last_frame is not None:
                    return True, self.last_frame.copy(), f"RTSP IP: {self.ip}:{self.port} (FPS: live)"
            # If thread didn't grab yet, try direct read
            if self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    return True, frame, f"RTSP IP: {self.ip}:{self.port}"
            return False, None, f"RTSP akisina ulasilamadi ({self.ip})"

        elif self.camera_type == "http":
            try:
                auth = (self.username, self.password) if self.username else None
                res = requests.get(self.get_http_url(), auth=auth, timeout=self.timeout_sec)
                if res.status_code == 200:
                    arr = np.frombuffer(res.content, np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return True, frame, f"HTTP Snapshot: {self.ip}"
            except Exception as e:
                return False, None, f"HTTP kamera hatasi: {e}"
            return False, None, f"HTTP baglanti hatasi ({self.ip})"

        elif self.camera_type == "tcp_socket":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.timeout_sec)
                    s.connect((self.ip, self.port))
                    # Send trigger command
                    s.sendall(b"TRIGGER\n")
                    # Read size header (4 bytes)
                    size_data = s.recv(4)
                    size = int.from_bytes(size_data, byteorder="big")
                    # Read image bytes
                    buf = bytearray()
                    while len(buf) < size:
                        chunk = s.recv(min(4096, size - len(buf)))
                        if not chunk:
                            break
                        buf.extend(chunk)
                    arr = np.frombuffer(buf, np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return True, frame, f"TCP Trigger IP: {self.ip}"
            except Exception as e:
                return False, None, f"TCP Socket hatasi: {e}"

        return False, None, "Kamera aktif degil veya tanimsiz"

    def disconnect(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.is_connected = False
