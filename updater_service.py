# -*- coding: utf-8 -*-
"""
Movie TR AI - In-App Auto-Update System (OTA Update)
Enables 1-click in-app updates directly from Cloud Server / GitHub Releases
without sending manual EXEs to customers.
"""

import os
import sys
import json
import time
import zipfile
import subprocess
import threading
from datetime import datetime
import urllib.request
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QColor

CURRENT_VERSION = "2.6.0"
DEFAULT_SERVER_URLS = [
    "https://movietr-license-bot.onrender.com",
    "http://127.0.0.1:8080"
]

def parse_semver(v_str):
    """Safely convert version string into comparable tuple e.g. '2.6.1' -> (2, 6, 1)."""
    try:
        clean = v_str.lower().replace("v", "").strip()
        parts = []
        for p in clean.split("."):
            digits = "".join([c for c in p if c.isdigit()])
            parts.append(int(digits) if digits else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)

def check_for_updates_sync(server_urls=None, app_name="Movie_TR"):
    """
    Query cloud server for the latest version info.
    Returns: (has_update: bool, info: dict)
    """
    urls = list(server_urls or DEFAULT_SERVER_URLS)
    info = None

    for base in urls:
        if not base:
            continue
        try:
            req_url = f"{base.rstrip('/')}/version?app={app_name}"
            req = urllib.request.Request(
                req_url,
                headers={"User-Agent": f"MovieTR_AutoUpdater/{CURRENT_VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data and "version" in data:
                        info = data
                        break
        except Exception:
            continue

    if not info:
        return False, {
            "version": CURRENT_VERSION,
            "changelog": "មិនអាចភ្ជាប់ទៅកាន់ Update Server បានឡើយ។",
            "download_url": ""
        }

    latest_ver = info.get("version", CURRENT_VERSION)
    latest_tuple = parse_semver(latest_ver)
    current_tuple = parse_semver(CURRENT_VERSION)

    has_update = latest_tuple > current_tuple
    return has_update, info

class DownloadWorker(QThread):
    sig_progress = Signal(int, float, float) # percent, downloaded_mb, total_mb
    sig_finished = Signal(str)               # downloaded_file_path
    sig_error = Signal(str)                  # error_message

    def __init__(self, download_url, dest_dir):
        super().__init__()
        self.download_url = download_url
        self.dest_dir = dest_dir
        self.is_cancelled = False

    def run(self):
        try:
            os.makedirs(self.dest_dir, exist_ok=True)
            # Determine filename from URL or default
            parsed = urlparse(self.download_url)
            base_name = os.path.basename(parsed.path) or "Movie_TR_update.zip"
            if not (base_name.endswith(".zip") or base_name.endswith(".exe")):
                base_name = "Movie_TR_update.zip"

            dest_path = os.path.join(self.dest_dir, base_name)
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MovieTR_Updater"}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 1024 * 128  # 128 KB chunks

                with open(dest_path, "wb") as f:
                    while True:
                        if self.is_cancelled:
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            self.sig_progress.emit(
                                pct,
                                round(downloaded / (1024 * 1024), 1),
                                round(total_size / (1024 * 1024), 1)
                            )
                        else:
                            # Indeterminate size fallback
                            self.sig_progress.emit(
                                50,
                                round(downloaded / (1024 * 1024), 1),
                                0.0
                            )

            self.sig_finished.emit(dest_path)
        except Exception as e:
            self.sig_error.emit(str(e))

class UpdateCenterDialog(QDialog):
    """
    Modern Cyber Glassmorphic Update Center Dialog for Movie TR AI.
    """
    def __init__(self, parent=None, server_urls=None, update_info=None):
        super().__init__(parent)
        self.setWindowTitle("🚀 Movie TR AI - មជ្ឈមណ្ឌលធ្វើបច្ចុប្បន្នភាព (Update Center)")
        self.resize(620, 520)
        self.setMinimumSize(560, 480)
        self.server_urls = server_urls or DEFAULT_SERVER_URLS
        self.update_info = update_info
        self.download_thread = None

        self.init_ui()
        if not self.update_info:
            self.check_update_async()
        else:
            self.display_update_info(self.update_info)

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0b111e;
            }
            QWidget {
                font-family: 'Leelawadee UI', 'Khmer OS Siemreap', 'Segoe UI', sans-serif;
                color: #e2e8f0;
            }
            QFrame#card_panel {
                background: #111a2c;
                border: 1px solid #1e2d4a;
                border-radius: 12px;
            }
            QLabel {
                color: #cbd5e1;
            }
            QTextEdit {
                background-color: #0d1524;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }
            QProgressBar {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                height: 22px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #8b5cf6);
                border-radius: 7px;
            }
            QPushButton#btn_update_now {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #3b82f6);
                color: #050b14;
                font-weight: 900;
                font-size: 14px;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
            }
            QPushButton#btn_update_now:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #60a5fa);
            }
            QPushButton#btn_update_now:disabled {
                background: #1e293b;
                color: #64748b;
            }
            QPushButton#btn_close_dlg {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 9px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btn_close_dlg:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Banner
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 32px;")
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_h = QLabel("Movie TR AI - Update Center")
        lbl_h.setStyleSheet("color: #00e5ff; font-size: 18px; font-weight: 900;")
        lbl_sub = QLabel("ប្រព័ន្ធទាញយក និងដំឡើងជំនាន់ថ្មីដោយស្វ័យប្រវត្តិតាមរយៈ Cloud Server")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        title_box.addWidget(lbl_h)
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        layout.addLayout(header)

        # 2. Main Card Panel
        card = QFrame()
        card.setObjectName("card_panel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(12)

        # Versions info row
        ver_row = QHBoxLayout()
        ver_row.setSpacing(10)

        self.lbl_cur_ver = QLabel(f"ជំនាន់បច្ចុប្បន្ន: <b>v{CURRENT_VERSION}</b>")
        self.lbl_cur_ver.setStyleSheet("background: #0f172a; padding: 6px 12px; border-radius: 8px; border: 1px solid #1e293b; color: #38bdf8;")

        self.lbl_latest_ver = QLabel("ជំនាន់ចុងក្រោយ: <b>កំពុងពិនិត្យ...</b>")
        self.lbl_latest_ver.setStyleSheet("background: #0f172a; padding: 6px 12px; border-radius: 8px; border: 1px solid #1e293b; color: #a855f7;")

        ver_row.addWidget(self.lbl_cur_ver)
        ver_row.addWidget(self.lbl_latest_ver)
        ver_row.addStretch()
        c_layout.addLayout(ver_row)

        # Status text
        self.lbl_status = QLabel("⏳ កំពុងភ្ជាប់ទៅកាន់ Server ដើម្បីពិនិត្យមើល Version ថ្មី...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #f59e0b;")
        c_layout.addWidget(self.lbl_status)

        # Changelog / Release Notes
        lbl_cl = QLabel("📝 កំណត់ត្រាកែលម្អ (Release Notes / Changelog):")
        lbl_cl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        c_layout.addWidget(lbl_cl)

        self.txt_changelog = QTextEdit()
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setPlaceholderText("ព័ត៌មានពីការកែលម្អលើ Version ថ្មីនឹងបង្ហាញនៅទីនេះ...")
        c_layout.addWidget(self.txt_changelog)

        # Progress Section
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        c_layout.addWidget(self.progress_bar)

        self.lbl_progress_detail = QLabel("")
        self.lbl_progress_detail.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.lbl_progress_detail.setAlignment(Qt.AlignCenter)
        self.lbl_progress_detail.setVisible(False)
        c_layout.addWidget(self.lbl_progress_detail)

        layout.addWidget(card)

        # 3. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_check_again = QPushButton("🔄 ពិនិត្យម្តងទៀត")
        self.btn_check_again.setObjectName("btn_close_dlg")
        self.btn_check_again.clicked.connect(self.check_update_async)

        self.btn_update = QPushButton("⚡ ទាញយក & Update ឥឡូវនេះ (Update Now)")
        self.btn_update.setObjectName("btn_update_now")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self.start_download_update)

        self.btn_close = QPushButton("បិទ (Close)")
        self.btn_close.setObjectName("btn_close_dlg")
        self.btn_close.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_check_again)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        btn_row.addWidget(self.btn_update)
        layout.addLayout(btn_row)

    def check_update_async(self):
        self.lbl_status.setText("⏳ កំពុងភ្ជាប់ទៅកាន់ Server ដើម្បីពិនិត្យមើល Version ថ្មី...")
        self.lbl_status.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: bold;")
        self.btn_update.setEnabled(False)
        self.btn_check_again.setEnabled(False)

        def worker():
            has_up, info = check_for_updates_sync(self.server_urls)
            # Switch back to UI thread
            from PySide6.QtCore import QMetaObject, Q_ARG
            self.meta_apply_info(has_up, info)

        threading.Thread(target=worker, daemon=True).start()

    def meta_apply_info(self, has_up, info):
        # Use QMetaObject or timer if needed, or PySide invoke
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.on_check_completed(has_up, info))

    def on_check_completed(self, has_up, info):
        self.btn_check_again.setEnabled(True)
        self.update_info = info
        self.display_update_info(info)

    def display_update_info(self, info):
        latest_ver = info.get("version", CURRENT_VERSION)
        self.lbl_latest_ver.setText(f"ជំនាន់ចុងក្រោយ: <b>v{latest_ver}</b>")

        has_update = parse_semver(latest_ver) > parse_semver(CURRENT_VERSION)
        dl_url = info.get("download_url", "").strip()

        cl_text = info.get("changelog", "").strip() or "✨ ការកែលម្អប្រព័ន្ធទូទៅ និងពង្រឹងសុវត្ថិភាព"
        self.txt_changelog.setPlainText(cl_text)

        if has_update:
            self.lbl_status.setText(f"🎉 រកឃើញកំណែទម្រង់ថ្មីស្រឡាង (v{latest_ver})! អាចធ្វើការ Update បានភ្លាមៗ")
            self.lbl_status.setStyleSheet("color: #34d399; font-size: 13px; font-weight: bold;")
            if dl_url:
                self.btn_update.setEnabled(True)
                self.btn_update.setText(f"⚡ ទាញយក & Update ទៅ v{latest_ver}")
            else:
                self.btn_update.setEnabled(False)
                self.btn_update.setText("⏳ Admin កំពុង Upload File...")
        else:
            self.lbl_status.setText("✅ កម្មវិធីរបស់អ្នកជាជំនាន់ចុងក្រោយបង្អស់ហើយ (Up to date)!")
            self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")
            self.btn_update.setEnabled(False)
            self.btn_update.setText("✅ គ្មាន Update ថ្មីទេ")

    def start_download_update(self):
        if not self.update_info or not self.update_info.get("download_url"):
            QMessageBox.warning(self, "មិនទាន់មាន Link", "មិនទាន់មាន Link សម្រាប់ទាញយក File Update នៅឡើយទេ។ សូមទាក់ទងលោក Admin!")
            return

        dl_url = self.update_info.get("download_url").strip()
        temp_dir = os.path.join(os.getcwd(), "update_temp")

        self.btn_update.setEnabled(False)
        self.btn_check_again.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_progress_detail.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("⏳ កំពុងទាញយកកញ្ចប់ Update ពី Cloud Server...")

        self.download_thread = DownloadWorker(dl_url, temp_dir)
        self.download_thread.sig_progress.connect(self.on_download_progress)
        self.download_thread.sig_finished.connect(self.on_download_finished)
        self.download_thread.sig_error.connect(self.on_download_error)
        self.download_thread.start()

    def on_download_progress(self, pct, downloaded_mb, total_mb):
        self.progress_bar.setValue(pct)
        if total_mb > 0:
            self.lbl_progress_detail.setText(f"ទាញយកបាន: {downloaded_mb} MB / {total_mb} MB ({pct}%)")
        else:
            self.lbl_progress_detail.setText(f"ទាញយកបាន: {downloaded_mb} MB...")

    def on_download_finished(self, file_path):
        self.lbl_status.setText("✅ ទាញយករួចរាល់! កំពុងរៀបចំដំឡើង...")
        self.lbl_status.setStyleSheet("color: #34d399; font-size: 13px; font-weight: bold;")

        # Unpack zip if applicable
        target_exe_path = None
        base_dir = os.getcwd()
        temp_dir = os.path.dirname(file_path)

        if file_path.endswith(".zip"):
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.extractall(temp_dir)
            except Exception as e:
                QMessageBox.critical(self, "Error Extracting", f"មិនអាចពន្លា File Update បានទេ: {e}")
                return

        # Prepare updater.bat
        batch_script = os.path.join(base_dir, "updater.bat")
        batch_content = """@echo off
chcp 65001 >nul
title Movie TR AI - In-App Auto Updater
echo ========================================================
echo   MOVIE TR AI - AUTOMATIC IN-APP UPDATER
echo ========================================================
echo.
echo កំពុងរង់ចាំកម្មវិធី Movie TR បិទដំណើរការជាមុនសិន...
timeout /t 2 /nobreak >nul

:wait_loop
tasklist /fi "imagename eq Movie_TR.exe" 2>nul | find /i "Movie_TR.exe" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo.
echo កំពុងដំឡើង និងជំនួស File ជំនាន់ថ្មី...
if exist "update_temp\Movie_TR.exe" (
    copy /y "update_temp\Movie_TR.exe" "Movie_TR.exe" >nul
)
if exist "update_temp\Movie_TR_Nuitka_Portable\Movie_TR.exe" (
    copy /y "update_temp\Movie_TR_Nuitka_Portable\Movie_TR.exe" "Movie_TR.exe" >nul
)
if exist "update_temp\files" (
    xcopy /y /e /i "update_temp\files\\*" "." >nul
)

echo.
echo កំពុងបើកកម្មវិធី Movie TR ជំនាន់ថ្មីឡើងវិញ...
timeout /t 1 /nobreak >nul
start "" "Movie_TR.exe"

rem Clean up temporary files
rd /s /q "update_temp" >nul 2>nul
del /f /q "%~f0" >nul 2>nul
exit
"""
        with open(batch_script, "w", encoding="utf-8") as f:
            f.write(batch_content)

        QMessageBox.information(
            self,
            "🎉 ទាញយករួចរាល់ (Update Ready)",
            "✅ កញ្ចប់ Update ត្រូវបានទាញយករួចរាល់ជាស្ថាពរ!\n\n"
            "កម្មវិធី Movie TR នឹងបិទខ្លួនឯងមួយភ្លែត ដើម្បីជំនួស File ថ្មី "
            "រួចបើកកម្មវិធីជំនាន់ថ្មីឡើងវិញភ្លាមៗដោយស្វ័យប្រវត្តិ។"
        )

        # Launch detached updater script
        try:
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            flags = CREATE_NO_WINDOW | DETACHED_PROCESS if sys.platform == "win32" else 0
            subprocess.Popen(["cmd.exe", "/c", batch_script], creationflags=flags)
        except Exception:
            subprocess.Popen(["cmd.exe", "/c", batch_script])

        # Close running application cleanly
        QApplication.quit()
        sys.exit(0)

    def on_download_error(self, err_msg):
        self.lbl_status.setText("❌ ការទាញយកបានបរាជ័យ!")
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: bold;")
        self.btn_update.setEnabled(True)
        self.btn_check_again.setEnabled(True)
        QMessageBox.critical(self, "កំហុសពេលទាញយក", f"មិនអាចទាញយកកញ្ចប់ Update បានទេ:\n\n{err_msg}")
