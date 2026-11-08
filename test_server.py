"""
Integration test for PC Server REST endpoints and client synchronization.
"""

import threading
import time
import requests
import uvicorn
from server.server import app


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")


def test_api():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.0)

    base = "http://127.0.0.1:8001"

    # 1. Health
    res = requests.get(f"{base}/api/health")
    assert res.status_code == 200, "Health check failed"
    print("✔ Health Check:", res.json())

    # 2. Golden Reference download
    res = requests.get(f"{base}/api/golden")
    assert res.status_code == 200, "Golden reference download failed"
    print("✔ Golden Download Size:", len(res.content), "bytes")

    # 3. Stream Next Frame
    res = requests.get(f"{base}/api/stream/next")
    assert res.status_code == 200, "Stream next failed"
    data = res.json()
    assert "image_base64" in data, "No base64 image received"
    print(f"✔ Stream Next Frame: ID={data['frame_id']}, Sample={data['sample_name']}, Base64 len={len(data['image_base64'])}")

    # 4. Log Inspection
    payload = {
        "sample_name": data["sample_name"],
        "decision": "OK",
        "anomaly_score": 0.0,
        "confidence": 0.95,
        "elapsed_ms": 4.5,
        "reason": "Test inspection passed"
    }
    res = requests.post(f"{base}/api/inspection/log", json=payload)
    assert res.status_code == 200, "Log inspection failed"
    print("✔ Log Inspection:", res.json())

    # 5. Send Feedback (Active Learning Sync)
    fb_payload = {
        "sample_name": data["sample_name"],
        "model_decision": "NOT OK",
        "operator_decision": "OK",
        "anomaly_score": 0.16,
        "notes": "Verified by QC supervisor"
    }
    res = requests.post(f"{base}/api/feedback", json=fb_payload)
    assert res.status_code == 200, "Feedback logging failed"
    print("✔ Operator Feedback Logged:", res.json())

    # 6. Stats
    res = requests.get(f"{base}/api/stats")
    assert res.status_code == 200, "Stats fetch failed"
    print("✔ Server Stats:", res.json())

    print("\n✅ SERVER INTEGRATION TESTS PASSED 100%!")


if __name__ == "__main__":
    test_api()
