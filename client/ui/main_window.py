"""
PySide6 Industrial Vision QC Desktop Application.
Features:
- SQLite Database Logging & Historical Records Viewer (OK/NOK with Timestamps)
- External Ethernet IP Camera Integration (RTSP / HTTP / TCP Trigger / GigE)
- Live inspection view with multi-layer overlays (Raw, Aligned ROI, Anomaly Heatmap)
- Prominent OK / NOT OK (Failure) status banners
- Multi-model inspection breakdown (localization, golden comparison, sub-checks)
- Interactive Human-in-the-Loop Active Learning (Operator Feedback -> Instant Model Update)
- Conveyor auto-run & server synchronization
"""

import os
import time
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QSlider, QGroupBox,
    QGridLayout, QStatusBar, QMessageBox, QTextEdit, QDialog,
    QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)

from core.pipeline import VisionQCPipeline, PipelineOutput
from core.active_learner import ActiveLearner
from core.database import InspectionDatabase
from client.network_client import PCServerClient


class DatabaseViewerDialog(QDialog):
    def __init__(self, db: InspectionDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("🗄 Kalite Kontrol Veritabanı Kayıtları (Geçmiş ve Raporlar)")
        self.resize(1000, 550)
        self.setStyleSheet("""
            QDialog { background-color: #1e1f29; color: #f8f8f2; }
            QLabel { color: #f8f8f2; font-weight: bold; }
            QTableWidget { background-color: #282a36; color: #f8f8f2; gridline-color: #44475a; border: 1px solid #44475a; border-radius: 4px; }
            QHeaderView::section { background-color: #21222c; color: #bd93f9; font-weight: bold; padding: 6px; border: 1px solid #44475a; }
            QPushButton { background-color: #44475a; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #6272a4; }
            QComboBox { background-color: #282a36; color: #50fa7b; border: 1px solid #6272a4; border-radius: 4px; padding: 4px; }
        """)

        layout = QVBoxLayout(self)

        # Filter bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Filtrele:"))
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["Tümü", "Yalnızca OK", "Yalnızca NOT OK (Hatalı)"])
        self.cmb_filter.currentIndexChanged.connect(self.load_data)
        top_bar.addWidget(self.cmb_filter)

        top_bar.addStretch()

        self.btn_export = QPushButton("📥 CSV / Excel Olarak Dışa Aktar")
        self.btn_export.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_export.clicked.connect(self.export_csv)
        top_bar.addWidget(self.btn_export)

        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_refresh.clicked.connect(self.load_data)
        top_bar.addWidget(self.btn_refresh)

        layout.addLayout(top_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tarih ve Saat", "Parça / Kaynak", "Karar",
            "Anomali Skoru", "Kusur Özeti", "Süre (ms)", "Operatör Durumu"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        idx = self.cmb_filter.currentIndex()
        filter_status = "ALL"
        if idx == 1:
            filter_status = "OK"
        elif idx == 2:
            filter_status = "NOT OK"

        rows = self.db.get_recent_inspections(limit=200, filter_status=filter_status)
        self.table.setRowCount(len(rows))

        for i, r in enumerate(rows):
            # ID
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            # Created At
            self.table.setItem(i, 1, QTableWidgetItem(str(r["created_at"])))
            # Sample
            self.table.setItem(i, 2, QTableWidgetItem(str(r["sample_name"])))

            # Decision with Color
            dec_item = QTableWidgetItem(str(r["decision"]))
            dec_item.setFont(QFont("Arial", 10, QFont.Bold))
            if r["decision"] == "OK":
                dec_item.setForeground(QColor("#50fa7b"))
            else:
                dec_item.setForeground(QColor("#ff5555"))
            self.table.setItem(i, 3, dec_item)

            # Anomaly Score
            score_item = QTableWidgetItem(f"%{int(r['anomaly_score'] * 100)}")
            self.table.setItem(i, 4, score_item)

            # Defect Summary
            self.table.setItem(i, 5, QTableWidgetItem(str(r["defect_summary"] or "-")))

            # Elapsed ms
            self.table.setItem(i, 6, QTableWidgetItem(f"{r['elapsed_ms']:.1f}"))

            # Operator Override
            op_text = "Otomatik Karar"
            if r["operator_override"] == 1:
                op_text = f"Elle Düzeltildi ({r['operator_decision']})"
            op_item = QTableWidgetItem(op_text)
            if r["operator_override"] == 1:
                op_item.setForeground(QColor("#ffb86c"))
            self.table.setItem(i, 7, op_item)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV Dosyasını Kaydet", "qc_raporu.csv", "CSV Dosyaları (*.csv)")
        if path:
            count = self.db.export_csv(path)
            QMessageBox.information(self, "Dışa Aktarma Başarılı", f"{count} adet muayene kaydı başarıyla dışa aktarıldı:\n{path}")


class CameraConfigDialog(QDialog):
    def __init__(self, parent=None, current_ip="192.168.1.100", current_port=554):
        super().__init__(parent)
        self.setWindowTitle("Harici Ethernet IP Kamera Ayarları")
        self.resize(420, 300)
        self.setStyleSheet("""
            QDialog { background-color: #21222c; color: #f8f8f2; }
            QLabel { color: #f8f8f2; font-weight: bold; }
            QLineEdit, QComboBox { background-color: #282a36; color: #50fa7b; border: 1px solid #6272a4; border-radius: 4px; padding: 6px; }
            QPushButton { background-color: #6272a4; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["RTSP Akışı (H.264/MJPEG)", "HTTP Snapshot / MJPEG", "TCP/IP Trigger Socket", "Simülasyon (Test Verisi)"])

        self.txt_ip = QLineEdit(current_ip)
        self.txt_port = QLineEdit(str(current_port))
        self.txt_path = QLineEdit("/stream1")
        self.txt_user = QLineEdit("")
        self.txt_pass = QLineEdit("")
        self.txt_pass.setEchoMode(QLineEdit.Password)

        form.addRow("Kamera Protokolü:", self.cmb_type)
        form.addRow("Ethernet IP Adresi:", self.txt_ip)
        form.addRow("Port:", self.txt_port)
        form.addRow("Akış Yolu / Endpoint:", self.txt_path)
        form.addRow("Kullanıcı Adı (opsiyonel):", self.txt_user)
        form.addRow("Şifre (opsiyonel):", self.txt_pass)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_config(self):
        type_map = {0: "rtsp", 1: "http", 2: "tcp_socket", 3: "simulated"}
        return {
            "camera_type": type_map.get(self.cmb_type.currentIndex(), "rtsp"),
            "ip": self.txt_ip.text().strip(),
            "port": int(self.txt_port.text().strip() or "554"),
            "stream_path": self.txt_path.text().strip(),
            "username": self.txt_user.text().strip(),
            "password": self.txt_pass.text().strip()
        }


class MainWindow(QMainWindow):
    def __init__(self, project_dir: str):
        super().__init__()
        self.project_dir = project_dir
        self.door_handle_mock_dir = os.path.join(project_dir, "mock_data", "door_handles")
        self.pcb_mock_dir = os.path.join(project_dir, "mock_data")

        # Default mode is door handle inspection
        self.current_mode = "door_handle"
        self.mock_dir = self.door_handle_mock_dir if os.path.exists(self.door_handle_mock_dir) else self.pcb_mock_dir
        self.db_path = os.path.join(project_dir, "data", "qc_inspections.db")
        self.golden_path = os.path.join(self.mock_dir, "golden_reference.png")

        # Core Engines & Database
        self.db = InspectionDatabase(self.db_path)
        self.pipeline = VisionQCPipeline(
            self.golden_path if os.path.exists(self.golden_path) else None,
            mode=self.current_mode
        )
        self.learner = ActiveLearner(self.db_path, self.pipeline)
        self.network = PCServerClient("http://localhost:8000")

        # Runtime State
        self.current_raw_frame = None
        self.current_sample_name = "Yok"
        self.last_pipeline_output: PipelineOutput = None
        self.last_db_id = None
        self.view_mode = "composite"
        self.camera_ip = "192.168.1.100"
        self.camera_port = 554

        # Auto Run Timer
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.on_fetch_and_inspect)

        self.init_ui()
        self.apply_dark_theme()
        self.check_server_status()

    def init_ui(self):
        self.setWindowTitle("Smart Vision QC - Endüstriyel Kalite Kontrol ve Kapı Kolu Muayene Sistemi")
        self.resize(1340, 880)

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left Column: Image Viewport & Controls
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        # Header Info Bar
        info_bar = QHBoxLayout()
        self.lbl_server_status = QLabel("Sunucu: Bağlanıyor...")
        self.lbl_server_status.setStyleSheet("font-weight: bold; color: #a0a0b0;")

        self.lbl_camera_status = QLabel("📡 Kamera: Bağlı Değil")
        self.lbl_camera_status.setStyleSheet("color: #ffb86c; font-weight: bold; margin-left: 10px;")

        self.btn_config_camera = QPushButton("⚙ Ethernet Kamera")
        self.btn_config_camera.setStyleSheet("background-color: #44475a; color: #8be9fd; font-weight: bold; padding: 4px 8px;")
        self.btn_config_camera.clicked.connect(self.open_camera_dialog)

        self.btn_view_db = QPushButton("🗄 Veritabanı Kayıtları")
        self.btn_view_db.setStyleSheet("background-color: #6272a4; color: #50fa7b; font-weight: bold; padding: 4px 10px;")
        self.btn_view_db.clicked.connect(self.open_database_viewer)

        # Mode Selector (Door Handle vs PCB)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["🚪 Kapı Kolu Muayenesi", "🔲 Elektronik Kart (PCB)"])
        self.cmb_mode.setStyleSheet("background-color: #282a36; color: #f1fa8c; font-weight: bold; border: 1px solid #6272a4; padding: 4px;")
        self.cmb_mode.currentIndexChanged.connect(self.on_mode_changed)

        self.lbl_sample_id = QLabel("Kaynak: -")
        self.lbl_sample_id.setStyleSheet("color: #00bcd4; font-weight: bold;")

        info_bar.addWidget(self.lbl_server_status)
        info_bar.addWidget(self.lbl_camera_status)
        info_bar.addWidget(self.btn_config_camera)
        info_bar.addWidget(self.btn_view_db)
        info_bar.addWidget(QLabel("Mod:"))
        info_bar.addWidget(self.cmb_mode)
        info_bar.addStretch()
        info_bar.addWidget(self.lbl_sample_id)
        left_layout.addLayout(info_bar)

        # Central Image Display
        self.image_display = QLabel("Görüntü bekleniyor...\n(Kamera bağlandığında veya 'Muayene Et' butonuna basıldığında akış başlar)")
        self.image_display.setAlignment(Qt.AlignCenter)
        self.image_display.setMinimumSize(640, 480)
        self.image_display.setStyleSheet("""
            background-color: #121318;
            border: 2px solid #282a36;
            border-radius: 8px;
            color: #6272a4;
            font-size: 15px;
        """)
        left_layout.addWidget(self.image_display, stretch=1)

        # View Mode Toggle Buttons
        view_mode_layout = QHBoxLayout()
        self.btn_view_composite = QPushButton("Sonuç ve Isı Haritası (Kompozit)")
        self.btn_view_raw = QPushButton("Ham Kamera")
        self.btn_view_aligned = QPushButton("Hizalanmış Parça (ROI)")
        self.btn_view_heatmap = QPushButton("Yalnızca Isı Haritası")

        for b in [self.btn_view_composite, self.btn_view_raw, self.btn_view_aligned, self.btn_view_heatmap]:
            b.setCheckable(True)
            view_mode_layout.addWidget(b)

        self.btn_view_composite.setChecked(True)
        self.btn_view_composite.clicked.connect(lambda: self.set_view_mode("composite"))
        self.btn_view_raw.clicked.connect(lambda: self.set_view_mode("raw"))
        self.btn_view_aligned.clicked.connect(lambda: self.set_view_mode("aligned"))
        self.btn_view_heatmap.clicked.connect(lambda: self.set_view_mode("heatmap"))
        left_layout.addLayout(view_mode_layout)

        main_layout.addLayout(left_layout, stretch=3)

        # Right Column: Decision, Model Breakdown, Active Learning & Controls
        right_layout = QVBoxLayout()
        right_layout.setSpacing(14)

        # 1. Big Decision Card
        self.decision_card = QFrame()
        self.decision_card.setFixedHeight(110)
        self.decision_card.setStyleSheet("""
            background-color: #21222c;
            border-radius: 8px;
            border: 2px solid #44475a;
        """)
        card_layout = QVBoxLayout(self.decision_card)
        self.lbl_decision = QLabel("HAZIR")
        self.lbl_decision.setAlignment(Qt.AlignCenter)
        self.lbl_decision.setFont(QFont("Arial", 28, QFont.Bold))
        self.lbl_decision.setStyleSheet("color: #f8f8f2;")
        self.lbl_reason = QLabel("Kameradan veya dosyadan yeni muayene başlatın.")
        self.lbl_reason.setAlignment(Qt.AlignCenter)
        self.lbl_reason.setStyleSheet("color: #8be9fd; font-size: 12px;")
        card_layout.addWidget(self.lbl_decision)
        card_layout.addWidget(self.lbl_reason)
        right_layout.addWidget(self.decision_card)

        # 2. Inspection Metrics & Model Checks Group
        grp_metrics = QGroupBox("Model Muayene Sonuçları")
        grp_metrics.setStyleSheet("QGroupBox { font-weight: bold; color: #f8f8f2; }")
        metrics_layout = QGridLayout(grp_metrics)

        metrics_layout.addWidget(QLabel("Anomali / Sapma Skoru:"), 0, 0)
        self.bar_anomaly = QProgressBar()
        self.bar_anomaly.setRange(0, 100)
        self.bar_anomaly.setValue(0)
        self.bar_anomaly.setTextVisible(True)
        self.bar_anomaly.setStyleSheet("QProgressBar::chunk { background-color: #ff5555; }")
        metrics_layout.addWidget(self.bar_anomaly, 0, 1)

        metrics_layout.addWidget(QLabel("Güven Seviyesi:"), 1, 0)
        self.lbl_confidence = QLabel("-%")
        self.lbl_confidence.setStyleSheet("font-weight: bold; color: #50fa7b;")
        metrics_layout.addWidget(self.lbl_confidence, 1, 1)

        metrics_layout.addWidget(QLabel("Parça Konumlama ve Açı:"), 2, 0)
        self.lbl_locator_info = QLabel("-")
        metrics_layout.addWidget(self.lbl_locator_info, 2, 1)

        metrics_layout.addWidget(QLabel("Alt Model Kontrolleri:"), 3, 0)
        self.lbl_subchecks = QLabel("-")
        metrics_layout.addWidget(self.lbl_subchecks, 3, 1)

        metrics_layout.addWidget(QLabel("Muayene Süresi:"), 4, 0)
        self.lbl_time = QLabel("- ms")
        metrics_layout.addWidget(self.lbl_time, 4, 1)

        right_layout.addWidget(grp_metrics)

        # 3. Active Learning & Operator Feedback
        grp_learning = QGroupBox("Sürekli Öğrenme ve Operatör Geri Bildirimi")
        grp_learning.setStyleSheet("QGroupBox { font-weight: bold; color: #ffb86c; }")
        learn_layout = QVBoxLayout(grp_learning)

        lbl_instruct = QLabel("Model kararı yanlışsa düzeltebilirsiniz.\nKarar veritabanı dosyasına işlenir ve sistem toleransı öğrenir.")
        lbl_instruct.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        learn_layout.addWidget(lbl_instruct)

        btn_feedback_layout = QHBoxLayout()
        self.btn_confirm_ok = QPushButton("✅ Karar Doğru (Onayla)")
        self.btn_confirm_ok.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px;")
        self.btn_confirm_ok.clicked.connect(self.on_confirm_decision)

        self.btn_override = QPushButton("⚠️ Kararı Düzelt (Öğrenmeyi Tetikle)")
        self.btn_override.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; padding: 8px;")
        self.btn_override.clicked.connect(self.on_override_decision)

        btn_feedback_layout.addWidget(self.btn_confirm_ok)
        btn_feedback_layout.addWidget(self.btn_override)
        learn_layout.addLayout(btn_feedback_layout)

        self.txt_learning_log = QTextEdit()
        self.txt_learning_log.setReadOnly(True)
        self.txt_learning_log.setFixedHeight(70)
        self.txt_learning_log.setStyleSheet("background-color: #191a21; color: #50fa7b; font-family: monospace; font-size: 11px;")
        self.txt_learning_log.setText("Veritabanı ve öğrenme modülü hazır.")
        learn_layout.addWidget(self.txt_learning_log)

        right_layout.addWidget(grp_learning)

        # 4. Global Statistics & Threshold Slider
        grp_stats = QGroupBox("Veritabanı İstatistikleri ve Anomali Eşiği")
        grp_stats.setStyleSheet("QGroupBox { font-weight: bold; color: #bd93f9; }")
        stats_layout = QGridLayout(grp_stats)

        self.lbl_stats_summary = QLabel("Toplam: 0 | OK: 0 | NOK: 0 | Doğruluk: %100")
        self.lbl_stats_summary.setStyleSheet("color: #f1fa8c;")
        stats_layout.addWidget(self.lbl_stats_summary, 0, 0, 1, 2)

        stats_layout.addWidget(QLabel("Hassasiyet / Anomali Eşiği:"), 1, 0)
        self.slider_thresh = QSlider(Qt.Horizontal)
        self.slider_thresh.setRange(5, 40)
        self.slider_thresh.setValue(int(self.pipeline.failure_detector.threshold * 100))
        self.slider_thresh.valueChanged.connect(self.on_threshold_changed)
        stats_layout.addWidget(self.slider_thresh, 1, 1)

        self.lbl_thresh_val = QLabel(f"{self.pipeline.failure_detector.threshold:.2f}")
        stats_layout.addWidget(self.lbl_thresh_val, 1, 2)

        right_layout.addWidget(grp_stats)

        # 5. Control Buttons
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(8)

        # Row 1: File Upload & Teach Golden Reference (Using "ve" instead of "&" to prevent Qt mnemonic shortcut issue)
        row1_layout = QHBoxLayout()
        self.btn_upload_image = QPushButton("📂 Resim Yükle ve Muayene Et")
        self.btn_upload_image.setFixedHeight(40)
        self.btn_upload_image.setStyleSheet("background-color: #4f5b66; color: #8be9fd; font-size: 13px; font-weight: bold;")
        self.btn_upload_image.clicked.connect(self.on_upload_image)

        self.btn_teach_golden = QPushButton("⭐ Bu Resmi Referans Olarak Öğret")
        self.btn_teach_golden.setFixedHeight(40)
        self.btn_teach_golden.setStyleSheet("background-color: #ffb86c; color: #1e1f29; font-size: 13px; font-weight: bold;")
        self.btn_teach_golden.clicked.connect(self.on_teach_golden)

        row1_layout.addWidget(self.btn_upload_image, stretch=1)
        row1_layout.addWidget(self.btn_teach_golden, stretch=1)
        ctrl_layout.addLayout(row1_layout)

        # Row 2: Camera / Feed & Auto stream
        row2_layout = QHBoxLayout()
        self.btn_fetch_next = QPushButton("📸 Sıradaki Parçayı Muayene Et")
        self.btn_fetch_next.setFixedHeight(45)
        self.btn_fetch_next.setStyleSheet("background-color: #6272a4; color: white; font-size: 14px; font-weight: bold;")
        self.btn_fetch_next.clicked.connect(self.on_fetch_and_inspect)

        self.btn_auto_run = QPushButton("▶ Canlı / Otomatik Akış")
        self.btn_auto_run.setFixedHeight(45)
        self.btn_auto_run.setCheckable(True)
        self.btn_auto_run.setStyleSheet("background-color: #44475a; color: white; font-size: 14px; font-weight: bold;")
        self.btn_auto_run.clicked.connect(self.toggle_auto_run)

        row2_layout.addWidget(self.btn_fetch_next, stretch=2)
        row2_layout.addWidget(self.btn_auto_run, stretch=1)
        ctrl_layout.addLayout(row2_layout)

        right_layout.addLayout(ctrl_layout)

        main_layout.addLayout(right_layout, stretch=2)

        self.statusBar().showMessage(f"Veritabanı aktif: {self.db_path}")
        self.update_stats_display()

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        for b, m in [(self.btn_view_composite, "composite"), (self.btn_view_raw, "raw"),
                     (self.btn_view_aligned, "aligned"), (self.btn_view_heatmap, "heatmap")]:
            b.setChecked(m == mode)
        self.render_current_view()

    def check_server_status(self):
        is_online = self.network.check_connection()
        if is_online:
            self.lbl_server_status.setText("🟢 PC Sunucu: BAĞLI")
            self.lbl_server_status.setStyleSheet("font-weight: bold; color: #50fa7b;")
            cam_stat = self.network.get_camera_status()
            if cam_stat.get("connected"):
                ctype = cam_stat.get("camera_type", "ip").upper()
                cip = cam_stat.get("ip", "")
                self.lbl_camera_status.setText(f"📡 Kamera: {ctype} ({cip}) [AKTİF]")
                self.lbl_camera_status.setStyleSheet("color: #50fa7b; font-weight: bold;")
            else:
                self.lbl_camera_status.setText("📡 Kamera: Bağlı Değil (Simülasyon)")
                self.lbl_camera_status.setStyleSheet("color: #ffb86c; font-weight: bold;")
        else:
            self.lbl_server_status.setText("🟠 PC Sunucu: ÇEVRİMDIŞI (Yerel DB)")
            self.lbl_server_status.setStyleSheet("font-weight: bold; color: #ffb86c;")
            self.lbl_camera_status.setText("📡 Kamera: Yerel Test Modu")

    @Slot()
    def open_camera_dialog(self):
        dlg = CameraConfigDialog(self, current_ip=self.camera_ip, current_port=self.camera_port)
        if dlg.exec():
            cfg = dlg.get_config()
            self.camera_ip = cfg["ip"]
            self.camera_port = cfg["port"]
            res = self.network.configure_camera(
                camera_type=cfg["camera_type"],
                ip=cfg["ip"],
                port=cfg["port"],
                stream_path=cfg["stream_path"],
                username=cfg["username"],
                password=cfg["password"]
            )
            if res.get("success"):
                QMessageBox.information(self, "Kamera Bağlantısı", f"Ethernet IP Kamera başarıyla bağlandı!\nIP: {cfg['ip']}:{cfg['port']}")
            else:
                QMessageBox.warning(self, "Kamera Uyarısı", f"Kameraya doğrudan bağlanılamadı ({cfg['ip']}).\nSimülasyon modunda devam edilecek.")
            self.check_server_status()

    @Slot()
    def open_database_viewer(self):
        dlg = DatabaseViewerDialog(self.db, self)
        dlg.exec()

    @Slot()
    def on_mode_changed(self, idx: int):
        self.current_mode = "door_handle" if idx == 0 else "pcb"
        self.pipeline.set_mode(self.current_mode)

        if self.current_mode == "door_handle":
            self.mock_dir = self.door_handle_mock_dir
            self.golden_path = os.path.join(self.mock_dir, "golden_reference.png")
            if os.path.exists(self.golden_path):
                self.pipeline.load_golden_reference(cv2.imread(self.golden_path), auto_align=True)
            self.statusBar().showMessage("Mod değiştirildi: Kapı Kolu Muayenesi")
            self.txt_learning_log.append(f"[{time.strftime('%H:%M:%S')}] 🚪 Kapı Kolu Muayene Moduna geçildi.")
        else:
            self.mock_dir = self.pcb_mock_dir
            self.golden_path = os.path.join(self.mock_dir, "golden_reference.png")
            if os.path.exists(self.golden_path):
                self.pipeline.load_golden_reference(cv2.imread(self.golden_path), auto_align=True)
            self.statusBar().showMessage("Mod değiştirildi: PCB Muayenesi")
            self.txt_learning_log.append(f"[{time.strftime('%H:%M:%S')}] 🔲 PCB Muayene Moduna geçildi.")

        self.update_stats_display()

    @Slot()
    def on_upload_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Kapı Kolu / Parça Resmi Yükle ve Muayene Et",
            self.mock_dir,
            "Resim Dosyaları (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return

        frame = cv2.imread(file_path)
        if frame is None:
            QMessageBox.critical(self, "Hata", f"Görsel yüklenemedi:\n{file_path}")
            return

        sample_name = os.path.basename(file_path)
        self.inspect_frame(frame, f"[YÜKLENEN RESİM] {sample_name}", source="FILE_UPLOAD")

    @Slot()
    def on_teach_golden(self):
        if self.current_raw_frame is not None:
            ret = QMessageBox.question(
                self,
                "Altın Referans Öğret",
                "Ekranda görüntülenen mevcut parça 'Altın Referans (Hatasız Standart)' olarak öğretilsin mi?\n\n(Diskten başka bir resim seçmek için 'Hayır'a basın.)",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if ret == QMessageBox.Cancel:
                return
            if ret == QMessageBox.Yes:
                self.teach_frame_as_golden(self.current_raw_frame, self.current_sample_name)
                return

        # Pick pristine golden from file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Hatasız (OK) Referans Görseli Seç",
            self.mock_dir,
            "Resim Dosyaları (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return

        frame = cv2.imread(file_path)
        if frame is None:
            QMessageBox.critical(self, "Hata", f"Görsel yüklenemedi:\n{file_path}")
            return

        self.teach_frame_as_golden(frame, os.path.basename(file_path))

    def teach_frame_as_golden(self, frame: np.ndarray, sample_name: str):
        self.pipeline.load_golden_reference(frame, auto_align=True)
        try:
            cv2.imwrite(self.golden_path, frame)
        except Exception:
            pass

        self.txt_learning_log.append(f"[{time.strftime('%H:%M:%S')}] ⭐ Yeni Altın Referans Öğretildi: {sample_name}")
        QMessageBox.information(
            self,
            "Referans Başarıyla Öğretildi",
            f"'{sample_name}' hatasız standart model olarak kaydedildi!\nModel toleransları ve geometri şablonu bu parçaya göre optimize edildi."
        )
        self.inspect_frame(frame, f"[YENİ REFERANS] {sample_name}", source="TEACH_GOLDEN")

    @Slot()
    def on_fetch_and_inspect(self):
        self.check_server_status()
        frame, sample_name = self.network.fetch_next_frame(self.mock_dir)
        if frame is None:
            self.statusBar().showMessage("Hata: Görüntü yakalanamadı.")
            return

        self.inspect_frame(frame, sample_name, source="CAMERA")

    def inspect_frame(self, frame: np.ndarray, sample_name: str, source: str = "CAMERA"):
        self.current_raw_frame = frame
        self.current_sample_name = sample_name
        self.lbl_sample_id.setText(f"Kaynak: {sample_name}")

        output = self.pipeline.run(frame)
        self.last_pipeline_output = output

        # Log to Persistent SQLite Database
        score = output.inspection.anomaly_score if output.inspection else 1.0
        self.last_db_id = self.db.log_inspection(
            sample_name=sample_name,
            decision=output.final_decision,
            anomaly_score=score,
            threshold=output.inspection.threshold if output.inspection else 0.15,
            confidence=output.overall_confidence,
            defect_count=len(output.inspection.defect_regions) if output.inspection else 1,
            defect_summary=output.reason,
            elapsed_ms=output.elapsed_ms,
            source=source,
            notes="Sistem muayenesi"
        )

        self.update_decision_card(output)
        self.render_current_view()
        self.update_stats_display()

        # Sync to PC server if online
        self.network.send_inspection_log({
            "sample_name": sample_name,
            "decision": output.final_decision,
            "anomaly_score": score,
            "confidence": output.overall_confidence,
            "elapsed_ms": output.elapsed_ms,
            "reason": output.reason,
        })

    def update_decision_card(self, out: PipelineOutput):
        if out.is_ok:
            self.decision_card.setStyleSheet("""
                background-color: #1b5e20;
                border-radius: 8px;
                border: 2px solid #00e676;
            """)
            self.lbl_decision.setText("✔ OK (GEÇTİ)")
            self.lbl_decision.setStyleSheet("color: #e8f5e9; font-weight: bold; font-size: 28px;")
        else:
            self.decision_card.setStyleSheet("""
                background-color: #b71c1c;
                border-radius: 8px;
                border: 2px solid #ff1744;
            """)
            self.lbl_decision.setText("✖ NOT OK (HATALI)")
            self.lbl_decision.setStyleSheet("color: #ffebee; font-weight: bold; font-size: 28px;")

        self.lbl_reason.setText(out.reason)
        self.lbl_time.setText(f"{out.elapsed_ms:.1f} ms")
        self.lbl_confidence.setText(f"%{int(out.overall_confidence * 100)}")

        if out.localization.success:
            self.lbl_locator_info.setText(f"({out.localization.center[0]},{out.localization.center[1]}) | Açı: {out.localization.angle:.1f}°")
        else:
            self.lbl_locator_info.setText("Parça bulunamadı")

        if out.inspection:
            pct = int(min(1.0, out.inspection.anomaly_score) * 100)
            self.bar_anomaly.setValue(pct)
            self.bar_anomaly.setFormat(f"%{pct} (Eşik: %{int(out.inspection.threshold * 100)})")

        subcheck_text = []
        for k, v in out.subchecks.get("details", {}).items():
            sym = "✔" if v else "✖"
            subcheck_text.append(f"{sym} {k}")
        self.lbl_subchecks.setText(" | ".join(subcheck_text) if subcheck_text else "Uygulanamadı")

    def render_current_view(self):
        if self.current_raw_frame is None or self.last_pipeline_output is None:
            return

        out = self.last_pipeline_output
        target_img = None

        if self.view_mode == "raw":
            target_img = out.localization.debug_frame
        elif self.view_mode == "aligned":
            target_img = out.localization.aligned_image if out.localization.aligned_image is not None else self.current_raw_frame
        elif self.view_mode == "heatmap":
            target_img = out.inspection.heatmap if out.inspection else self.current_raw_frame
        else:  # "composite"
            target_img = out.inspection.composite_view if out.inspection else out.localization.debug_frame

        if target_img is None:
            return

        h, w, ch = target_img.shape
        bytes_per_line = ch * w
        rgb_img = cv2.cvtColor(target_img, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)

        scaled_pixmap = pixmap.scaled(
            self.image_display.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_display.setPixmap(scaled_pixmap)

    @Slot()
    def on_confirm_decision(self):
        if not self.last_pipeline_output or self.last_pipeline_output.localization.aligned_image is None:
            return

        out = self.last_pipeline_output
        score = out.inspection.anomaly_score if out.inspection else 0.5
        res = self.learner.process_feedback(
            aligned_image=out.localization.aligned_image,
            model_decision=out.final_decision,
            operator_decision=out.final_decision,
            anomaly_score=score,
            notes=f"Operatör onayladı: {self.current_sample_name}"
        )
        self.txt_learning_log.append(f"[{time.strftime('%H:%M:%S')}] {res['message']}")
        self.update_stats_display()

    @Slot()
    def on_override_decision(self):
        if not self.last_pipeline_output or self.last_pipeline_output.localization.aligned_image is None:
            return

        out = self.last_pipeline_output
        old_decision = out.final_decision
        new_decision = "OK" if old_decision == "NOT OK" else "NOT OK"
        score = out.inspection.anomaly_score if out.inspection else 0.5

        # Update Database row
        self.db.update_feedback(
            inspection_id=self.last_db_id,
            sample_name=self.current_sample_name,
            model_decision=old_decision,
            operator_decision=new_decision,
            notes="Operatör elle düzeltti"
        )

        res = self.learner.process_feedback(
            aligned_image=out.localization.aligned_image,
            model_decision=old_decision,
            operator_decision=new_decision,
            anomaly_score=score,
            notes=f"Operatör müdahalesi: {self.current_sample_name}"
        )

        self.slider_thresh.setValue(int(res["new_threshold"] * 100))
        self.lbl_thresh_val.setText(f"{res['new_threshold']:.2f}")

        self.last_pipeline_output.final_decision = new_decision
        self.last_pipeline_output.is_ok = (new_decision == "OK")
        self.last_pipeline_output.reason = f"Operatör tarafından düzeltildi: {old_decision} -> {new_decision}"
        self.update_decision_card(self.last_pipeline_output)

        self.txt_learning_log.append(f"[{time.strftime('%H:%M:%S')}] 🔥 {res['message']}")
        self.update_stats_display()

        self.network.send_feedback({
            "sample_name": self.current_sample_name,
            "model_decision": old_decision,
            "operator_decision": new_decision,
            "anomaly_score": score,
            "notes": res["message"]
        })

    def on_threshold_changed(self, val: int):
        new_th = val / 100.0
        self.lbl_thresh_val.setText(f"{new_th:.2f}")
        self.pipeline.failure_detector.threshold = new_th

    def toggle_auto_run(self):
        if self.btn_auto_run.isChecked():
            self.btn_auto_run.setText("⏸ Durdur")
            self.btn_auto_run.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
            self.auto_timer.start(1500)
        else:
            self.btn_auto_run.setText("▶ Canlı / Otomatik Akış")
            self.btn_auto_run.setStyleSheet("background-color: #44475a; color: white; font-weight: bold;")
            self.auto_timer.stop()

    def update_stats_display(self):
        stats = self.db.get_statistics()
        bank_len = len(self.pipeline.failure_detector.ok_memory_bank)
        self.lbl_stats_summary.setText(
            f"Toplam: {stats['total']} | OK: {stats['ok_count']} | NOK: {stats['nok_count']} | Doğruluk: %{stats['accuracy_pct']} | OK Havuzu: {bank_len}"
        )

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1f29; }
            QLabel { color: #f8f8f2; }
            QPushButton {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #44475a; }
            QPushButton:checked {
                background-color: #bd93f9;
                color: #282a36;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #44475a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QProgressBar {
                background-color: #282a36;
                border: 1px solid #44475a;
                border-radius: 4px;
                text-align: center;
                color: #f8f8f2;
                font-weight: bold;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #44475a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #bd93f9;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QStatusBar { background-color: #191a21; color: #6272a4; }
        """)
