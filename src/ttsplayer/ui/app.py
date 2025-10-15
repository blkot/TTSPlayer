"""PySide6 application wiring for TTSPlayer."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

import math

from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ttsplayer.audio.player import TrackPlayer
from ttsplayer.models import Track


class TrackCardWidget(QFrame):
    """Card component that displays transcript text with a background progress overlay."""

    def __init__(self, track: Track, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._progress: float = 0.0
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("trackCard")
        self.setProperty("selected", False)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        transcript_text = track.transcript or "(No transcript available)"
        self.transcript_label = QLabel(transcript_text, self)
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.transcript_label.setObjectName("trackTranscript")
        layout.addWidget(self.transcript_label)

        if not track.transcript:
            fallback = QLabel(track.title, self)
            fallback.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            fallback.setWordWrap(True)
            fallback.setObjectName("trackFallbackTitle")
            layout.addWidget(fallback)

        layout.addStretch(1)

    def set_progress(self, fraction: float) -> None:
        clamped = max(0.0, min(fraction, 1.0))
        if math.isclose(clamped, self._progress, rel_tol=1e-3):
            return
        self._progress = clamped
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._progress <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        progress_width = rect.width() * self._progress
        if progress_width <= 0:
            painter.end()
            return

        progress_rect = QRectF(rect.x(), rect.y(), progress_width, rect.height())
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 16, 16)
        painter.setClipPath(path)
        painter.fillRect(progress_rect, QColor("#96eb9f"))
        painter.end()


class TrackListWindow(QMainWindow):
    """Main window displaying available tracks and their transcripts."""

    def __init__(self, tracks: Sequence[Track], player: TrackPlayer) -> None:
        super().__init__()
        self._player = player
        self._suppress_autoplay = True
        self._card_widgets: dict[str, TrackCardWidget] = {}
        self._current_track_id: str | None = None
        self._slider_is_dragging = False
        self._slider_scale = 1000
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(100)
        self._progress_timer.timeout.connect(self._refresh_progress)
        self.setWindowTitle("TTSPlayer")
        self._build_ui(tracks)

    def _build_ui(self, tracks: Sequence[Track]) -> None:
        central = QWidget(self)
        central.setObjectName("mainContainer")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Audio Library", central)
        title.setObjectName("windowTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        subtitle = QLabel("Select a card to play its audio instantly.", central)
        subtitle.setObjectName("windowSubtitle")
        subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.track_list = QListWidget(central)
        self.track_list.setSelectionMode(QListWidget.SingleSelection)
        self.track_list.setSpacing(12)
        self.track_list.setUniformItemSizes(False)
        self.track_list.setResizeMode(QListView.Adjust)
        self.track_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.track_list.setObjectName("trackList")

        for track in tracks:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, track.identifier)
            card = TrackCardWidget(track, parent=central)
            size_hint = card.sizeHint()
            size_hint.setHeight(size_hint.height() + 12)
            item.setSizeHint(size_hint)
            self.track_list.addItem(item)
            self.track_list.setItemWidget(item, card)
            self._card_widgets[track.identifier] = card

        self.track_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.track_list.itemDoubleClicked.connect(self._play_selected)

        self.replay_button = QPushButton("Replay", central)
        self.replay_button.clicked.connect(self._play_selected)
        self.replay_button.setEnabled(False)

        self.stop_button = QPushButton("Stop", central)
        self.stop_button.clicked.connect(self._stop_playback)
        self.stop_button.setEnabled(False)

        self.elapsed_label = QLabel("0:00", central)
        self.elapsed_label.setObjectName("timeLabel")
        self.duration_label = QLabel("0:00", central)
        self.duration_label.setObjectName("timeLabel")

        self.progress_slider = QSlider(Qt.Horizontal, central)
        self.progress_slider.setObjectName("progressSlider")
        self.progress_slider.setRange(0, self._slider_scale)
        self.progress_slider.setSingleStep(1)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.elapsed_label)
        controls.addWidget(self.progress_slider, 1)
        controls.addWidget(self.duration_label)
        controls.addWidget(self.replay_button)
        controls.addWidget(self.stop_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.track_list)
        layout.addLayout(controls)

        central.setLayout(layout)
        self.setCentralWidget(central)
        self._apply_styles()
        if self.track_list.count():
            self.track_list.setCurrentRow(0)
            self._update_card_selection_states()
        self._suppress_autoplay = False

    def _on_selection_changed(self) -> None:
        identifier = self._current_identifier()
        has_selection = identifier is not None
        self.replay_button.setEnabled(has_selection)
        self.stop_button.setEnabled(has_selection)
        if not has_selection:
            self._reset_progress_ui(clear_current=True)
            self._update_card_selection_states()
            return

        if self._suppress_autoplay:
            self._suppress_autoplay = False
            self._reset_progress_ui(clear_current=True)
        elif has_selection:
            self._play_selected()
        self._update_card_selection_states()

    def _current_identifier(self) -> str | None:
        selected_items = self.track_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].data(Qt.UserRole)

    def _play_selected(self) -> None:
        identifier = self._current_identifier()
        if not identifier:
            return
        self._player.play(identifier)
        self._current_track_id = identifier
        self._begin_progress_cycle(identifier)

    def _stop_playback(self) -> None:
        self._player.stop()
        self._reset_progress_ui(clear_current=True)

    def _update_card_selection_states(self) -> None:
        selected_indexes = {self.track_list.row(item) for item in self.track_list.selectedItems()}
        for row in range(self.track_list.count()):
            item = self.track_list.item(row)
            card = self.track_list.itemWidget(item)
            if not card:
                continue
            is_selected = row in selected_indexes
            card.setProperty("selected", is_selected)
            style = card.style()
            if hasattr(style, "unpolish"):
                style.unpolish(card)
            if hasattr(style, "polish"):
                style.polish(card)
            card.update()

    def _begin_progress_cycle(self, track_id: str) -> None:
        length = self._player.get_track_length(track_id) or 0.0
        slider_max = int(max(1, length * self._slider_scale)) if length > 0 else self._slider_scale
        can_seek = self._player.supports_seeking(track_id)
        self.progress_slider.blockSignals(True)
        self.progress_slider.setRange(0, slider_max)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(can_seek)
        self.progress_slider.blockSignals(False)
        self.elapsed_label.setText("0:00")
        self.duration_label.setText(self._format_time(length))
        self._slider_is_dragging = False
        self._update_card_progress(track_id, 0.0)
        self._progress_timer.start()

    def _refresh_progress(self) -> None:
        if not self._current_track_id:
            return

        position = self._player.get_current_position()
        length = self._player.get_track_length(self._current_track_id) or 0.0

        if not self._slider_is_dragging:
            slider_value = int(position * self._slider_scale)
            slider_value = max(0, min(slider_value, self.progress_slider.maximum()))
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(slider_value)
            self.progress_slider.blockSignals(False)

        self.elapsed_label.setText(self._format_time(position))
        fraction = position / length if length > 0 else 0.0
        self._update_card_progress(self._current_track_id, fraction)

        if not self._player.is_playing():
            if length > 0:
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(self.progress_slider.maximum())
                self.progress_slider.blockSignals(False)
                self.elapsed_label.setText(self._format_time(length))
                self._update_card_progress(self._current_track_id, 1.0)
            self._progress_timer.stop()

    def _reset_progress_ui(self, *, clear_current: bool = False) -> None:
        self._progress_timer.stop()
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(0)
        if clear_current:
            self.progress_slider.setEnabled(False)
            self.duration_label.setText("0:00")
            self._current_track_id = None
        self.progress_slider.blockSignals(False)
        self.elapsed_label.setText("0:00")
        self._slider_is_dragging = False
        self._update_card_progress(None, 0.0)

    def _update_card_progress(self, active_id: str | None, fraction: float) -> None:
        for track_id, card in self._card_widgets.items():
            if active_id and track_id == active_id:
                card.set_progress(fraction)
            else:
                card.set_progress(0.0)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _on_slider_pressed(self) -> None:
        if not self.progress_slider.isEnabled():
            return
        self._slider_is_dragging = True

    def _on_slider_released(self) -> None:
        if not self.progress_slider.isEnabled() or not self._current_track_id:
            self._slider_is_dragging = False
            return
        position = self.progress_slider.value() / self._slider_scale
        self._slider_is_dragging = False
        self._player.seek(position)
        self._progress_timer.start()

    def _on_slider_moved(self, value: int) -> None:
        if not self.progress_slider.isEnabled():
            return
        seconds = value / self._slider_scale
        self.elapsed_label.setText(self._format_time(seconds))
        length_max = self.progress_slider.maximum() / self._slider_scale
        fraction = (seconds / length_max) if length_max > 0 else 0.0
        if self._current_track_id:
            self._update_card_progress(self._current_track_id, fraction)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#mainContainer {
                background-color: #f5f6fb;
                color: #1f2430;
                font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            }
            QLabel#windowTitle {
                font-size: 24px;
                font-weight: 600;
                color: #11162a;
            }
            QLabel#windowSubtitle {
                font-size: 14px;
                color: #69728a;
            }
            QLabel#timeLabel {
                font-size: 12px;
                color: #52607d;
                min-width: 42px;
            }
            QListWidget#trackList {
                background: transparent;
                border: none;
                padding: 4px 0;
            }
            QListWidget#trackList::item {
                margin: 0px;
            }
            QListWidget#trackList::item:hover {
                background: transparent;
                border: none;
            }
            QListWidget#trackList::item:selected {
                background: transparent;
                border: none;
            }
            QListWidget#trackList::item:selected:active {
                background: transparent;
            }
            QFrame#trackCard {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #d9deea;
                padding: 4px;
                color: #1f2430;
            }
            QFrame#trackCard:hover {
                background-color: #f2f5ff;
                border: 1px solid #a9bbea;
            }
            QFrame#trackCard[selected="true"] {
                background-color: #ecf1ff;
                border: 2px solid #3f63ff;
                border-radius: 16px;
            }
            QLabel#trackTranscript {
                font-size: 15px;
                font-weight: 500;
                color: #1b2030;
                line-height: 1.45;
            }
            QLabel#trackFallbackTitle {
                font-size: 13px;
                color: #7c849b;
            }
            QSlider#progressSlider {
                min-height: 24px;
            }
            QSlider#progressSlider::groove:horizontal {
                background: #d4d9ec;
                height: 6px;
                border-radius: 3px;
            }
            QSlider#progressSlider::sub-page:horizontal {
                background: #5a7aff;
                border-radius: 3px;
            }
            QSlider#progressSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #ffffff;
                border: 1px solid #5a7aff;
            }
            QPushButton {
                background-color: #3f63ff;
                border: none;
                border-radius: 12px;
                padding: 10px 22px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2f52e6;
            }
            QPushButton:pressed {
                background-color: #2443c5;
            }
            QPushButton:disabled {
                color: #a8b0c8;
                background-color: #dfe3f2;
            }
            """
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._progress_timer.stop()
        self._player.close()
        super().closeEvent(event)


@dataclass
class TrackListApp:
    """Bootstrap the Qt event loop and main window."""

    tracks: Sequence[Track]
    player: TrackPlayer

    def run(self) -> None:
        app = QApplication.instance()
        created_app = False
        if app is None:
            app = QApplication(sys.argv)
            created_app = True

        app.aboutToQuit.connect(self.player.close)

        window = TrackListWindow(self.tracks, self.player)
        window.show()

        try:
            app.exec()
        finally:
            if created_app:
                # Ensure the mixer is closed if the window closes without invoking closeEvent.
                self.player.close()
