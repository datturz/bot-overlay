# -*- coding: utf-8 -*-
"""
Lineage2M Boss Timer v2 - Desktop Application with Resizable Overlay
Uses existing database schema: kill_time + interval
Read-only mode with auto-refresh every 10 seconds
"""

import sys
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QSizeGrip, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QColor, QPalette

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("Warning: pyttsx3 not installed. Sound notifications disabled.")

from config import (
    APP_TITLE, APP_VERSION, WARNING_MINUTES_YELLOW, WARNING_MINUTES_RED,
    OVERLAY_OPACITY, WINDOW_WIDTH, WINDOW_HEIGHT, OVERLAY_MIN_WIDTH, OVERLAY_MIN_HEIGHT,
    GMT_PLUS_7
)
from database import db


# Boss type colors
TYPE_COLORS = {
    "ours": "#00ff00",      # Green
    "invasion": "#ff6600",  # Orange
}


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

    def __init__(self):
        super().__init__()
        self.overlay_mode = False
        self.boss_widgets: List[BossTimerWidget] = []
        self.dragging = False
        self.drag_position = QPoint()
        self.current_filter = "all"

        # Sound notification tracking
        self.announced_bosses: Dict[int, Set[int]] = {}
        self.tts_engine = None
        self.tts_queue: List[str] = []  # Queue for TTS messages
        self.tts_lock = threading.Lock()
        self.tts_thread_running = False
        self.sound_enabled = True
        self.volume = 1.0  # Volume 0.0 - 1.0

        # Initialize TTS engine
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', self.volume)
            except Exception as e:
                print(f"Failed to initialize TTS: {e}")
                self.tts_engine = None

        self.setup_ui()
        self.setup_timer()
        self.refresh_bosses()

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

        # Volume down button
        vol_down_btn = QPushButton("-")
        vol_down_btn.setFixedSize(20, 22)
        vol_down_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: #fff;
                border: none;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16213e;
            }
        """)
        vol_down_btn.clicked.connect(self.volume_down)
        layout.addWidget(vol_down_btn)

        # Volume label
        self.vol_label = QLabel("100%")
        self.vol_label.setFixedWidth(35)
        self.vol_label.setAlignment(Qt.AlignCenter)
        self.vol_label.setStyleSheet("color: #aaa; font-size: 9px;")
        layout.addWidget(self.vol_label)

        # Volume up button
        vol_up_btn = QPushButton("+")
        vol_up_btn.setFixedSize(20, 22)
        vol_up_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460;
                color: #fff;
                border: none;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16213e;
            }
        """)
        vol_up_btn.clicked.connect(self.volume_up)
        layout.addWidget(vol_up_btn)

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

        # Auto-refresh from database every 10 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_bosses)
        self.refresh_timer.start(10000)

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
            # If just spawned (within 1 minute, countdown between -60 and 0), keep at top
            if -60 <= countdown <= 0:
                return countdown  # Just spawned stays at top (negative values first)
            # If spawned more than 1 min ago (countdown < -60), put at bottom
            if countdown < -60:
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
        if self.sound_enabled and self.tts_engine:
            self.check_boss_notifications()

    def check_boss_notifications(self):
        """Check if any boss needs sound notification"""
        for widget in self.boss_widgets:
            boss = widget.boss_data
            boss_id = boss.get("id")
            boss_name = boss.get("name", "Unknown")
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
                    self.announce_boss_spawned(boss_name)
                continue

            # Announce at 5 minutes (between 4:01 and 5:00)
            if 240 < total_seconds <= 300 and 5 not in self.announced_bosses[boss_id]:
                self.announced_bosses[boss_id].add(5)
                self.announce_boss(boss_name, 5)
            # Announce at 1 minute (between 0:01 and 1:00)
            elif 0 < total_seconds <= 60 and 1 not in self.announced_bosses[boss_id]:
                self.announced_bosses[boss_id].add(1)
                self.announce_boss(boss_name, 1)

    def queue_announcement(self, text: str):
        """Add announcement to queue and start processing if not already running"""
        with self.tts_lock:
            self.tts_queue.append(text)
            if not self.tts_thread_running:
                self.tts_thread_running = True
                thread = threading.Thread(target=self.process_tts_queue, daemon=True)
                thread.start()

    def process_tts_queue(self):
        """Process all queued announcements sequentially"""
        while True:
            with self.tts_lock:
                if not self.tts_queue:
                    self.tts_thread_running = False
                    return
                text = self.tts_queue.pop(0)

            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"TTS error: {e}")

    def announce_boss(self, boss_name: str, minutes: int):
        """Announce boss respawn via TTS"""
        if minutes == 1:
            text = f"{boss_name} will respawn in 1 minute!"
        else:
            text = f"{boss_name} will respawn in {minutes} minutes!"
        self.queue_announcement(text)

    def announce_boss_spawned(self, boss_name: str):
        """Announce boss has spawned via TTS"""
        text = f"{boss_name} already respawn, lets go!"
        self.queue_announcement(text)

    def filter_bosses(self, filter_type: str):
        """Filter bosses by type"""
        self.current_filter = filter_type
        for f_type, btn in self.filter_buttons.items():
            btn.setChecked(f_type == filter_type)
        self.refresh_bosses()

    def volume_up(self):
        """Increase volume by 10%"""
        self.volume = min(1.0, self.volume + 0.1)
        self.update_volume()

    def volume_down(self):
        """Decrease volume by 10%"""
        self.volume = max(0.0, self.volume - 0.1)
        self.update_volume()

    def update_volume(self):
        """Update TTS volume and label"""
        if self.tts_engine:
            self.tts_engine.setProperty('volume', self.volume)
        self.vol_label.setText(f"{int(self.volume * 100)}%")

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
        event.accept()


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

    # Create and show main window (no login required - read only)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
