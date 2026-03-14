# -*- coding: utf-8 -*-
"""
Lineage2M Boss Timer v2 - Desktop Application with Resizable Overlay
Uses existing database schema: kill_time + interval
Read-only mode with auto-refresh every 1 minute
"""

import sys
import os
import threading
import platform
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QSizeGrip, QMessageBox,
    QDialog, QLineEdit, QDialogButtonBox, QProgressDialog, QSlider
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette

import requests

# Use winsound for Windows audio
WINSOUND_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import winsound
        WINSOUND_AVAILABLE = True
    except ImportError:
        pass

from config import (
    APP_TITLE, APP_VERSION, WARNING_MINUTES_YELLOW, WARNING_MINUTES_RED,
    OVERLAY_OPACITY, WINDOW_WIDTH, WINDOW_HEIGHT, OVERLAY_MIN_WIDTH, OVERLAY_MIN_HEIGHT,
    GMT_PLUS_7
)
from database import db

# Constants
SPAWN_DISPLAY_SECONDS = 180  # 3 minutes before moving to bottom
POLLING_INTERVAL_MS = 60000  # 1 minute polling interval
PIN_CHECK_INTERVAL_MS = 300000  # 5 minutes PIN validation interval
UPDATE_CHECK_INTERVAL_MS = 600000  # 10 minutes update check interval

# GitHub repository for updates
GITHUB_REPO = "datturz/bot-overlay"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class UpdateChecker(QThread):
    """Background thread to check for updates"""
    update_available = pyqtSignal(str, str)  # version, download_url
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            print(f"Fetching: {GITHUB_API_URL}")
            response = requests.get(GITHUB_API_URL, timeout=10)
            print(f"Response status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                print(f"Latest version on GitHub: {latest_version}")
                print(f"Current version: {self.current_version}")

                # Find Windows executable in assets
                download_url = None
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        print(f"Found exe: {asset.get('name')}")
                        break

                if latest_version and self._is_newer(latest_version):
                    print(f"Update available! {self.current_version} -> {latest_version}")
                    self.update_available.emit(latest_version, download_url or "")
                else:
                    print("No update needed")
                    self.no_update.emit()
            else:
                print(f"HTTP error: {response.status_code}")
                self.error.emit(f"HTTP {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")
            self.error.emit(str(e))

    def _is_newer(self, latest: str) -> bool:
        """Compare versions (e.g., 2.0.0 vs 2.1.0)"""
        try:
            current_parts = [int(x) for x in self.current_version.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            return latest_parts > current_parts
        except:
            return False


class UpdateDownloader(QThread):
    """Background thread to download update"""
    progress = pyqtSignal(int)  # percentage
    finished = pyqtSignal(str)  # downloaded file path
    error = pyqtSignal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            # Download to temp file
            response = requests.get(self.download_url, stream=True, timeout=60)
            total_size = int(response.headers.get('content-length', 0))

            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "L2M_BossTimer_update.exe")

            downloaded = 0
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)

            self.finished.emit(temp_file)
        except Exception as e:
            self.error.emit(str(e))


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# Boss type colors
TYPE_COLORS = {
    "ours": "#00ff00",      # Green
    "invasion": "#ff6600",  # Orange
}


class PinDialog(QDialog):
    """PIN validation dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PIN Validation")
        self.setFixedSize(300, 150)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e8e8e8;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #16213e;
                color: #e8e8e8;
                border: 1px solid #0f3460;
                border-radius: 5px;
                padding: 8px;
                font-size: 16px;
            }
            QLineEdit:focus {
                border: 1px solid #e94560;
            }
            QPushButton {
                background-color: #e94560;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Label
        label = QLabel("Enter PIN to access:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # PIN input
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("Enter PIN")
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.returnPressed.connect(self.accept)
        layout.addWidget(self.pin_input)

        # Submit button
        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.accept)
        layout.addWidget(submit_btn)

    def get_pin(self) -> str:
        return self.pin_input.text()


class BossTimerWidget(QFrame):
    """Widget for displaying a single boss timer (read-only)"""

    def __init__(self, boss_data: Dict, parent=None):
        super().__init__(parent)
        self.boss_data = boss_data
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            BossTimerWidget {
                background-color: rgba(22, 33, 62, 200);
                border-radius: 6px;
                margin: 1px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        # Type indicator
        boss_type = self.boss_data.get("type", "ours")
        type_color = TYPE_COLORS.get(boss_type, "#00ff00")
        type_label = QLabel(boss_type[:3].upper())
        type_label.setFixedWidth(35)
        type_label.setAlignment(Qt.AlignCenter)
        type_label.setStyleSheet(f"""
            background-color: {type_color};
            color: #000;
            font-weight: bold;
            font-size: 10px;
            border-radius: 3px;
            padding: 2px;
        """)
        layout.addWidget(type_label)

        # Boss info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)

        name_label = QLabel(self.boss_data.get("name", "Unknown"))
        name_label.setStyleSheet("color: #ffff00; font-weight: bold; font-size: 13px;")
        info_layout.addWidget(name_label)

        # Show percentage and interval
        percentage = self.boss_data.get("percentage", 100)
        interval = self.boss_data.get("interval", 0)
        detail_label = QLabel(f"{percentage}% | {interval}h respawn")
        detail_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        info_layout.addWidget(detail_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Spawn time display (actual time HH:MM)
        self.spawn_time_label = QLabel("--:--")
        self.spawn_time_label.setStyleSheet("""
            color: #00ffff;
            font-size: 12px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
        """)
        self.spawn_time_label.setFixedWidth(45)
        self.spawn_time_label.setAlignment(Qt.AlignCenter)
        self.spawn_time_label.setToolTip("Spawn Time")
        layout.addWidget(self.spawn_time_label)

        # Countdown timer display
        self.timer_label = QLabel("--:--:--")
        self.timer_label.setStyleSheet("""
            color: #44ff44;
            font-size: 14px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
        """)
        self.timer_label.setFixedWidth(70)
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setToolTip("Countdown")
        layout.addWidget(self.timer_label)

        self.update_timer()

    def update_timer(self):
        """Update the countdown timer display"""
        kill_time = self.boss_data.get("kill_time", "00:00")
        interval = self.boss_data.get("interval", 8)

        if not kill_time:
            self.spawn_time_label.setText("--:--")
            self.timer_label.setText("--:--:--")
            self.timer_label.setStyleSheet("""
                color: #aaaaaa;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Consolas', monospace;
            """)
            return

        # Calculate spawn time and countdown
        spawn_time = db.calculate_spawn_time(kill_time, interval)
        total_seconds = db.calculate_countdown_seconds(kill_time, interval)

        # Update spawn time label (HH:MM in GMT+7)
        spawn_time_str = spawn_time.strftime("%H:%M")
        self.spawn_time_label.setText(spawn_time_str)

        if total_seconds <= 0:
            # Boss should have spawned
            self.timer_label.setText("SPAWN!")
            self.timer_label.setStyleSheet("""
                color: #ff4444;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Consolas', monospace;
                background-color: rgba(85, 0, 0, 150);
                border-radius: 3px;
            """)
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            # Color based on time remaining
            minutes_remaining = total_seconds / 60
            if minutes_remaining <= WARNING_MINUTES_RED:
                color = "#ff4444"  # Red
            elif minutes_remaining <= WARNING_MINUTES_YELLOW:
                color = "#ffff44"  # Yellow
            else:
                color = "#44ff44"  # Green

            self.timer_label.setStyleSheet(f"""
                color: {color};
                font-size: 14px;
                font-weight: bold;
                font-family: 'Consolas', monospace;
            """)


class MainWindow(QMainWindow):
    """Main application window with resizable overlay"""

    def __init__(self, user_pin: str):
        super().__init__()
        self.overlay_mode = False
        self.boss_widgets: List[BossTimerWidget] = []
        self.dragging = False
        self.drag_position = QPoint()
        self.current_filter = "all"
        self.user_pin = user_pin  # Store PIN for periodic validation

        # Sound notification tracking
        self.announced_bosses: Dict[int, Set[int]] = {}
        self.sound_queue: List[tuple] = []  # Queue for sound messages
        self.sound_lock = threading.Lock()
        self.sound_thread_running = False
        self.sound_enabled = True
        self.sound_volume = 100  # Volume 0-100

        # Sound file paths
        self.sound_files = {
            "ours_5min": get_resource_path("sound/boss_5min.wav"),
            "ours_1min": get_resource_path("sound/boss_1min.wav"),
            "ours_spawn": get_resource_path("sound/boss_spawn.wav"),
            "invasion_5min": get_resource_path("sound/invasion_5min.wav"),
            "invasion_1min": get_resource_path("sound/invasion_1min.wav"),
            "invasion_spawn": get_resource_path("sound/invasion_spawn.wav"),
        }

        # Update tracking
        self.latest_version = None
        self.download_url = None
        self.update_checker = None
        self.update_downloader = None

        self.setup_ui()
        self.setup_timer()
        self.refresh_bosses()
        self.check_for_updates()  # Check on startup

    def setup_ui(self):
        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.setMinimumSize(OVERLAY_MIN_WIDTH, OVERLAY_MIN_HEIGHT)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Main style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #16213e;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #0f3460;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Filter bar
        filter_bar = self.create_filter_bar()
        main_layout.addWidget(filter_bar)

        # Boss list (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.boss_container = QWidget()
        self.boss_layout = QVBoxLayout(self.boss_container)
        self.boss_layout.setContentsMargins(0, 0, 0, 0)
        self.boss_layout.setSpacing(3)
        self.boss_layout.addStretch()

        scroll.setWidget(self.boss_container)
        main_layout.addWidget(scroll)

        # Footer with resize grip
        footer = self.create_footer()
        main_layout.addWidget(footer)

    def create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: rgba(22, 33, 62, 200);
                border-radius: 6px;
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)

        # Title
        title = QLabel(APP_TITLE)
        title.setStyleSheet("color: #e94560; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # Current time (GMT+7)
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #00ffff; font-size: 11px;")
        layout.addWidget(self.time_label)

        # Update button (hidden by default)
        self.update_btn = QPushButton("Update!")
        self.update_btn.setFixedSize(55, 22)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: #fff;
                border: none;
                border-radius: 3px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff8833;
            }
        """)
        self.update_btn.clicked.connect(self.do_update)
        self.update_btn.hide()  # Hidden until update available
        layout.addWidget(self.update_btn)

        # Sound toggle button
        self.sound_btn = QPushButton("Sound")
        self.sound_btn.setFixedSize(50, 22)
        self.sound_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aa00;
                color: #fff;
                border: none;
                border-radius: 3px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00cc00;
            }
        """)
        self.sound_btn.clicked.connect(self.toggle_sound)
        layout.addWidget(self.sound_btn)

        # Volume slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setFixedSize(60, 20)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #0f3460;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #e94560;
                width: 12px;
                margin: -3px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #00aa00;
                border-radius: 3px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        layout.addWidget(self.volume_slider)

        # Volume label
        self.volume_label = QLabel("100%")
        self.volume_label.setFixedWidth(30)
        self.volume_label.setStyleSheet("color: #aaa; font-size: 9px;")
        layout.addWidget(self.volume_label)

        # Test sound button
        self.test_sound_btn = QPushButton("🔊")
        self.test_sound_btn.setFixedSize(22, 22)
        self.test_sound_btn.setToolTip("Test Sound")
        self.test_sound_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: #fff;
                border: none;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e94560;
            }
        """)
        self.test_sound_btn.clicked.connect(self.test_sound)
        layout.addWidget(self.test_sound_btn)

        # Overlay toggle button
        self.overlay_btn = QPushButton("Overlay")
        self.overlay_btn.setFixedSize(50, 22)
        self.overlay_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: #eee;
                border: none;
                border-radius: 3px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #e94560;
            }
        """)
        self.overlay_btn.clicked.connect(self.toggle_overlay_mode)
        layout.addWidget(self.overlay_btn)

        return header

    def create_filter_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Filter buttons
        self.filter_buttons = {}
        for filter_type, label, color in [("all", "ALL", "#e94560"), ("ours", "OURS", "#00ff00"), ("invasion", "INV", "#ff6600"), ("ffa", "FFA", "#9966ff")]:
            btn = QPushButton(label)
            btn.setFixedSize(45, 20)
            btn.setCheckable(True)
            btn.setChecked(filter_type == "all")

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #16213e;
                    color: {color};
                    border: 1px solid {color};
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    background-color: {color};
                    color: #000;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: #000;
                }}
            """)
            btn.clicked.connect(lambda checked, f=filter_type: self.filter_bosses(f))
            layout.addWidget(btn)
            self.filter_buttons[filter_type] = btn

        layout.addStretch()

        # Boss count
        self.count_label = QLabel("0 bosses")
        self.count_label.setStyleSheet("color: #888; font-size: 9px;")
        layout.addWidget(self.count_label)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(50, 20)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: #eee;
                border: none;
                border-radius: 3px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #16213e;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_bosses)
        layout.addWidget(refresh_btn)

        return bar

    def create_footer(self) -> QWidget:
        footer = QFrame()
        footer.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 2, 0, 0)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 9px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Size grip for resizing
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.size_grip)

        return footer

    def setup_timer(self):
        """Setup timer for updating countdowns"""
        # Update display every second
        self.update_timer_obj = QTimer(self)
        self.update_timer_obj.timeout.connect(self.update_all_timers)
        self.update_timer_obj.start(1000)

        # Auto-refresh from database every 1 minute
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_bosses)
        self.refresh_timer.start(POLLING_INTERVAL_MS)

        # PIN validation every 5 minutes
        self.pin_check_timer = QTimer(self)
        self.pin_check_timer.timeout.connect(self.validate_pin_periodic)
        self.pin_check_timer.start(PIN_CHECK_INTERVAL_MS)

        # Update check every 10 minutes
        self.update_check_timer = QTimer(self)
        self.update_check_timer.timeout.connect(self.check_for_updates)
        self.update_check_timer.start(UPDATE_CHECK_INTERVAL_MS)

    def validate_pin_periodic(self):
        """Validate PIN periodically - kick user if PIN is no longer valid"""
        if not db.validate_pin(self.user_pin):
            self.update_timer_obj.stop()
            self.refresh_timer.stop()
            self.pin_check_timer.stop()
            QMessageBox.critical(
                self,
                "Session Expired",
                "Your PIN is no longer valid.\nThe application will now close."
            )
            self.close()
            QApplication.quit()

    def check_for_updates(self):
        """Check GitHub for new version"""
        from config import APP_VERSION
        print(f"Checking for updates... Current version: {APP_VERSION}")
        self.update_checker = UpdateChecker(APP_VERSION)
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(lambda: print("No update available"))
        self.update_checker.error.connect(lambda e: print(f"Update check error: {e}"))
        self.update_checker.start()

    def on_update_available(self, version: str, download_url: str):
        """Called when new version is found"""
        self.latest_version = version
        self.download_url = download_url
        self.update_btn.setText(f"v{version}")
        self.update_btn.setToolTip(f"Update available: v{version}\nClick to download and install")
        self.update_btn.show()

    def do_update(self):
        """Download and install update"""
        if not self.download_url:
            QMessageBox.warning(self, "Update Error", "No download URL available")
            return

        reply = QMessageBox.question(
            self,
            "Update Available",
            f"Download and install v{self.latest_version}?\n\nThe application will restart after update.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Show progress dialog
        self.progress_dialog = QProgressDialog("Downloading update...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Updating")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.show()

        # Start download
        self.update_downloader = UpdateDownloader(self.download_url)
        self.update_downloader.progress.connect(self.on_download_progress)
        self.update_downloader.finished.connect(self.on_download_finished)
        self.update_downloader.error.connect(self.on_download_error)
        self.update_downloader.start()

    def on_download_progress(self, percent: int):
        """Update progress bar"""
        self.progress_dialog.setValue(percent)

    def on_download_finished(self, temp_file: str):
        """Download complete - install update"""
        self.progress_dialog.close()

        try:
            # Get current executable path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                QMessageBox.information(self, "Update", "Update downloaded. Please restart in production mode.")
                return

            # Create batch script to replace exe and restart
            batch_content = f'''@echo off
timeout /t 2 /nobreak > nul
copy /y "{temp_file}" "{current_exe}"
del "{temp_file}"
start "" "{current_exe}"
del "%~f0"
'''
            batch_file = os.path.join(tempfile.gettempdir(), "update_l2m.bat")
            with open(batch_file, 'w') as f:
                f.write(batch_content)

            # Run batch and exit
            subprocess.Popen(['cmd', '/c', batch_file], shell=True)
            QApplication.quit()

        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to install update:\n{e}")

    def on_download_error(self, error: str):
        """Download failed"""
        self.progress_dialog.close()
        QMessageBox.critical(self, "Download Error", f"Failed to download update:\n{error}")

    def refresh_bosses(self):
        """Refresh boss list from database"""
        # Clear existing widgets
        for widget in self.boss_widgets:
            widget.deleteLater()
        self.boss_widgets.clear()

        # Remove stretch
        while self.boss_layout.count() > 0:
            item = self.boss_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get bosses from database
        if self.current_filter == "all":
            bosses = db.get_all_bosses()
        else:
            bosses = db.get_bosses_by_type(self.current_filter)

        # Sort by countdown (nearest spawn first, just spawned at top, old spawns at bottom)
        def sort_key(b):
            kill_time = b.get("kill_time", "00:00")
            interval = b.get("interval", 8)
            if not kill_time:
                return float('inf')
            countdown = db.calculate_countdown_seconds(kill_time, interval)
            # If just spawned (within 3 minutes), keep at top
            if -SPAWN_DISPLAY_SECONDS <= countdown <= 0:
                return countdown  # Just spawned stays at top (negative values first)
            # If spawned more than 3 min ago, put at bottom
            if countdown < -SPAWN_DISPLAY_SECONDS:
                return float('inf')
            return countdown  # Upcoming spawns sorted by nearest first

        bosses.sort(key=sort_key)

        # Create widgets
        for boss in bosses:
            widget = BossTimerWidget(boss, self)
            self.boss_layout.addWidget(widget)
            self.boss_widgets.append(widget)

        self.boss_layout.addStretch()

        # Update status
        self.count_label.setText(f"{len(self.boss_widgets)} bosses")
        self.status_label.setText(f"Updated: {datetime.now(GMT_PLUS_7).strftime('%H:%M:%S')}")

    def update_all_timers(self):
        """Update all timer displays and check for sound notifications"""
        # Update current time display
        self.time_label.setText(f"GMT+7: {datetime.now(GMT_PLUS_7).strftime('%H:%M:%S')}")

        for widget in self.boss_widgets:
            widget.update_timer()

        # Check for sound notifications
        if self.sound_enabled:
            self.check_boss_notifications()

    def check_boss_notifications(self):
        """Check if any boss needs sound notification"""
        for widget in self.boss_widgets:
            boss = widget.boss_data
            boss_id = boss.get("id")
            boss_name = boss.get("name", "Unknown")
            boss_type = boss.get("type", "ours")
            kill_time = boss.get("kill_time")
            interval = boss.get("interval", 8)

            if not kill_time or not boss_id:
                continue

            # Calculate countdown
            total_seconds = db.calculate_countdown_seconds(kill_time, interval)

            # Initialize tracking for this boss if not exists
            if boss_id not in self.announced_bosses:
                self.announced_bosses[boss_id] = set()

            # Check if boss has spawned
            if total_seconds <= 0:
                if 0 not in self.announced_bosses[boss_id]:
                    self.announced_bosses[boss_id].add(0)
                    self.play_sound(boss_type, "spawn")
                continue

            # Announce at 5 minutes (between 4:01 and 5:00)
            if 240 < total_seconds <= 300 and 5 not in self.announced_bosses[boss_id]:
                self.announced_bosses[boss_id].add(5)
                self.play_sound(boss_type, "5min")
            # Announce at 1 minute (between 0:01 and 1:00)
            elif 0 < total_seconds <= 60 and 1 not in self.announced_bosses[boss_id]:
                self.announced_bosses[boss_id].add(1)
                self.play_sound(boss_type, "1min")

    def play_sound(self, boss_type: str, alert_type: str):
        """Play sound file in background thread"""
        sound_key = f"{boss_type}_{alert_type}"
        sound_file = self.sound_files.get(sound_key)

        if not sound_file or not os.path.exists(sound_file):
            # Fallback to beep
            if WINSOUND_AVAILABLE:
                threading.Thread(target=self._play_beep, args=(alert_type == "spawn",), daemon=True).start()
            return

        # Play WAV file in background thread
        threading.Thread(target=self._play_wav, args=(sound_file,), daemon=True).start()

    def _play_wav(self, sound_file: str):
        """Play WAV file using winsound (Windows) or afplay (macOS)"""
        try:
            if WINSOUND_AVAILABLE:
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif platform.system() == "Darwin":
                # macOS: use afplay command
                subprocess.Popen(["afplay", sound_file],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                print("Audio not supported on this platform")
        except Exception as e:
            print(f"Sound error: {e}")

    def _play_beep(self, is_spawn: bool):
        """Play beep sound as fallback"""
        try:
            if WINSOUND_AVAILABLE:
                if is_spawn:
                    for _ in range(3):
                        winsound.Beep(1000, 200)
                        winsound.Beep(1500, 200)
                else:
                    winsound.Beep(800, 300)
                    winsound.Beep(1000, 300)
            elif platform.system() == "Darwin":
                # macOS: use system beep via osascript
                import subprocess
                beep_count = 3 if is_spawn else 1
                for _ in range(beep_count):
                    subprocess.run(["osascript", "-e", "beep"], check=False)
        except Exception as e:
            print(f"Beep error: {e}")

    def filter_bosses(self, filter_type: str):
        """Filter bosses by type"""
        self.current_filter = filter_type
        for f_type, btn in self.filter_buttons.items():
            btn.setChecked(f_type == filter_type)
        self.refresh_bosses()

    def toggle_sound(self):
        """Toggle sound notifications on/off"""
        self.sound_enabled = not self.sound_enabled

        if self.sound_enabled:
            self.sound_btn.setText("Sound")
            self.sound_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00aa00;
                    color: #fff;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #00cc00;
                }
            """)
        else:
            self.sound_btn.setText("Mute")
            self.sound_btn.setStyleSheet("""
                QPushButton {
                    background-color: #aa0000;
                    color: #fff;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #cc0000;
                }
            """)
            self.announced_bosses.clear()

    def set_volume(self, value: int):
        """Set sound volume (0-100)"""
        self.sound_volume = value
        self.volume_label.setText(f"{value}%")

        # Mute if volume is 0
        if value == 0 and self.sound_enabled:
            self.sound_enabled = False
            self.sound_btn.setText("Mute")
            self.sound_btn.setStyleSheet("""
                QPushButton {
                    background-color: #aa0000;
                    color: #fff;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }
            """)
        elif value > 0 and not self.sound_enabled:
            self.sound_enabled = True
            self.sound_btn.setText("Sound")
            self.sound_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00aa00;
                    color: #fff;
                    border: none;
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }
            """)

    def test_sound(self):
        """Play a test sound to check volume"""
        if not self.sound_enabled:
            return

        # Try to play boss_spawn.wav as test
        test_file = self.sound_files.get("ours_spawn")
        if test_file and os.path.exists(test_file):
            threading.Thread(target=self._play_wav, args=(test_file,), daemon=True).start()
        else:
            # Fallback to beep
            self._play_beep(False)

    def toggle_overlay_mode(self):
        """Toggle between normal window and overlay mode"""
        self.overlay_mode = not self.overlay_mode

        if self.overlay_mode:
            # Enable overlay mode - resizable, transparent, always on top
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
            self.setWindowOpacity(OVERLAY_OPACITY)
            self.overlay_btn.setText("Window")
        else:
            # Disable overlay mode
            self.setWindowFlags(Qt.Window)
            self.setWindowOpacity(1.0)
            self.overlay_btn.setText("Overlay")

        self.show()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging in overlay mode"""
        if self.overlay_mode and event.button() == Qt.LeftButton:
            # Only drag from header area
            if event.pos().y() < 50:
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging in overlay mode"""
        if self.overlay_mode and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.dragging = False

    def closeEvent(self, event):
        """Handle window close"""
        self.update_timer_obj.stop()
        self.refresh_timer.stop()
        self.pin_check_timer.stop()
        self.update_check_timer.stop()
        event.accept()


def validate_pin(app) -> Optional[str]:
    """Show PIN dialog and validate against Supabase. Returns PIN if valid, None otherwise."""
    max_attempts = 3

    for attempt in range(max_attempts):
        dialog = PinDialog()
        if dialog.exec_() != QDialog.Accepted:
            return None

        pin = dialog.get_pin()
        if not pin:
            QMessageBox.warning(None, "Error", "Please enter a PIN")
            continue

        # Validate PIN against Supabase
        if db.validate_pin(pin):
            return pin  # Return the valid PIN
        else:
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                QMessageBox.warning(
                    None,
                    "Invalid PIN",
                    f"Invalid PIN. {remaining} attempts remaining."
                )
            else:
                QMessageBox.critical(
                    None,
                    "Access Denied",
                    "Too many invalid attempts. Application will close."
                )

    return None


def main():
    # Create application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 26, 46))
    palette.setColor(QPalette.WindowText, QColor(238, 238, 238))
    palette.setColor(QPalette.Base, QColor(22, 33, 62))
    palette.setColor(QPalette.AlternateBase, QColor(15, 52, 96))
    palette.setColor(QPalette.Text, QColor(238, 238, 238))
    palette.setColor(QPalette.Button, QColor(15, 52, 96))
    palette.setColor(QPalette.ButtonText, QColor(238, 238, 238))
    palette.setColor(QPalette.Highlight, QColor(233, 69, 96))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    # Connect to database
    print("Connecting to Supabase...")
    if not db.connect():
        QMessageBox.critical(
            None,
            "Connection Error",
            "Failed to connect to Supabase.\n\n"
            "Please check:\n"
            "1. .env file exists with SUPABASE_URL and SUPABASE_KEY\n"
            "2. Internet connection is available\n"
            "3. Supabase project is active"
        )
        sys.exit(1)

    print("Connected to Supabase!")

    # Validate PIN
    user_pin = validate_pin(app)
    if not user_pin:
        sys.exit(0)

    # Create and show main window with PIN for periodic validation
    window = MainWindow(user_pin)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
