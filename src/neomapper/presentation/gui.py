
from __future__ import annotations

import traceback
from datetime import timedelta
from pathlib import Path
import shutil
import time
import os

from PySide6.QtCore import QObject, QRunnable, Qt, QDateTime, QEventLoop, QThreadPool, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QComboBox, QMessageBox,
    QDateTimeEdit, QProgressBar, QCheckBox, QSplitter, QStackedWidget, QSlider, QDialog, QFormLayout, QSpinBox, QFileDialog
)

from neomapper.application.ephemerides import ObjectNotFoundError
from neomapper.infrastructure.config import load_config, save_config
from neomapper.infrastructure.paths import logs_dir, output_dir, object_output_dir
from neomapper.presentation.animation import generate_animation
from neomapper.presentation.altitude_plot import build_altitude_chart, AltitudeChartResult
from neomapper.presentation.object_summary import ObjectSummaryWidget
from neomapper.presentation.context_help import help_text, show_help
from neomapper.application.object_summary import calculate_object_summary
from neomapper.infrastructure.ephemeris.summary import HorizonsSummaryProvider
from neomapper.presentation.distances import AU_KM, format_distance, update_figure_distances
from neomapper.presentation.i18n import Translator, format_number
from neomapper.presentation.mapplot import build_location_figure, build_solar_system_sketch, build_visibility_figure, update_solar_system_labels
from neomapper.presentation.ephemeris_report import create_ephemeris_pdf
from neomapper.application.ephemerides import query_report_ephemerides
from neomapper.presentation.skymap_observing import build_sky_figure
from neomapper.shared.utils import parse_input_time_for_mode, safe_filename
from neomapper.shared.version import APP_TITLE, APP_VERSION


STYLE = """
QMainWindow, QWidget {
    background-color: #071017;
    color: #e9f0f7;
    font-family: Segoe UI;
}
QFrame#Card {
    background-color: #101922;
    border: 1px solid #1f3345;
    border-radius: 10px;
}
QFrame#SubCard {
    background-color: #0d161f;
    border: 1px solid #1b2b3a;
    border-radius: 8px;
}
QFrame#MapArea {
    background-color: #0b1219;
    border: 1px solid #1f3345;
    border-radius: 10px;
}
QLabel#Title {
    color: #f3f6fb;
    font-size: 24px;
    font-weight: 700;
}
QLabel#Subtitle {
    color: #4aa3ff;
    font-size: 12px;
}
QLabel#Section {
    color: #f3f6fb;
    font-size: 15px;
    font-weight: 700;
}
QLabel#Muted {
    color: #9aa8b5;
    font-size: 12px;
}
QLabel#MetricValue {
    color: #f3f6fb;
    font-size: 18px;
    font-weight: 700;
}
QLabel#MetricBlue {
    color: #2f95ff;
    font-size: 20px;
    font-weight: 700;
}
QLabel#MetricYellow {
    color: #ffd400;
    font-size: 20px;
    font-weight: 700;
}
QLineEdit, QComboBox, QDateTimeEdit {
    background-color: #0b1219;
    border: 1px solid #26394a;
    border-radius: 6px;
    padding: 7px;
    color: #e9f0f7;
}
QPushButton {
    background-color: #172332;
    border: 1px solid #26394a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e9f0f7;
}
QPushButton:hover {
    background-color: #213247;
}
QPushButton#Blue:enabled {
    background-color: #1578ff;
    border: 0;
    font-weight: 700;
    font-size: 14px;
}
QPushButton#Blue:enabled:hover {
    background-color: #2a88ff;
}
QPushButton:disabled {
    background-color: #101922;
    border: 1px solid #26394a;
    color: #667683;
}
QCheckBox {
    color: #e9f0f7;
    spacing: 8px;
}
QProgressBar {
    border: 1px solid #26394a;
    border-radius: 6px;
    background: #101922;
    height: 10px;
}
QProgressBar::chunk {
    background-color: #1578ff;
    border-radius: 5px;
}
"""


def application_icon_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "neomapper_icon.ico"

class TranslationRegistry:
    """Keep every widget registered for a key, including repeated labels."""
    def __init__(self):
        self._widgets = {}

    def __setitem__(self, key, widget):
        self._widgets.setdefault(key, []).append(widget)

    def __contains__(self, key):
        return key in self._widgets

    def __getitem__(self, key):
        return self._widgets[key][-1]

    def items(self):
        for key, widgets in self._widgets.items():
            for widget in widgets:
                yield key, widget


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(object)
    progress = Signal(object)
    finished = Signal()


class BackgroundWorker(QRunnable):
    """Run a callable outside the Qt GUI thread and return through signals."""

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.result.emit(self.function(self.signals.progress.emit))
        except Exception as exc:
            self.signals.error.emit((exc, traceback.format_exc()))
        finally:
            self.signals.finished.emit()


class NEOMapperMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - GUI")
        self.setWindowIcon(QIcon(str(application_icon_path())))
        self.resize(1500, 900)
        self.setMinimumSize(1180, 740)
        self.setStyleSheet(STYLE)

        self.last_png: Path | None = None
        self._distance_preview = None
        self._displayed_png = None
        self.last_result: dict | None = None
        self.cfg = load_config()
        self.translator = Translator(self.cfg.get("ui", "language", fallback="EN"))
        self.tr_widgets = TranslationRegistry()
        self.metric_labels = {}
        self.animation_cancel_requested = False
        self.workflow_step = 0
        self.thread_pool = QThreadPool(self)
        self.active_workers = set()
        self.player_frames: list[Path] = []
        self._page_previews: dict[int, Path] = {}
        self._page_frames: dict[int, list[Path]] = {}
        self.player_index = 0
        self._transient_frames_dir: Path | None = None
        self.player_timer = QTimer(self)
        self.player_timer.timeout.connect(self.player_next_frame)

        self._object_validated = False
        self._object_search_busy = False
        self.build_ui()
        self.right_stack.currentChanged.connect(self._update_preview_hint)
        self.object_edit.textChanged.connect(self._invalidate_object_search)
        self.datetime_edit.dateTimeChanged.connect(self._invalidate_object_search)
        self.ref_lat_edit.textChanged.connect(self._invalidate_orbital_summary)
        self.ref_lon_edit.textChanged.connect(self._invalidate_orbital_summary)
        for field in (self.ref_alt_edit, self.obs_min_alt_edit, self.obs_sun_alt_edit):
            field.textChanged.connect(self._invalidate_orbital_summary)
        self.map_time_edit.timeChanged.connect(self._invalidate_orbital_summary)
        self._update_object_actions()
        self.update_language_texts()

    def build_ui(self):
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 12, 14, 10)
        main.setSpacing(8)

        main.addLayout(self.build_header())

        body = QHBoxLayout()
        body.setSpacing(8)
        # v4.1.4: Object and Generate Map were moved into right-side tabs.
        # The former left panel is no longer shown, giving the map more room.
        body.addWidget(self.build_center_panel(), 1)
        body.addWidget(self.build_right_panel())
        main.addLayout(body, 1)

        main.addLayout(self.build_footer())
        self.setCentralWidget(root)

    def build_header(self):
        header = QHBoxLayout()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)

        # v4.1.6: remove the remaining slogan/header text to free vertical map area.
        self.subtitle_label = QLabel("")
        self.subtitle_label.hide()
        header.addStretch()

        # Kept as internal mirrors for existing rendering code.
        # Visible controls were moved to Settings in v4.1.2.
        # These must be parented to the main window; otherwise Qt may delete
        # the temporary header cards before build_right_panel() reads them.
        self.language_header_combo = QComboBox(self)
        self.language_header_combo.addItems(["EN", "PT", "ES"])
        self.language_header_combo.hide()
        self.render_header_combo = QComboBox(self)
        self.render_header_combo.addItems(["HD", "FHD", "2K", "4K"])
        self.render_header_combo.hide()

        return header

    def create_header_combo(self, label, values, width):
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedSize(width, 70)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 7, 10, 9)

        lab = QLabel(label)
        lab.setObjectName("Muted")
        self.metric_labels[label] = lab
        self.tr_widgets[label] = lab
        combo = QComboBox()
        combo.setMinimumHeight(32)
        combo.addItems(values)

        layout.addWidget(lab)
        layout.addWidget(combo)
        return combo, card

    def build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setFixedWidth(315)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        layout.addWidget(self.create_section_label("Object"))

        self.object_edit = self.create_line_field(layout, "Object / Designation", self.cfg.get("last", "object", fallback="99942"))

        info = QLabel("Time, Layers and Settings are now organized in the right-side tabs.")
        self.tr_widgets[info.text()] = info
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.generate_btn = QPushButton("🗺️  Generate Map")
        self.generate_btn.setObjectName("Blue")
        self.generate_btn.setMinimumHeight(46)
        self.generate_btn.clicked.connect(self.generate_map)
        layout.addWidget(self.generate_btn)

        layout.addStretch()
        return panel

    def build_center_panel(self):
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(1, 1, 1, 1)

        top = QHBoxLayout()
        top.setContentsMargins(12, 8, 12, 8)
        self.map_title = QLabel("Map Preview")
        self.map_title.setObjectName("Section")
        top.addWidget(self.map_title)
        top.addStretch()
        self.moon_curve_btn = QPushButton("Show Moon")
        self.moon_curve_btn.setCheckable(True)
        self.moon_curve_btn.setStyleSheet("QPushButton:checked { background-color: #365367; }")
        self.moon_curve_btn.hide()
        self.moon_curve_btn.clicked.connect(self._toggle_moon_curve)
        layout.addLayout(top)

        self.map_area = QFrame()
        self.map_area.setObjectName("MapArea")
        projection_layout = QVBoxLayout(self.map_area)
        projection_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_area = QFrame()
        projection_layout.addWidget(self.plot_area, 1)
        self.map_area_layout = QVBoxLayout(self.plot_area)
        self.map_area_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel("Click Generate Map to preview the selected chart type.")
        self.preview_label.setProperty("mapPreviewHint", True)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color:#9aa8b5;font-size:16px;")
        self.map_area_layout.addWidget(self.preview_label)

        self.altitude_details = QWidget()
        details_layout = QVBoxLayout(self.altitude_details)
        details_layout.setContentsMargins(8, 0, 8, 4)
        details_layout.addWidget(self.moon_curve_btn, 0, Qt.AlignRight)
        self.orbital_summary = ObjectSummaryWidget()
        from PySide6.QtWidgets import QHeaderView
        self.orbital_summary.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        details_layout.addWidget(self.orbital_summary)
        projection_layout.addWidget(self.altitude_details)
        self.altitude_details.hide()

        layout.addWidget(self.map_area, 1)
        controls = QHBoxLayout()
        controls.setContentsMargins(10, 5, 10, 8)
        controls.setSpacing(6)
        self.player_prev_btn = QPushButton("|<")
        self.player_play_btn = QPushButton("Play")
        self.player_next_btn = QPushButton(">|")
        self.player_prev_btn.clicked.connect(self.player_previous_frame)
        self.player_play_btn.clicked.connect(self.toggle_player)
        self.player_next_btn.clicked.connect(self.player_next_frame)
        self.player_slider = QSlider(Qt.Horizontal)
        self.player_slider.setRange(0, 0)
        self.player_slider.valueChanged.connect(self.player_seek)
        self.player_counter = QLabel("0 / 0")
        self.player_counter.setObjectName("Muted")
        self.player_loop = QCheckBox("Loop")
        self.player_loop.setChecked(True)
        for widget in (self.player_prev_btn, self.player_play_btn, self.player_next_btn, self.player_slider):
            widget.setEnabled(False)
        controls.addWidget(self.player_prev_btn)
        controls.addWidget(self.player_play_btn)
        controls.addWidget(self.player_next_btn)
        controls.addWidget(self.player_slider, 1)
        controls.addWidget(self.player_counter)
        controls.addWidget(self.player_loop)
        layout.addLayout(controls)
        return panel

    def build_right_panel(self):
        """Right side v4.1 panel: vertical icon tabs + contextual pages.

        Philosophy for v4.1: keep the world map as protagonist and put the
        most useful public-facing information first: observational window,
        best local visibility and basic viewing controls. Object orbital details
        are moved away from the primary view.
        """
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setFixedWidth(430)
        outer = QHBoxLayout(panel)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Vertical tab rail
        rail = QFrame()
        rail.setObjectName("SubCard")
        rail.setFixedWidth(104)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(8, 8, 8, 8)
        rail_layout.setSpacing(8)

        self.tab_buttons = []
        self.tab_specs = []
        def make_tab(text, icon, idx):
            btn = QPushButton(f"{icon}\n{text}")
            btn.setCheckable(True)
            btn.setMinimumHeight(72)
            btn.setStyleSheet("""
                QPushButton { text-align: center; font-weight: 600; font-size: 11px; }
                QPushButton:checked { background-color: #1578ff; border: 1px solid #2a88ff; }
            """)
            btn.clicked.connect(lambda _=False, i=idx: self._activate_workflow_page(i))
            btn.clicked.connect(lambda _=False, b=btn: self._set_active_tab(b))
            self.tab_buttons.append(btn)
            self.tab_specs.append((text, icon, btn))
            rail_layout.addWidget(btn)
            return btn

        self.right_stack = QStackedWidget()

        # Page 0 — Observation: the default and most important page.
        obs_page = QFrame()
        obs_layout = QVBoxLayout(obs_page)
        obs_layout.setContentsMargins(8, 8, 8, 8)
        obs_layout.setSpacing(10)
        obs_layout.addWidget(self.create_section_label("Observational Information"))
        self.plot_altitude_btn = QPushButton("Plot altitude chart")
        self.plot_altitude_btn.setObjectName("Blue")
        self.plot_altitude_btn.clicked.connect(self.plot_altitude_chart)
        self.tr_widgets["Plot altitude chart"] = self.plot_altitude_btn
        obs_layout.addWidget(self.plot_altitude_btn)
        self.orbital_summary_btn = QPushButton()
        self.orbital_summary_btn.setObjectName("Blue")
        self.orbital_summary_btn.clicked.connect(self.generate_orbital_summary)
        self.tr_widgets["Orbital summary"] = self.orbital_summary_btn
        obs_layout.addWidget(self.orbital_summary_btn)
        self.obs_next_btn = QPushButton("Continue to Layers →")
        self.obs_next_btn.setObjectName("Blue")
        self.obs_next_btn.clicked.connect(self._continue_to_layers)
        self.tr_widgets["Continue to Layers →"] = self.obs_next_btn
        obs_layout.addWidget(self.obs_next_btn)
        self.create_window_summary_card(obs_layout)
        self.summary_alt = self.create_metric_card(obs_layout, "Maximum altitude", "—", "MetricYellow")
        self.summary_time = QLabel(self)
        self.summary_time.hide()
        self.summary_dist = QLabel(self)
        self.summary_dist.hide()
        self.summary_mag = self.create_metric_card(obs_layout, "Magnitude", "—", "MetricValue")
        obs_layout.addWidget(self.create_section_label("Window Display"))
        self.obs_min_alt_edit = self.create_line_field(obs_layout, "Minimum altitude deg", self.cfg.get("observing", "min_altitude", fallback="0"))
        self.obs_sun_alt_edit = self.create_line_field(obs_layout, "Sun altitude limit deg", self.cfg.get("observing", "sun_altitude_limit", fallback="-12"))
        obs_layout.addStretch()
        from PySide6.QtWidgets import QScrollArea
        obs_scroll = QScrollArea()
        obs_scroll.setWidgetResizable(True)
        obs_scroll.setFrameShape(QFrame.NoFrame)
        obs_scroll.setWidget(obs_page)
        self.right_stack.addWidget(obs_scroll)

        # Page 1 — Object: primary workflow page in v4.1.4.
        obj_page = QFrame()
        obj_layout = QVBoxLayout(obj_page)
        obj_layout.setContentsMargins(8, 8, 8, 8)
        obj_layout.setSpacing(10)
        self.object_section_label = self.create_section_label("Object")
        obj_layout.addWidget(self.object_section_label)
        self.object_edit = self.create_line_field(obj_layout, "Object / Designation", self.cfg.get("last", "object", fallback="99942"))
        self.favorites_btn = QPushButton()
        self.favorites_btn.setObjectName("Blue")
        self.favorites_btn.setEnabled(True)
        self.tr_widgets["Favorites"] = self.favorites_btn
        self.favorites_btn.clicked.connect(self.open_favorites)
        obj_layout.addWidget(self.favorites_btn)
        self.object_date_label = self.create_section_label("Observation date")
        obj_layout.addWidget(self.object_date_label)
        self.datetime_edit = self.create_datetime_field(
            obj_layout, "Date", QDateTime.currentDateTime()
        )
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd")
        self.object_search_btn = QPushButton("🔎  Search")
        self.object_search_btn.setObjectName("Blue")
        self.object_search_btn.setMinimumHeight(40)
        self.object_search_btn.clicked.connect(lambda _checked=False: self.generate_map(preview=False))
        self.tr_widgets["Search"] = self.object_search_btn
        obj_layout.addWidget(self.object_search_btn)
        self.plot_solar_btn = QPushButton("☀  Plot Solar System")
        self.tr_widgets["Plot Solar System"] = self.plot_solar_btn
        self.plot_solar_btn.setObjectName("Blue")
        self.plot_solar_btn.clicked.connect(self.plot_solar_system)
        obj_layout.addWidget(self.plot_solar_btn)
        obj_layout.addWidget(self.create_section_label("Object Information"))
        self.summary_object = self.create_metric_card(obj_layout, "Object", "—", "MetricBlue")
        self.object_sun_distance = self.create_metric_card(obj_layout, "Distance to Sun", "—", "MetricValue")
        self.object_earth_distance = self.create_metric_card(obj_layout, "Distance to Earth", "—", "MetricValue")
        self.object_magnitude = self.create_metric_card(obj_layout, "Magnitude", "—", "MetricValue")
        self.object_best_alt = self.create_metric_card(obj_layout, "Maximum altitude", "—", "MetricYellow")
        self.summary_file = self.create_metric_card(obj_layout, "Output", "—", "MetricValue")
        self.object_best_alt.parentWidget().setVisible(False)
        self.summary_file.parentWidget().setVisible(False)
        self.object_next_btn = QPushButton("Continue to Obs. Information →")
        self.tr_widgets["Continue to Obs. Information →"] = self.object_next_btn
        self.object_next_btn.setObjectName("Blue")
        self.object_next_btn.clicked.connect(self._continue_to_observation)
        self.object_next_btn.setEnabled(False)
        obj_layout.addWidget(self.object_next_btn)
        obj_layout.addStretch()
        self.right_stack.addWidget(obj_page)

        # Page 2 — Local / Reference Point.
        local_page = QFrame()
        local_layout = QVBoxLayout(local_page)
        local_layout.setContentsMargins(8, 8, 8, 8)
        local_layout.setSpacing(10)
        local_layout.addWidget(self.create_section_label("Reference Location"))

        self.presets = self.load_site_presets()
        self.site_preset_combo = self.create_combo_field(local_layout, "Preset", list(self.presets.keys()) + ["Custom"])
        self.site_preset_combo.currentTextChanged.connect(self.apply_site_preset)
        self.ref_name_edit = self.create_line_field(local_layout, "Name", self.cfg.get("reference", "name", fallback="Belo Horizonte, MG, Brazil"))

        # Latitude and Longitude side by side, now inside the Local tab.
        latlon_row = QHBoxLayout()
        latlon_row.setSpacing(8)
        lat_box = QVBoxLayout()
        lon_box = QVBoxLayout()
        self.ref_lat_edit = self.create_line_field(lat_box, "Latitude", self.cfg.get("reference", "lat", fallback="-19.9"))
        self.ref_lon_edit = self.create_line_field(lon_box, "Longitude", self.cfg.get("reference", "lon", fallback="-43.9"))
        latlon_row.addLayout(lat_box)
        latlon_row.addLayout(lon_box)
        local_layout.addLayout(latlon_row)
        self.ref_alt_edit = self.create_line_field(local_layout, "Altitude m", self.cfg.get("reference", "alt", fallback="850"))

        preset_buttons = QHBoxLayout()
        preset_buttons.setSpacing(6)
        self.save_preset_btn = QPushButton("💾 Save")
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        self.update_preset_btn = QPushButton("↻ Update")
        self.update_preset_btn.clicked.connect(self.update_current_preset)
        self.delete_preset_btn = QPushButton("🗑 Delete")
        self.delete_preset_btn.clicked.connect(self.delete_current_preset)
        self.tr_widgets["Save"] = self.save_preset_btn
        self.tr_widgets["Update"] = self.update_preset_btn
        self.tr_widgets["Delete"] = self.delete_preset_btn
        preset_buttons.addWidget(self.save_preset_btn)
        preset_buttons.addWidget(self.update_preset_btn)
        preset_buttons.addWidget(self.delete_preset_btn)
        local_layout.addLayout(preset_buttons)
        self.select_current_preset_from_reference()

        self.quick_site_label = self.create_metric_card(local_layout, "Reference point", "—", "MetricValue")
        local_layout.addStretch()
        self._local_page = local_page
        self.right_stack.addWidget(local_page)

        # Page 3 — Time quick view.
        time_page = QFrame()
        time_layout = QVBoxLayout(time_page)
        time_layout.setContentsMargins(8, 8, 8, 8)
        time_layout.setSpacing(10)
        time_layout.addWidget(self.create_section_label("Time"))
        # Date is part of the Object step; time remains an internal value for
        # the later workflow stages and is not exposed here yet.
        self.now_btn = QPushButton("Now")
        self.now_btn.clicked.connect(self.set_datetime_now)
        self.tr_widgets["Now"] = self.now_btn
        time_layout.addWidget(self.now_btn)
        self.time_mode_combo = self.create_combo_field(time_layout, "Time display", ["UTC", "LOCAL"])
        self.time_mode_combo.setCurrentText(self.cfg.get("time", "mode", fallback="UTC"))
        self.time_mode_combo.currentTextChanged.connect(lambda _: self.update_language_texts())
        self.quick_time_mode = self.create_metric_card(time_layout, "Current time mode", self.time_mode_combo.currentText(), "MetricValue")
        time_note = QLabel("The selected Time Display controls both input interpretation and all output labels.")
        time_note.setObjectName("Muted")
        time_note.setWordWrap(True)
        self.tr_widgets["The selected Time Display controls both input interpretation and all output labels."] = time_note
        time_layout.addWidget(time_note)
        self.time_next_btn = QPushButton("Continue to Obs. Information →")
        self.time_next_btn.setObjectName("Blue")
        self.time_next_btn.clicked.connect(self._advance_workflow)
        time_layout.addWidget(self.time_next_btn)
        time_layout.addStretch()
        self.right_stack.addWidget(time_page)

        # Page 4 — Layers quick view.
        layer_page = QFrame()
        layer_layout = QVBoxLayout(layer_page)
        layer_layout.setContentsMargins(8, 8, 8, 8)
        layer_layout.setSpacing(10)
        layer_layout.addWidget(self.create_section_label("Map Layers"))
        self.map_date_edit = self.create_datetime_field(layer_layout, "Date", self.datetime_edit.dateTime())
        self.map_date_edit.setDisplayFormat("yyyy-MM-dd")
        map_time_row = QHBoxLayout()
        map_time_fields = QVBoxLayout()
        self.map_time_edit = self.create_datetime_field(map_time_fields, "Map time", self.datetime_edit.dateTime())
        self.map_time_edit.setDisplayFormat("HH:mm:ss")
        self.map_time_edit.setCalendarPopup(False)
        map_time_row.addLayout(map_time_fields, 2)
        layer_layout.addLayout(map_time_row)
        self.datetime_edit.dateTimeChanged.connect(self._sync_map_datetime)

        self.map_type_combo = self.create_combo_field(layer_layout, "Map type", ["Visibility Map", "Sky Map"])
        self.map_type_combo.setCurrentText(self.cfg.get("map", "type", fallback="Visibility Map"))
        self.star_magnitude_combo = self.create_combo_field(
            layer_layout, "Star magnitude limit", ["4.0", "5.0", "6.0", "7.0"]
        )
        self.star_magnitude_combo.setCurrentText(
            self.cfg.get("map", "star_magnitude_limit", fallback="5.0")
        )
        self.generate_btn = QPushButton("🗺️  Generate Map")
        self.generate_btn.setObjectName("Blue")
        self.generate_btn.setMinimumHeight(46)
        self.generate_btn.clicked.connect(self.generate_map)
        layer_layout.addWidget(self.generate_btn)
        self.ephemeris_btn = QPushButton("Ephemerides")
        self.ephemeris_btn.setObjectName("Blue")
        self.ephemeris_btn.clicked.connect(self.open_ephemeris_dialog)
        self.tr_widgets["Ephemerides"] = self.ephemeris_btn
        layer_layout.addWidget(self.ephemeris_btn)
        self.cb_daynight = self.create_check(layer_layout, "Day / Night", True)
        self.cb_civil = self.create_check(layer_layout, "Civil twilight", True)
        self.cb_nautical = self.create_check(layer_layout, "Nautical twilight", True)
        self.cb_astro = self.create_check(layer_layout, "Astronomical twilight", True)
        self.cb_terminator = self.create_check(layer_layout, "Terminator", True)
        self.cb_reference_point = self.create_check(layer_layout, "Reference point", self.cfg.get("map", "show_reference_point", fallback="yes").lower() in ("yes","true","1"))
        self.cb_altitude = self.create_check(layer_layout, "Altitude lines", False)
        self.cb_obs_box = self.create_check(layer_layout, "Show window box on map", self.cfg.get("observing", "show_box", fallback="no").lower() in ("yes","true","1"))
        self.obs_box_pos_combo = self.create_combo_field(layer_layout, "Window box position", ["Upper right", "Upper left", "Lower right", "Lower left"])
        self.obs_box_pos_combo.setCurrentText(self.cfg.get("observing", "box_position", fallback="Upper right"))
        self.visibility_map_controls = (
            self.cb_daynight, self.cb_civil, self.cb_nautical, self.cb_astro,
            self.cb_terminator, self.cb_reference_point, self.cb_altitude,
            self.cb_obs_box, self.tr_widgets["Window box position"], self.obs_box_pos_combo,
        )
        self.map_type_combo.currentIndexChanged.connect(self._update_map_type_controls)
        self._update_map_type_controls()
        self.layers_next_btn = QPushButton("Continue to Animation →")
        self.layers_next_btn.setObjectName("Blue")
        self.tr_widgets["Continue to Animation →"] = self.layers_next_btn
        self.layers_next_btn.clicked.connect(self._continue_to_animation)
        layer_layout.addWidget(self.layers_next_btn)
        layer_layout.addStretch()
        self.right_stack.addWidget(layer_page)

        # Page 5 — Animation.
        anim_page = QFrame()
        anim_layout = QVBoxLayout(anim_page)
        anim_layout.setContentsMargins(8, 8, 8, 8)
        anim_layout.setSpacing(10)
        anim_layout.addWidget(self.create_section_label("Animation"))
        initial_time = self.datetime_edit.dateTime()
        self.anim_start_edit = self.create_datetime_field(anim_layout, "Start time", initial_time)
        self.anim_end_edit = self.create_datetime_field(anim_layout, "End time", initial_time.addSecs(86400))
        self.datetime_edit.dateTimeChanged.connect(self._sync_animation_datetime)
        self.anim_step_combo = self.create_combo_field(anim_layout, "Step", [])
        for label, step in (("1 min", 1), ("5 min", 5), ("10 min", 10), ("30 min", 30),
                            ("1 h", 60), ("1 day", 1440), ("1 week", 10080), ("1 month", "month"), ("1 year", "year")):
            self.anim_step_combo.addItem(label, step)
        self.anim_step_combo.setCurrentIndex(1)
        self.anim_playback_combo = self.create_combo_field(
            anim_layout,
            "Playback Speed",
            ["Very Slow (1 fps)", "Slow (4 fps)", "Normal (8 fps)", "Fast (15 fps)", "Very Fast (25 fps)"],
        )
        self.anim_playback_combo.setCurrentText("Normal (8 fps)")
        self.anim_format_combo = self.create_combo_field(anim_layout, "Output format", ["GIF", "MP4", "GIF + MP4", "Frames PNG"])
        self.cb_anim_info_panel = self.create_check(anim_layout, "Show information panel", True)
        self.cb_anim_trail = self.create_check(anim_layout, "Keep Previous Positions (Trail)", False)
        self.cb_anim_keep_frames = self.create_check(anim_layout, "Keep generated frames", False)
        anim_buttons = QHBoxLayout()
        self.generate_anim_btn = QPushButton("🎞️  Generate Animation")
        self.generate_anim_btn.setObjectName("Blue")
        self.generate_anim_btn.setMinimumHeight(44)
        self.generate_anim_btn.clicked.connect(self.generate_animation_output)
        self.cancel_anim_btn = QPushButton("⏹  Cancel")
        self.cancel_anim_btn.setMinimumHeight(44)
        self.cancel_anim_btn.setEnabled(False)
        self.cancel_anim_btn.clicked.connect(self.cancel_animation_output)
        self.tr_widgets["Generate Animation"] = self.generate_anim_btn
        self.tr_widgets["Cancel"] = self.cancel_anim_btn
        anim_buttons.addWidget(self.generate_anim_btn, 1)
        anim_buttons.addWidget(self.cancel_anim_btn)
        anim_layout.addLayout(anim_buttons)
        self.anim_progress_label = QLabel(self.translator.tr("Ready"))
        self.anim_progress_label.setObjectName("Muted")
        self.anim_progress_label.setWordWrap(True)
        anim_layout.addWidget(self.anim_progress_label)
        self.open_animation_folder_btn = QPushButton("📂  Open animation folder")
        self.open_animation_folder_btn.clicked.connect(self.open_animation_folder)
        self.tr_widgets["Open animation folder"] = self.open_animation_folder_btn
        anim_layout.addWidget(self.open_animation_folder_btn)
        anim_note = QLabel("GIFs always play in an infinite loop. End Time controls the final rendered frame.")
        anim_note.setObjectName("Muted")
        anim_note.setWordWrap(True)
        self.tr_widgets["GIFs always play in an infinite loop. End Time controls the final rendered frame."] = anim_note
        anim_layout.addWidget(anim_note)
        anim_layout.addStretch()
        self.right_stack.addWidget(anim_page)

        # Page 6 — Settings.
        settings_page = QFrame()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(10)
        settings_layout.addWidget(self.create_section_label("Settings"))
        settings_layout.addWidget(self.tr_widgets["Time display"])
        settings_layout.addWidget(self.time_mode_combo)
        self.time_mode_combo.currentTextChanged.connect(self._save_time_mode)
        self.language_side_combo = self.create_combo_field(settings_layout, "Map language", ["EN", "PT", "ES"])
        self.language_side_combo.setCurrentText(self.cfg.get("ui", "language", fallback="EN"))
        self.language_header_combo.setCurrentText(self.language_side_combo.currentText())
        self.render_side_combo = self.create_combo_field(settings_layout, "Render size", ["HD", "FHD", "2K", "4K"])
        self.render_side_combo.setCurrentText(self.cfg.get("map", "render_size", fallback="HD"))
        self.render_header_combo.setCurrentText(self.render_side_combo.currentText())
        self.dpi_edit = self.create_line_field(settings_layout, "DPI", self.cfg.get("map", "dpi", fallback="130"))
        self.distance_unit_combo = self.create_combo_field(settings_layout, "Distance unit", ["UA", "km"])
        self.distance_unit_combo.setCurrentText(self.cfg.get("ui", "distance_unit", fallback="km"))
        self.orbital_summary.set_distance_unit(self.distance_unit_combo.currentText())
        self.distance_unit_combo.currentTextChanged.connect(self._distance_unit_changed)
        for key, label, attribute in (
            ("animation_frames", "Maximum animation frames", "animation_frame_limit"),
            ("ephemeris_rows", "Maximum ephemeris rows", "ephemeris_row_limit"),
        ):
            limit_label = QLabel(label)
            limit_label.setWordWrap(True)
            self.tr_widgets[label] = limit_label
            settings_layout.addWidget(limit_label)
            field = QSpinBox()
            field.setMinimumHeight(32)
            field.setRange(1, 2147483647)
            try:
                value = self.cfg.getint("limits", key, fallback=500)
            except ValueError:
                value = 500
            field.setValue(value if value > 0 else 500)
            setattr(self, attribute, field)
            settings_layout.addWidget(field)
            field.valueChanged.connect(lambda value, key=key: self._save_generation_limit(key, value))


        self.language_side_combo.currentTextChanged.connect(self.language_header_combo.setCurrentText)
        self.language_header_combo.currentTextChanged.connect(self.language_side_combo.setCurrentText)
        self.language_header_combo.currentTextChanged.connect(lambda _: self.update_language_texts())
        self.render_side_combo.currentTextChanged.connect(self.render_header_combo.setCurrentText)
        self.render_header_combo.currentTextChanged.connect(self.render_side_combo.setCurrentText)

        settings_layout.addStretch()
        # Reference-location controls belong to Settings; keep one stable
        # place for all site configuration instead of a separate workflow tab.
        self.right_stack.removeWidget(local_page)
        local_page.setParent(settings_page)
        settings_layout.insertWidget(1, local_page)
        local_page.show()
        from PySide6.QtWidgets import QScrollArea
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        settings_scroll.setWidget(settings_page)
        self.right_stack.addWidget(settings_scroll)

        # Page 7 — About.
        about_page = QFrame()
        about_layout = QVBoxLayout(about_page)
        about_layout.setContentsMargins(8, 8, 8, 8)
        about_layout.setSpacing(10)
        about_layout.addWidget(self.create_section_label("About"))
        self.about_name = self.create_metric_card(about_layout, "Software", APP_TITLE, "MetricBlue")
        self.about_version = self.create_metric_card(about_layout, "Version", APP_VERSION, "MetricValue")
        about_note = QLabel("NEOMapper — visibility mapping tool for near-Earth objects and planetary defense outreach.")
        about_note.setObjectName("Muted")
        about_note.setWordWrap(True)
        self.tr_widgets["NEOMapper — visibility mapping tool for near-Earth objects and planetary defense outreach."] = about_note
        about_layout.addWidget(about_note)
        data_credit = QLabel("Stellar catalogue: Credit: ESA (Hipparcos, CC BY-NC 3.0 IGO).")
        data_credit.setObjectName("Muted")
        data_credit.setWordWrap(True)
        self.tr_widgets["Stellar catalogue: Credit: ESA (Hipparcos, CC BY-NC 3.0 IGO)."] = data_credit
        about_layout.addWidget(data_credit)
        self.sponsor_label = QLabel()
        self.sponsor_label.setWordWrap(True)
        self.tr_widgets["Offered by Observatório SONEAR and the AstroNEOS channel."] = self.sponsor_label
        about_layout.addWidget(self.sponsor_label)
        self.channel_label = QLabel()
        self.channel_label.setWordWrap(True)
        self.channel_label.setOpenExternalLinks(True)
        self.tr_widgets['Subscribe to <a href="https://www.youtube.com/@AstroNEOS">AstroNEOS</a> to support more initiatives.'] = self.channel_label
        about_layout.addWidget(self.channel_label)
        self.help_btn = QPushButton()
        self.tr_widgets["Help"] = self.help_btn
        self.help_btn.clicked.connect(lambda: show_help(self, self.language_header_combo.currentText()))
        about_layout.addWidget(self.help_btn)
        about_layout.addStretch()
        self.right_stack.addWidget(about_page)

        make_tab("Object", "◎", 1)
        make_tab("Obs.\nInformation", "◷", 0)
        make_tab("Layers", "▱", 3)
        make_tab("Animation", "▥", 4)
        rail_layout.addStretch()
        make_tab("Settings", "⚙", 5)
        make_tab("About", "ⓘ", 6)
        self.right_stack.setCurrentIndex(1)
        self.tab_buttons[0].setChecked(True)
        self._update_workflow_navigation()

        outer.addWidget(rail)
        outer.addWidget(self.right_stack, 1)
        return panel

    def create_window_summary_card(self, layout):
        card = QFrame()
        card.setObjectName("SubCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        title = QLabel("Observation Window")
        title.setObjectName("Section")
        self.tr_widgets["Observation Window"] = title
        card_layout.addWidget(title)

        self.window_start_label = QLabel("Start window\n—")
        self.window_start_label.setObjectName("MetricValue")
        self.window_best_label = QLabel("Best time\n—")
        self.window_best_label.setObjectName("MetricYellow")
        self.window_end_label = QLabel("End window\n—")
        self.window_end_label.setObjectName("MetricValue")

        for lab in (self.window_start_label, self.window_best_label, self.window_end_label):
            lab.setWordWrap(True)
            card_layout.addWidget(lab)

        layout.addWidget(card)
        return card

    def _update_object_actions(self) -> None:
        self.object_search_btn.setEnabled(not self._object_search_busy)
        ready = self._object_validated and not self._object_search_busy
        self.plot_solar_btn.setEnabled(ready)
        self.object_next_btn.setEnabled(ready)

    def _invalidate_object_search(self) -> None:
        self._invalidate_orbital_summary()
        self._object_validated = False
        self.workflow_step = 0
        self._page_previews.clear()
        self._page_frames.clear()
        self.player_frames = []
        self._update_object_actions()
        self._update_workflow_navigation()

    def _continue_to_observation(self) -> None:
        self.workflow_step = max(1, self.workflow_step)
        self._update_workflow_navigation()
        self._activate_workflow_page(0)
        self._set_active_tab(self.tab_buttons[1])

    def _update_preview_hint(self) -> None:
        if not hasattr(self, "translator") or not self.preview_label.property("mapPreviewHint"):
            return
        page = self.right_stack.currentIndex()
        key = {
            1: "Click Plot Solar System to see a map of the object's position relative to the planets.",
            0: "Click Plot altitude chart to view the object's altitude during the night.",
            4: "Click Generate Animation to preview the animation.",
        }.get(page, "Click Generate Map to preview the selected chart type.")
        self.preview_label.setText(self.translator.tr(key))
        self.preview_label.setWordWrap(True)

    def _set_active_tab(self, active_button):
        if not hasattr(self, "tab_buttons"):
            return
        for btn in self.tab_buttons:
            btn.setChecked(btn is active_button)

    def _activate_workflow_page(self, page_index: int) -> None:
        """Switch pages without leaking a chart produced by another page."""
        self.player_timer.stop()
        current_page = self.right_stack.currentIndex()
        if self.player_frames:
            self._page_frames[current_page] = list(self.player_frames)
        self.set_player_frames([])
        self.last_png = None
        self.clear_map_area()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setObjectName("Muted")
        self.preview_label.setProperty("mapPreviewHint", True)
        self.map_area_layout.addWidget(self.preview_label)
        self.right_stack.setCurrentIndex(page_index)
        cached = self._page_previews.get(page_index)
        cached_frames = self._page_frames.get(page_index, [])
        if cached and cached.exists():
            self.show_png(cached)
        if cached_frames:
            self.set_player_frames(cached_frames)
        if not cached:
            self._update_preview_hint()
        if page_index == 0 and (self.orbital_summary.data is not None or self.orbital_summary.calculating):
            self.altitude_details.show()

    def show_center_message(self, message: str, *, color: str = "#ffcc33") -> None:
        """Show an attention message in the projection area when no chart exists."""
        self.clear_map_area()
        self.preview_label = QLabel(message)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(f"color:{color};font-size:18px;font-weight:600;padding:30px;")
        self.map_area_layout.addWidget(self.preview_label)

    def open_favorites(self) -> None:
        from neomapper.infrastructure.favorites import JsonFavoritesRepository
        from neomapper.presentation.favorites import FavoritesDialog
        try:
            dialog = FavoritesDialog(JsonFavoritesRepository(), self.object_edit.text().strip(),
                                     self.language_header_combo.currentText(), self)
            if dialog.exec() == QDialog.Accepted and dialog.selected_designation:
                self.object_edit.setText(dialog.selected_designation)
        except Exception:
            (logs_dir() / "favorites_error.log").write_text(traceback.format_exc(), encoding="utf-8")
            QMessageBox.warning(self, self.translator.tr("Favorites"), self.translator.tr("Could not load favorites"))

    def open_animation_folder(self) -> None:
        import os
        folder = object_output_dir(self.object_edit.text())
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def _update_workflow_navigation(self) -> None:
        """Enable wizard stages progressively while keeping utility pages open."""
        # Tab order: Object, Time, Observing info, Layers, Animation, Settings, About.
        for index, button in enumerate(self.tab_buttons[:4]):
            button.setEnabled(index <= self.workflow_step)
        self.tab_buttons[4].setEnabled(True)
        self.tab_buttons[5].setEnabled(True)

    def _advance_workflow(self) -> None:
        self.workflow_step = min(3, self.workflow_step + 1)
        self._update_workflow_navigation()
        if self.workflow_step < 4:
            target_index = [1, 0, 3, 4][self.workflow_step]
            self._activate_workflow_page(target_index)
            self._set_active_tab(self.tab_buttons[self.workflow_step])

    def _sync_map_datetime(self, value: QDateTime) -> None:
        """Use the Object observation date as the default for the map controls."""
        self.map_date_edit.setDate(value.date())
        self.map_time_edit.setTime(value.time())

    def _map_datetime(self) -> QDateTime:
        return QDateTime(self.map_date_edit.date(), self.map_time_edit.time())

    def _sync_animation_datetime(self, value: QDateTime) -> None:
        """Reset animation defaults when the original observation date changes."""
        self.anim_start_edit.setDateTime(value)
        self.anim_end_edit.setDateTime(value.addSecs(86400))

    def _update_map_type_controls(self) -> None:
        is_sky = (self.map_type_combo.currentData() or self.map_type_combo.currentText()) == "Sky Map"
        self.star_magnitude_combo.setVisible(is_sky)
        self.tr_widgets["Star magnitude limit"].setVisible(is_sky)
        for control in self.visibility_map_controls:
            control.setVisible(not is_sky)

    def _continue_to_animation(self) -> None:
        self.workflow_step = 3
        self._update_workflow_navigation()
        self._activate_workflow_page(4)
        self._set_active_tab(self.tab_buttons[3])

    def _continue_to_layers(self) -> None:
        self.workflow_step = max(2, self.workflow_step)
        self._update_workflow_navigation()
        self._activate_workflow_page(3)
        self._set_active_tab(self.tab_buttons[2])

    def plot_altitude_chart(self) -> None:
        tr = self.translator.tr
        self.plot_altitude_btn.setEnabled(False)
        self.moon_curve_btn.setEnabled(False)
        self.status_label.setText(tr("Generating altitude chart…"))
        self.show_center_message(tr("Generating altitude chart…"))
        try:
            summary_identity = self._summary_identity()
            latitude = float(self.ref_lat_edit.text())
            longitude = float(self.ref_lon_edit.text())
            height = float(self.ref_alt_edit.text() or 0)
            mode = self.time_mode_combo.currentText()
            instant = parse_input_time_for_mode(
                self._map_datetime().toString("yyyy-MM-dd HH:mm:ss"),
                mode, latitude, longitude,
            )
            object_query = self.object_edit.text().strip()
            if not object_query:
                raise ValueError(self.translator.tr("Enter an object first"))
            language = self.language_header_combo.currentText()
            path = object_output_dir(object_query) / f"{safe_filename(object_query)}_altitude_{instant.utc.datetime:%Y%m%d_%H%M%S}.png"
            moon_path = path.with_stem(path.stem + "_moon")
            self.player_timer.stop()
            min_altitude = float(self.obs_min_alt_edit.text() or 0)
            sun_limit = float(self.obs_sun_alt_edit.text() or -12)
            result = self._run_responsive(lambda _emit: build_altitude_chart(
                object_query, instant, latitude, longitude, height, path, language, mode,
                moon_output_png=moon_path,
                min_altitude_deg=min_altitude, sun_limit_deg=sun_limit, return_details=True,
            ))
            if self._summary_identity() != summary_identity:
                return
            self._altitude_chart_details = result if isinstance(result, AltitudeChartResult) else None
            self._altitude_conditions_context = (mode, latitude, longitude)
            if isinstance(result, AltitudeChartResult):
                result = result.path
            self.set_player_frames([])
            self.clear_map_area()
            self.preview_label = QLabel()
            self.preview_label.setAlignment(Qt.AlignCenter)
            self.map_area_layout.addWidget(self.preview_label)
            self._altitude_chart_paths = (result, moon_path)
            self.moon_curve_btn.show()
            self._toggle_moon_curve()
            self.map_title.setText(tr("Altitude chart"))
            self.status_label.setText(tr("Altitude chart saved: {path}", path=result))
        except Exception as exc:
            log_path = logs_dir() / "altitude_chart_error.log"
            log_path.write_text(getattr(exc, "worker_traceback", traceback.format_exc()), encoding="utf-8")
            message = tr("Could not generate altitude chart. Check object, date, location and connection. Log: {path}", path=log_path)
            self.status_label.setText(message)
            QMessageBox.critical(self, tr("Altitude chart"), message)
        finally:
            self.plot_altitude_btn.setEnabled(True)
            self.moon_curve_btn.setEnabled(True)

    def _invalidate_orbital_summary(self) -> None:
        self.orbital_summary.reset()

    def generate_orbital_summary(self) -> None:
        tr = self.translator.tr
        self.orbital_summary_btn.setEnabled(False)
        self.status_label.setText(tr("Calculating orbital summary…"))
        try:
            identity = self._summary_identity()
            object_query = self.object_edit.text().strip()
            if not object_query:
                raise ValueError(tr("Enter an object first"))
            mode = self.time_mode_combo.currentText()
            latitude = float(self.ref_lat_edit.text())
            longitude = float(self.ref_lon_edit.text())
            instant = parse_input_time_for_mode(
                self._map_datetime().toString("yyyy-MM-dd HH:mm:ss"),
                mode, latitude, longitude,
            )
            self.orbital_summary.set_calculating(True)
            if self.right_stack.currentIndex() == 0:
                self.altitude_details.show()
            summary = self._run_responsive(
                lambda _emit: calculate_object_summary(object_query, instant, HorizonsSummaryProvider())
            )
            if self._summary_identity() != identity:
                return
            self.orbital_summary.set_summary(summary, mode, latitude, longitude)
            if self.right_stack.currentIndex() == 0:
                self.altitude_details.show()
            self.status_label.setText(tr("Orbital summary"))
        except Exception as exc:
            log_path = logs_dir() / "object_summary_error.log"
            log_path.write_text(getattr(exc, "worker_traceback", traceback.format_exc()), encoding="utf-8")
            self.orbital_summary.reset()
            message = tr("Enter an object first") if not self.object_edit.text().strip() else tr("Could not calculate orbital summary")
            self.orbital_summary.note.setText(message)
            self.status_label.setText(message)
        finally:
            self.orbital_summary.set_calculating(False)
            self.orbital_summary_btn.setEnabled(True)

    def _summary_identity(self) -> tuple[str, ...]:
        return (self.object_edit.text().strip(), self._map_datetime().toString("yyyy-MM-dd HH:mm:ss"),
                self.time_mode_combo.currentText(), self.ref_lat_edit.text(), self.ref_lon_edit.text(),
                self.ref_alt_edit.text(), self.obs_min_alt_edit.text(), self.obs_sun_alt_edit.text())

    def _update_altitude_conditions(self) -> None:
        details = getattr(self, "_altitude_chart_details", None)
        if details is None:
            return
        from neomapper.shared.utils import format_time_for_map
        mode, latitude, longitude = self._altitude_conditions_context
        observation = details.observation
        best = observation["best"]
        tr = self.translator.tr
        for label, key, instant in (
            (self.window_start_label, "Start window", observation["window_start"]),
            (self.window_best_label, "Best time", best.time),
            (self.window_end_label, "End window", observation["window_stop"]),
        ):
            shown = format_time_for_map(instant, mode, latitude, longitude)[0] if instant is not None else None
            label.setText(tr(key) + "\n" + (f"{shown[11:16]} {mode}" if shown else "—"))
            label.setToolTip(f"{shown} {mode}" if shown else tr("No eligible observing window"))
        if best.time is not None:
            shown = format_time_for_map(best.time, mode, latitude, longitude)[0]
            self.summary_alt.setText(f"{format_number(best.altitude_deg, 1, self.translator.locale, False)}° @ {shown[11:16]} {mode}")
            self.summary_alt.setToolTip(f"{shown} {mode}")
        else:
            self.summary_alt.setText(tr("No eligible observing window"))
            self.summary_alt.setToolTip("")

    def _toggle_moon_curve(self) -> None:
        self.moon_curve_btn.setText(self.translator.tr(
            "Hide Moon" if self.moon_curve_btn.isChecked() else "Show Moon"))
        paths = getattr(self, "_altitude_chart_paths", None)
        if paths:
            path = paths[int(self.moon_curve_btn.isChecked())]
            self.show_png(path)
            self.last_png = path

    def build_footer(self):
        footer = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setValue(0)
        footer.addWidget(self.progress, 1)

        self.status_label = QLabel(self.translator.tr("Ready."))
        self.status_label.setObjectName("Muted")
        footer.addWidget(self.status_label)

        return footer

    def create_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("Section")
        self.tr_widgets[text] = label
        return label

    def create_line_field(self, layout, label, value):
        lab = QLabel(label)
        lab.setObjectName("Muted")
        self.tr_widgets[label] = lab
        edit = QLineEdit(value)
        edit.setMinimumHeight(32)
        layout.addWidget(lab)
        layout.addWidget(edit)
        return edit

    def create_datetime_field(self, layout, label, qdt):
        lab = QLabel(label)
        lab.setObjectName("Muted")
        self.tr_widgets[label] = lab
        dt = QDateTimeEdit(qdt)
        dt.setMinimumHeight(32)
        dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        dt.setCalendarPopup(True)
        layout.addWidget(lab)
        layout.addWidget(dt)
        return dt

    def create_combo_field(self, layout, label, values):
        lab = QLabel(label)
        lab.setObjectName("Muted")
        self.tr_widgets[label] = lab
        combo = QComboBox()
        combo.setMinimumHeight(32)
        combo.addItems(values)
        layout.addWidget(lab)
        layout.addWidget(combo)
        return combo

    def create_check(self, layout, text, checked=True):
        cb = QCheckBox(text)
        self.tr_widgets[text] = cb
        cb.setChecked(checked)
        layout.addWidget(cb)
        return cb

    def create_metric_card(self, layout, label, value, style_name):
        # Do not name this method "metric": QWidget/QMainWindow already has metric().
        card = QFrame()
        card.setObjectName("SubCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 7, 10, 9)

        lab = QLabel(label)
        lab.setObjectName("Muted")
        self.tr_widgets[label] = lab

        val = QLabel(value)
        val.setObjectName(style_name)
        val.setWordWrap(True)

        v.addWidget(lab)
        v.addWidget(val)
        layout.addWidget(card)
        return val

    def clear_map_area(self):
        self.moon_curve_btn.hide()
        self.altitude_details.hide()
        while self.map_area_layout.count():
            item = self.map_area_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def show_png(self, png_path: Path):
        altitude_paths = getattr(self, "_altitude_chart_paths", ())
        is_altitude_chart = Path(png_path) in altitude_paths
        self.altitude_details.setVisible(is_altitude_chart or (self.right_stack.currentIndex() == 0 and (self.orbital_summary.data is not None or self.orbital_summary.calculating)))
        self.moon_curve_btn.setVisible(is_altitude_chart)
        if is_altitude_chart:
            self._update_altitude_conditions()
            self.map_title.setText(self.translator.tr("Altitude chart"))
        self.map_area.layout().activate()
        self.preview_label.setMinimumSize(1, 1)
        self._displayed_png = Path(png_path)
        self.preview_label.setProperty("mapPreviewHint", False)
        pix = QPixmap(str(png_path))
        if pix.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(self.translator.tr("Could not load PNG:\n{path}", path=png_path))
            self.preview_label.setStyleSheet("color:#ff6b6b;")
        else:
            self.preview_label.setText("")
            self.preview_label.setStyleSheet("")
            self.preview_label.setPixmap(pix.scaled(self.plot_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if hasattr(self, "right_stack"):
                self._page_previews[self.right_stack.currentIndex()] = Path(png_path)

    def set_player_frames(self, frame_files):
        previous_transient_dir = self._transient_frames_dir
        self._transient_frames_dir = None
        self.player_timer.stop()
        self.player_play_btn.setText(self.translator.tr("Play"))
        new_frames = [Path(path) for path in frame_files if Path(path).exists()]
        new_frame_dirs = {path.parent.resolve() for path in new_frames}
        if (
            previous_transient_dir is not None
            and previous_transient_dir.resolve() not in new_frame_dirs
        ):
            shutil.rmtree(previous_transient_dir, ignore_errors=True)
        self.player_frames = new_frames
        self.player_index = 0
        count = len(self.player_frames)
        self.player_slider.blockSignals(True)
        self.player_slider.setRange(0, max(0, count - 1))
        self.player_slider.setValue(0)
        self.player_slider.blockSignals(False)
        for widget in (self.player_prev_btn, self.player_play_btn, self.player_next_btn, self.player_slider):
            widget.setEnabled(count > 0)
        self.player_counter.setText(f"1 / {count}" if count else "0 / 0")
        if count:
            self.show_player_frame(0)

    def show_player_frame(self, index):
        if not self.player_frames:
            return
        self.player_index = max(0, min(int(index), len(self.player_frames) - 1))
        self.show_png(self.player_frames[self.player_index])
        self.player_slider.blockSignals(True)
        self.player_slider.setValue(self.player_index)
        self.player_slider.blockSignals(False)
        self.player_counter.setText(f"{self.player_index + 1} / {len(self.player_frames)}")

    def player_seek(self, index):
        self.show_player_frame(index)

    def player_previous_frame(self):
        if self.player_frames:
            self.show_player_frame((self.player_index - 1) % len(self.player_frames))

    def player_next_frame(self):
        if not self.player_frames:
            return
        next_index = self.player_index + 1
        if next_index >= len(self.player_frames):
            if self.player_loop.isChecked():
                next_index = 0
            else:
                self.player_timer.stop()
                self.player_play_btn.setText(self.translator.tr("Play"))
                return
        self.show_player_frame(next_index)

    def toggle_player(self):
        if not self.player_frames:
            return
        if self.player_timer.isActive():
            self.player_timer.stop()
            self.player_play_btn.setText(self.translator.tr("Play"))
        else:
            fps = (1, 4, 8, 15, 25)[self.anim_playback_combo.currentIndex()]
            self.player_timer.start(max(1, round(1000 / fps)))
            self.player_play_btn.setText(self.translator.tr("Pause"))

    def closeEvent(self, event):
        self.player_timer.stop()
        if self._transient_frames_dir is not None:
            shutil.rmtree(self._transient_frames_dir, ignore_errors=True)
            self._transient_frames_dir = None
        super().closeEvent(event)

    def load_site_presets(self):
        presets = {}
        # Built-in starter preset. Y05/Y00 are intentionally not preloaded in v4.0.2.
        presets["Belo Horizonte"] = {"name": "Belo Horizonte, MG, Brazil", "lat": "-19.9", "lon": "-43.9", "alt": "850"}
        for section in self.cfg.sections():
            if section.startswith("preset:"):
                key = section.split(":", 1)[1].strip()
                if key and key.lower() != "custom":
                    presets[key] = {
                        "name": self.cfg.get(section, "name", fallback=key),
                        "lat": self.cfg.get(section, "lat", fallback="0"),
                        "lon": self.cfg.get(section, "lon", fallback="0"),
                        "alt": self.cfg.get(section, "alt", fallback="0"),
                    }
        return presets

    def select_current_preset_from_reference(self):
        cur_name = self.cfg.get("reference", "name", fallback="")
        cur_lat = self.cfg.get("reference", "lat", fallback="")
        cur_lon = self.cfg.get("reference", "lon", fallback="")
        selected = "Custom"
        for preset, data in self.presets.items():
            if data.get("name") == cur_name or (data.get("lat") == cur_lat and data.get("lon") == cur_lon):
                selected = preset
                break
        self.site_preset_combo.blockSignals(True)
        self.site_preset_combo.setCurrentIndex(len(self.presets)) if selected == "Custom" else self.site_preset_combo.setCurrentText(selected)
        self.site_preset_combo.blockSignals(False)

    def _translate_custom_preset(self) -> None:
        index = self.site_preset_combo.count() - 1
        self.site_preset_combo.blockSignals(True)
        self.site_preset_combo.setItemData(index, "Custom")
        self.site_preset_combo.setItemText(index, self.translator.tr("Custom"))
        self.site_preset_combo.blockSignals(False)

    def apply_site_preset(self, preset):
        if self.site_preset_combo.currentData() == "Custom" or preset == "Custom":
            return
        data = self.presets.get(preset)
        if data:
            self.ref_name_edit.setText(data.get("name", preset))
            self.ref_lat_edit.setText(data.get("lat", "0"))
            self.ref_lon_edit.setText(data.get("lon", "0"))
            self.ref_alt_edit.setText(data.get("alt", "0"))

    def save_current_preset(self):
        preset_name = self.ref_name_edit.text().strip() or self.translator.tr("Custom Site")
        section = f"preset:{preset_name}"
        if section not in self.cfg:
            self.cfg[section] = {}
        self.cfg[section]["name"] = preset_name
        self.cfg[section]["lat"] = self.ref_lat_edit.text().strip()
        self.cfg[section]["lon"] = self.ref_lon_edit.text().strip()
        self.cfg[section]["alt"] = self.ref_alt_edit.text().strip() or "0"
        save_config(self.cfg)
        self.presets = self.load_site_presets()
        self.site_preset_combo.blockSignals(True)
        self.site_preset_combo.clear()
        self.site_preset_combo.addItems(list(self.presets.keys()) + ["Custom"])
        self.site_preset_combo.setCurrentText(preset_name)
        self.site_preset_combo.blockSignals(False)
        self._translate_custom_preset()
        self.status_label.setText(self.translator.tr("Preset saved: {name}", name=preset_name))
        self.show_location_preview()

    def update_current_preset(self):
        preset_name = self.site_preset_combo.currentData() or self.site_preset_combo.currentText().strip()
        if preset_name in ("", "Custom", "Belo Horizonte"):
            QMessageBox.information(self, "NEOMapper", self.translator.tr("This preset cannot be updated. Use Save to create a user preset."))
            return
        section = f"preset:{preset_name}"
        if section not in self.cfg:
            self.cfg[section] = {}
        self.cfg[section]["name"] = self.ref_name_edit.text().strip() or preset_name
        self.cfg[section]["lat"] = self.ref_lat_edit.text().strip()
        self.cfg[section]["lon"] = self.ref_lon_edit.text().strip()
        self.cfg[section]["alt"] = self.ref_alt_edit.text().strip() or "0"
        save_config(self.cfg)
        self.presets = self.load_site_presets()
        self.status_label.setText(self.translator.tr("Preset updated: {name}", name=preset_name))
        self.show_location_preview()

    def show_location_preview(self) -> None:
        """Render the selected site on a world map in the main preview area."""
        try:
            name = self.ref_name_edit.text().strip() or "Reference location"
            latitude = float(self.ref_lat_edit.text().strip())
            longitude = float(self.ref_lon_edit.text().strip())
            output = object_output_dir(self.object_edit.text()) / "reference_location_preview.png"
            figure = build_location_figure(name, latitude, longitude, str(output), language=self.language_header_combo.currentText())
            import matplotlib.pyplot as plt
            plt.close(figure)
            self.set_player_frames([])
            self.show_png(output)
            self.map_title.setText(self.translator.tr("Reference location") + f" — {name}")
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "NEOMapper", self.translator.tr("Invalid reference coordinates: {error}", error=exc))

    def plot_solar_system(self) -> None:
        """Plot the heliocentric system for the selected object and date."""
        try:
            self.show_center_message(self.translator.tr("Generating solar-system plot…"))
            object_name = self.object_edit.text().strip()
            if not object_name:
                raise ValueError(self.translator.tr("Enter an object first"))
            date_text = self.datetime_edit.dateTime().toString("yyyy-MM-dd") + " 00:00:00"
            instant = parse_input_time_for_mode(date_text, self.time_mode_combo.currentText(), float(self.ref_lat_edit.text()), float(self.ref_lon_edit.text()))
            from neomapper.infrastructure.ephemeris.solar_system import load_object_orbit
            orbit = self._run_responsive(lambda _emit: load_object_orbit(object_name, instant))
            output = object_output_dir(object_name) / "solar_system_sketch.png"
            figure = build_solar_system_sketch(
                orbit.name, float((orbit.position_au ** 2).sum() ** .5), str(output),
                obstime=instant, semi_major_au=orbit.semi_major_au, eccentricity=orbit.eccentricity,
                object_xy=tuple(orbit.position_au[:2]), object_path_au=orbit.path_au,
                distance_unit=self.distance_unit_combo.currentText(), language=self.language_header_combo.currentText(),
            )
            import matplotlib.pyplot as plt
            plt.close(figure)
            self.set_player_frames([])
            self._distance_preview = (figure, output)
            self.show_png(output)
            self.map_title.setText(self.translator.tr("Solar System sketch"))
        except Exception as exc:
            from neomapper.infrastructure.diagnostics import record_exception
            record_exception("solar_system_error.log")
            QMessageBox.warning(self, "NEOMapper", self.translator.tr("Could not plot the Solar System: {error}", error=exc))

    def delete_current_preset(self):
        preset_name = self.site_preset_combo.currentData() or self.site_preset_combo.currentText().strip()
        if preset_name in ("", "Custom", "Belo Horizonte"):
            QMessageBox.information(self, "NEOMapper", self.translator.tr("This preset cannot be deleted."))
            return
        section = f"preset:{preset_name}"
        reply = QMessageBox.question(self, "NEOMapper", self.translator.tr("Delete preset '{name}'?", name=preset_name), QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        if section in self.cfg:
            self.cfg.remove_section(section)
            save_config(self.cfg)
        self.presets = self.load_site_presets()
        self.site_preset_combo.blockSignals(True)
        self.site_preset_combo.clear()
        self.site_preset_combo.addItems(list(self.presets.keys()) + ["Custom"])
        self.site_preset_combo.setCurrentText("Custom")
        self.site_preset_combo.blockSignals(False)
        self._translate_custom_preset()
        self.status_label.setText(self.translator.tr("Preset deleted: {name}", name=preset_name))

    def set_datetime_now(self):
        if self.time_mode_combo.currentText().upper() == "UTC":
            self.datetime_edit.setDateTime(QDateTime.currentDateTimeUtc())
        else:
            self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.status_label.setText(
            self.translator.tr("Date and time updated")
        )

    def update_language_texts(self):
        lang = (self.language_header_combo.currentText() if hasattr(self, "language_header_combo") else "EN").upper()
        self.orbital_summary.set_language(lang)
        pt = lang == "PT"
        previous = getattr(self, "translator", Translator("EN"))
        for label, key in ((self.status_label, "Ready."), (self.anim_progress_label, "Ready")):
            if label.text() == previous.tr(key):
                label.setText(Translator(lang).tr(key))
        self.translator = Translator(lang)
        self.player_play_btn.setText(self.translator.tr("Pause" if self.player_timer.isActive() else "Play"))
        self.moon_curve_btn.setText(self.translator.tr("Hide Moon" if self.moon_curve_btn.isChecked() else "Show Moon"))
        translations = self.translator.merged()
        self.translations = translations
        if hasattr(self, "distance_unit_combo"):
            self._refresh_distance_cards()
        if self._distance_preview is not None:
            figure, path = self._distance_preview
            if hasattr(figure, "_solar_title_data"):
                update_solar_system_labels(figure, lang, self.distance_unit_combo.currentText())
                figure.savefig(path, dpi=figure.dpi, facecolor=figure.get_facecolor())
                if self._displayed_png == path:
                    self.show_png(path)
        self._translate_custom_preset()
        self.object_section_label.setText(self.translator.tr("Object"))
        # Time Display controls the meaning of the input itself.
        time_label_key = "Date / Time LOCAL" if self.time_mode_combo.currentText().upper() == "LOCAL" else "Date / Time UTC"
        if "Date / Time UTC" in self.tr_widgets:
            self.tr_widgets["Date / Time UTC"].setText(translations.get(time_label_key, time_label_key))
        for key, widget in self.tr_widgets.items():
            if key == "Date / Time UTC":
                continue
            widget.setText(translations.get(key, key))
            explanation = help_text(key, lang)
            if explanation:
                widget.setToolTip(explanation)
        for widget, key in ((self.time_mode_combo, "Time display"),
                            (self.distance_unit_combo, "Distance unit"),
                            (self.obs_min_alt_edit, "Minimum altitude deg"),
                            (self.obs_sun_alt_edit, "Sun altitude limit deg"),
                            (self.orbital_summary_btn, "Orbital summary")):
            widget.setToolTip(help_text(key, lang))
        short_tab_pt = {
            "Object": "Objeto",
            "Obs.\nInformation": "Info.\nObs.",
            "Local": "Local",
            "Time": "Horário",
            "Layers": "Camadas",
            "Animation": "Animação",
            "Settings": "Ajustes",
            "About": "Sobre",
        }
        short_tab_es = {
            "Object": "Objeto",
            "Obs.\nInformation": "Info.\nobservac.",
            "Local": "Local",
            "Time": "Horario",
            "Layers": "Capas",
            "Animation": "Anima-\nción",
            "Settings": "Ajustes",
            "About": "Acerca\nde",
        }
        for key, icon, button in getattr(self, "tab_specs", []):
            if pt:
                tab_text = short_tab_pt.get(key, translations.get(key, key))
            elif lang == "ES":
                tab_text = short_tab_es.get(key, translations.get(key, key))
            else:
                tab_text = translations.get(key, key)
            button.setText(f"{icon}\n{tab_text}")
            button.setMinimumHeight(72 + max(0, tab_text.count("\n")) * 10)
            button.setToolTip(translations.get(key, key).replace("\n", " "))
        self.generate_btn.setText("🗺️  " + translations.get("Generate Map", "Generate Map"))
        box_positions = ["Upper right", "Upper left", "Lower right", "Lower left"]
        current_position = self.obs_box_pos_combo.currentData() or self.obs_box_pos_combo.currentText()
        for index, key in enumerate(box_positions):
            self.obs_box_pos_combo.setItemData(index, key)
            self.obs_box_pos_combo.setItemText(index, translations.get(key, key))
        position_index = self.obs_box_pos_combo.findData(current_position)
        if position_index >= 0:
            self.obs_box_pos_combo.setCurrentIndex(position_index)
        map_types = ["Visibility Map", "Sky Map"]
        for index, key in enumerate(("Very Slow (1 fps)", "Slow (4 fps)", "Normal (8 fps)", "Fast (15 fps)", "Very Fast (25 fps)")):
            self.anim_playback_combo.setItemText(index, self.translator.tr(key))
        self.anim_format_combo.setItemText(3, self.translator.tr("Frames PNG"))
        for index, key in enumerate(("1 min", "5 min", "10 min", "30 min", "1 h", "1 day", "1 week", "1 month", "1 year")):
            self.anim_step_combo.setItemText(index, self.translator.tr(key))
        current_map_type = self.map_type_combo.currentData() or self.map_type_combo.currentText()
        for index, key in enumerate(map_types):
            self.map_type_combo.setItemData(index, key)
            self.map_type_combo.setItemText(index, translations.get(key, key))
        map_type_index = self.map_type_combo.findData(current_map_type)
        if map_type_index >= 0:
            self.map_type_combo.setCurrentIndex(map_type_index)
        self._update_map_type_controls()
        self._update_preview_hint()
        if self.window_start_label.text().endswith("—"):
            self.window_start_label.setText(translations.get("Start window", "Start window") + "\n—")
            self.window_best_label.setText(translations.get("Best time", "Best time") + "\n—")
            self.window_end_label.setText(translations.get("End window", "End window") + "\n—")
        if hasattr(self, "player_loop"):
            self.player_loop.setText(translations.get("Loop", "Loop"))
        if hasattr(self, "map_title") and self.last_png:
            self.map_title.setText(translations.get("Map Preview", "Prévia do Mapa" if pt else "Map Preview") + f" — {self.last_png.name}")
        elif hasattr(self, "map_title"):
            self.map_title.setText(translations.get("Map Preview", "Prévia do Mapa" if pt else "Map Preview"))

    def _refresh_distance_cards(self) -> None:
        if not self.last_result:
            return
        unit = self.distance_unit_combo.currentText()
        language = self.language_header_combo.currentText()
        earth = format_distance(self.last_result.get("geo_km"), unit, language)
        self.summary_dist.setText(earth)
        self.object_earth_distance.setText(earth)
        sun_au = self.last_result.get("heliocentric_distance_au")
        self.object_sun_distance.setText(format_distance(
            None if sun_au is None else float(sun_au) * AU_KM, unit, language
        ))

    def _distance_unit_changed(self, unit: str) -> None:
        self.orbital_summary.set_distance_unit(unit)
        self.cfg["ui"]["distance_unit"] = unit
        save_config(self.cfg)
        self._refresh_distance_cards()
        if self.player_frames:
            self.set_player_frames([])
            self.last_png = None
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setProperty("mapPreviewHint", False)
            self.preview_label.setText(self.translator.tr("Generate the animation again to use the selected distance unit."))
        elif self._distance_preview is not None:
            figure, path = self._distance_preview
            if self._displayed_png == path and not self.preview_label.property("mapPreviewHint"):
                update_figure_distances(figure, unit)
                figure.savefig(path, dpi=figure.dpi, facecolor=figure.get_facecolor())
                self.show_png(path)

    def _save_generation_limit(self, key: str, value: int) -> None:
        self.cfg["limits"][key] = str(value)
        save_config(self.cfg)

    def _save_time_mode(self, mode: str) -> None:
        self._invalidate_orbital_summary()
        self.cfg["time"]["mode"] = mode
        save_config(self.cfg)

    def save_current_settings(self):
        cfg = self.cfg
        if "last" not in cfg:
            cfg["last"] = {}
        cfg["last"]["object"] = self.object_edit.text().strip()
        cfg["reference"]["name"] = self.ref_name_edit.text().strip()
        cfg["reference"]["lat"] = self.ref_lat_edit.text().strip()
        cfg["reference"]["lon"] = self.ref_lon_edit.text().strip()
        cfg["reference"]["alt"] = self.ref_alt_edit.text().strip() or "0"
        cfg["time"]["mode"] = self.time_mode_combo.currentText()
        cfg["ui"]["language"] = self.language_header_combo.currentText()
        cfg["ui"]["distance_unit"] = self.distance_unit_combo.currentText()
        cfg["map"]["render_size"] = self.render_header_combo.currentText()
        cfg["map"]["type"] = self.map_type_combo.currentData() or self.map_type_combo.currentText()
        cfg["map"]["star_magnitude_limit"] = self.star_magnitude_combo.currentText()
        cfg["map"]["dpi"] = self.dpi_edit.text().strip() or "130"
        cfg["map"]["show_terminator"] = "yes" if self.cb_terminator.isChecked() else "no"
        cfg["map"]["show_reference_point"] = "yes" if self.cb_reference_point.isChecked() else "no"
        if "observing" not in cfg:
            cfg["observing"] = {}
        cfg["observing"]["min_altitude"] = self.obs_min_alt_edit.text().strip() or "0"
        cfg["observing"]["sun_altitude_limit"] = self.obs_sun_alt_edit.text().strip() or "-12"
        cfg["observing"]["show_box"] = "yes" if self.cb_obs_box.isChecked() else "no"
        cfg["observing"]["box_position"] = self.obs_box_pos_combo.currentData() or self.obs_box_pos_combo.currentText()
        save_config(cfg)

    def _minutes_from_combo(self, text, custom_text=None):
        text = (text or "").strip().lower()
        if text == "custom":
            try:
                return max(1, int(float(custom_text or "180")))
            except Exception:
                return 180
        if "day" in text:
            return 1440
        if "h" in text:
            try:
                return max(1, int(float(text.split()[0]) * 60))
            except Exception:
                return 60
        try:
            return max(1, int(float(text.split()[0])))
        except Exception:
            return 5

    def cancel_animation_output(self):
        self.animation_cancel_requested = True
        self.status_label.setText(self.translator.tr("Cancel requested. Finishing current frame..."))
        if hasattr(self, "anim_progress_label"):
            self.anim_progress_label.setText(self.translator.tr("Cancel requested. Finishing current frame..."))
        QApplication.processEvents()

    def _start_worker(self, function, on_result, on_error, on_progress=None, on_finished=None):
        worker = BackgroundWorker(function)
        self.active_workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        if on_progress is not None:
            worker.signals.progress.connect(on_progress)

        def cleanup():
            self.active_workers.discard(worker)
            if on_finished is not None:
                on_finished()

        worker.signals.finished.connect(cleanup)
        self.thread_pool.start(worker)

    def _run_responsive(self, function, on_progress=None):
        """Run expensive work in the pool while a local Qt loop keeps the UI responsive."""
        loop = QEventLoop(self)
        outcome = {}
        self._start_worker(
            function,
            lambda value: outcome.__setitem__("result", value),
            lambda value: outcome.__setitem__("error", value),
            on_progress=on_progress,
            on_finished=loop.quit,
        )
        unit_enabled = self.distance_unit_combo.isEnabled()
        self.distance_unit_combo.setEnabled(False)
        try:
            loop.exec()
        finally:
            self.distance_unit_combo.setEnabled(unit_enabled)
        if "error" in outcome:
            exc, worker_traceback = outcome["error"]
            setattr(exc, "worker_traceback", worker_traceback)
            raise exc
        return outcome.get("result")

    def generate_animation_output(self):
        try:
            self.animation_cancel_requested = False
            self.generate_anim_btn.setEnabled(False)
            self.cancel_anim_btn.setEnabled(True)
            self.progress.setValue(5)
            self.status_label.setText(self.translator.tr("Generating animation..."))
            self.show_center_message(self.translator.tr("Generating animation…"))
            if hasattr(self, "anim_progress_label"):
                self.anim_progress_label.setText(self.translator.tr("Rendering frame 0 / ?"))
            QApplication.processEvents()
            self.save_current_settings()

            out_dir = object_output_dir(self.object_edit.text())
            out_dir.mkdir(exist_ok=True)
            safe_obj = safe_filename(self.object_edit.text())
            start_qdt = self.anim_start_edit.dateTime()
            end_qdt = self.anim_end_edit.dateTime()
            if end_qdt <= start_qdt:
                raise ValueError(self.translator.tr("End must be after start"))
            start_txt = start_qdt.toString("yyyy-MM-dd HH:mm:ss")
            end_txt = end_qdt.toString("yyyy-MM-dd HH:mm:ss")
            selected_step = self.anim_step_combo.currentData()
            calendar_step = selected_step if isinstance(selected_step, str) else None
            step_min = selected_step if isinstance(selected_step, int) else 1
            stamp = start_qdt.toString("yyyyMMdd_HHmmss")
            generation_stamp = QDateTime.currentDateTime().toString("HHmmsszzz")
            base_output = out_dir / f"{safe_obj}_animation_{stamp}_{generation_stamp}"

            fmt = self.anim_format_combo.currentText().upper()
            export_gif = "GIF" in fmt
            export_mp4 = "MP4" in fmt
            keep_frames = self.cb_anim_keep_frames.isChecked() or "FRAMES" in fmt or (not export_gif and not export_mp4)
            fps = (1, 4, 8, 15, 25)[self.anim_playback_combo.currentIndex()]
            render_started = time.monotonic()

            def update_animation_progress(payload):
                done, total, _frame_file = payload
                pct = 5 + int((done / max(total, 1)) * 80)
                self.progress.setValue(min(90, pct))
                elapsed = max(0.1, time.monotonic() - render_started)
                if done > 0 and total > done:
                    remaining = int((elapsed / done) * (total - done))
                    eta = self.translator.tr("Remaining {time}", time=f"{remaining//60:02d}:{remaining%60:02d}")
                else:
                    eta = self.translator.tr("Remaining {time}", time="--:--")
                msg = self.translator.tr("Rendering frame {done}/{total} — {eta}", done=done, total=total, eta=eta)
                self.status_label.setText(msg)
                if hasattr(self, "anim_progress_label"):
                    self.anim_progress_label.setText(msg)

            animation_kwargs = dict(
                object_query=self.object_edit.text().strip(), start_time=start_txt,
                end_time=end_txt, base_output=str(base_output), step_minutes=step_min,
                fps=fps, export_gif=export_gif, export_mp4=export_mp4,
                max_frames=self.animation_frame_limit.value(),
                calendar_step=calendar_step,
                # The in-app player needs the rendered PNGs for the lifetime of
                # the window. Frames not requested by the user are removed when
                # replaced or when the application closes.
                keep_frames=True, trail_enabled=self.cb_anim_trail.isChecked(),
                time_label_enabled=False,
                map_type=self.map_type_combo.currentData() or self.map_type_combo.currentText(),
                cancel_callback=lambda: self.animation_cancel_requested,
                dpi=int(self.dpi_edit.text() or 130), watermark_text="ASTRONEOS",
                watermark_size="medium", reference_enabled=self.cb_reference_point.isChecked(),
                reference_name=self.ref_name_edit.text().strip(),
                reference_lat=float(self.ref_lat_edit.text()), reference_lon=float(self.ref_lon_edit.text()),
                show_daynight=self.cb_daynight.isChecked(), show_civil=self.cb_civil.isChecked(),
                show_nautical=self.cb_nautical.isChecked(), show_astro=self.cb_astro.isChecked(),
                show_altitude=self.cb_altitude.isChecked(), show_terminator=self.cb_terminator.isChecked(),
                time_mode=self.time_mode_combo.currentText(), render_size=self.render_header_combo.currentText(),
                language=self.language_header_combo.currentText(),
                distance_unit=self.distance_unit_combo.currentText(),
                show_info_panel=self.cb_anim_info_panel.isChecked(),
                obs_min_altitude=float(self.obs_min_alt_edit.text() or 0),
                obs_sun_altitude_limit=float(self.obs_sun_alt_edit.text() or -12),
                show_obs_box=self.cb_obs_box.isChecked(),
                obs_box_position=self.obs_box_pos_combo.currentData() or self.obs_box_pos_combo.currentText(),
            )

            def render(emit_progress):
                return generate_animation(
                    **animation_kwargs,
                    progress_callback=lambda done, total, frame_file: emit_progress((done, total, frame_file)),
                )

            result = self._run_responsive(render, update_animation_progress)
            # Effective frame times are UTC metadata, potentially clipped by the
            # horizon. Preserve the user's requested interval and input time mode.
            outputs = result.get("outputs") or []
            if not outputs:
                outputs = [result.get("frames_dir", "")]
            self.progress.setValue(100)
            self.status_label.setText(self.translator.tr("Animation ready: {files}", files="; ".join(str(Path(x).name) for x in outputs)))
            self.show_center_message(self.translator.tr("Animation ready. Use the player below or open the animation folder."), color="#7dff9b")
            if hasattr(self, "anim_progress_label"):
                self.anim_progress_label.setText(self.translator.tr("Animation ready: {files}", files="; ".join(str(Path(x).name) for x in outputs)))
            # Preview last generated frame when available.
            frames_dir = Path(result.get("frames_dir", ""))
            last_frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
            if last_frames:
                self.set_player_frames(last_frames)
                if not keep_frames:
                    self._transient_frames_dir = frames_dir
                self.last_png = last_frames[0]
                self.map_title.setText(getattr(self, "translations", {}).get("Map Preview", "Map Preview") + f" — {last_frames[-1].name}")
        except Exception as exc:
            self.progress.setValue(0)
            tb = getattr(exc, "worker_traceback", traceback.format_exc())
            logs = logs_dir()
            logs.mkdir(exist_ok=True)
            log_path = logs / "gui_animation_error.log"
            log_path.write_text(tb, encoding="utf-8")
            self.status_label.setText(self.translator.tr("Animation error: {error}", error=exc))
            self.show_center_message(self.translator.tr("Animation error: {error}", error=exc), color="#ff6b6b")
            if str(exc) == "Animation cancelled by user":
                self.show_center_message(self.translator.tr("Animation cancelled"))
                self.status_label.setText(self.translator.tr("Animation cancelled"))
                if hasattr(self, "anim_progress_label"):
                    self.anim_progress_label.setText(self.translator.tr("Animation cancelled"))
            else:
                QMessageBox.critical(self, self.translator.tr("NEOMapper Animation Error"), self.translator.tr("{error}\n\nLog saved at:\n{path}", error=exc, path=log_path))
        finally:
            self.generate_anim_btn.setEnabled(True)
            self.cancel_anim_btn.setEnabled(False)
            self.animation_cancel_requested = False

    def open_ephemeris_dialog(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle(self.translator.tr("Ephemerides")); form = QFormLayout(dialog)
        start = QDateTimeEdit(QDateTime.currentDateTime()); start.setCalendarPopup(True)
        end = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600)); end.setCalendarPopup(True)
        start.setDisplayFormat("yyyy-MM-dd HH:mm")
        end.setDisplayFormat("yyyy-MM-dd HH:mm")
        from datetime import datetime, timezone
        from neomapper.shared.utils import timezone_from_reference
        zone = timezone.utc if self.time_mode_combo.currentText() == "UTC" else timezone_from_reference(float(self.ref_lat_edit.text()), float(self.ref_lon_edit.text()))[1]
        current = datetime.now(zone).replace(tzinfo=None)
        start.setDateTime(QDateTime(current))
        end.setDateTime(QDateTime(current + timedelta(hours=1)))
        form.addRow(QLabel(self.time_mode_combo.currentText()))
        interval = QSpinBox(); interval.setRange(1, 10080); interval.setValue(10)
        unit = QComboBox(); unit.addItems([self.translator.tr("minute"), self.translator.tr("hour"), self.translator.tr("day")])
        form.addRow(self.translator.tr("Start date and time"), start); form.addRow(self.translator.tr("End date and time"), end)
        form.addRow(self.translator.tr("Interval"), interval); form.addRow(self.translator.tr("Unit"), unit)
        run = QPushButton(self.translator.tr("Save PDF")); print_btn = QPushButton(self.translator.tr("Print PDF"))
        preview_btn = QPushButton(self.translator.tr("View report"))
        preview_btn.setDefault(True)
        actions = QHBoxLayout(); actions.addWidget(preview_btn); actions.addWidget(run); actions.addWidget(print_btn); form.addRow(actions)
        progress_text = QLabel(); form.addRow(progress_text)
        def generate(_checked: bool = False, *, print_report: bool = False, preview: bool = False) -> None:
            try:
                run.setEnabled(False); print_btn.setEnabled(False); preview_btn.setEnabled(False)
                progress_text.setText(self.translator.tr("Searching…"))
                mode = self.time_mode_combo.currentText(); lat=float(self.ref_lat_edit.text()); lon=float(self.ref_lon_edit.text())
                t0=parse_input_time_for_mode(start.dateTime().toString("yyyy-MM-dd HH:mm:ss"), mode, lat, lon); t1=parse_input_time_for_mode(end.dateTime().toString("yyyy-MM-dd HH:mm:ss"), mode, lat, lon)
                unit_text = unit.currentText(); unit_key = next((k for k in ("minute", "hour", "day") if self.translator.tr(k) == unit_text), "minute")
                step = f"{interval.value()}{ {'minute':'m','hour':'h','day':'d'}[unit_key] }"
                object_query = self.object_edit.text().strip()
                if t1 <= t0:
                    raise ValueError(self.translator.tr("End must be after start"))
                max_rows = self.ephemeris_row_limit.value()
                rows = self._run_responsive(lambda _emit: query_report_ephemerides(object_query, t0, t1, step, lat, lon, max_rows=max_rows))
                if preview:
                    from tempfile import TemporaryDirectory
                    from neomapper.presentation.report_preview import ReportPreviewDialog

                    language = self.language_header_combo.currentText()
                    output_dir().mkdir(parents=True, exist_ok=True)
                    with TemporaryDirectory(prefix="report-preview-", dir=output_dir()) as folder:
                        path = str(Path(folder) / "ephemeris_report.pdf")
                        self._run_responsive(lambda _emit: create_ephemeris_pdf(object_query, rows, path, language))
                        progress_text.clear()
                        viewer = ReportPreviewDialog(path, language, dialog)
                        try:
                            viewer.exec()
                        finally:
                            viewer.document.close()
                            viewer.deleteLater()
                    return
                default_path = output_dir() / "ephemeris_report.pdf"
                target = str(default_path) if print_report else QFileDialog.getSaveFileName(self, self.translator.tr("Save PDF"), str(default_path), "PDF (*.pdf)")[0]
                if target:
                    if not target.lower().endswith(".pdf"):
                        target += ".pdf"
                    create_ephemeris_pdf(object_query, rows, target, self.language_header_combo.currentText())
                    if print_report:
                        from neomapper.presentation.pdf_print import print_pdf
                        print_pdf(target, dialog)
                    self.status_label.setText(target); dialog.accept()
            except Exception as exc:
                log_path = logs_dir() / "ephemeris_error.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(traceback.format_exc(), encoding="utf-8")
                from neomapper.application.generation_limits import GenerationLimitError
                message = self.translator.tr("Ephemeris limit exceeded", count=exc.count, limit=exc.limit) if isinstance(exc, GenerationLimitError) else str(exc)
                QMessageBox.critical(self, "NEOMapper", message)
            finally:
                progress_text.clear()
                run.setEnabled(True); print_btn.setEnabled(True); preview_btn.setEnabled(True)
        preview_btn.clicked.connect(lambda _checked=False: generate(preview=True))
        run.clicked.connect(lambda _checked=False: generate()); print_btn.clicked.connect(lambda _checked=False: generate(print_report=True)); dialog.exec()

    def generate_map(self, *, preview: bool = True) -> None:
        search_identity = (self.object_edit.text(), self.datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"))
        if not preview:
            self._invalidate_object_search()
            self._activate_workflow_page(1)
            self._object_search_busy = True
            self._update_object_actions()
        try:
            self.generate_btn.setEnabled(False)
            self.object_search_btn.setEnabled(False)
            self.progress.setValue(5)
            searching = not preview
            message_key = "Searching…" if searching else "Generating map…"
            self.status_label.setText(self.translator.tr(message_key))
            self.show_center_message(self.translator.tr(message_key))

            self.save_current_settings()

            out_dir = object_output_dir(self.object_edit.text())
            out_dir.mkdir(exist_ok=True)

            safe_obj = safe_filename(self.object_edit.text())
            selected_datetime = self._map_datetime() if preview else self.datetime_edit.dateTime()
            time_txt = selected_datetime.toString("yyyy-MM-dd HH:mm:ss")
            stamp = selected_datetime.toString("yyyyMMdd_HHmmss")
            is_sky_map = (self.map_type_combo.currentData() or self.map_type_combo.currentText()) == "Sky Map"
            map_suffix = "sky" if is_sky_map else "visibility"
            output_png = out_dir / f"{safe_obj}_{map_suffix}_{stamp}.png"

            common_kwargs = dict(
                output_png=str(output_png), dpi=int(self.dpi_edit.text() or 130),
                reference_alt=float(self.ref_alt_edit.text() or 0),
                watermark_text="ASTRONEOS", watermark_size="medium",
                reference_name=self.ref_name_edit.text().strip(),
                reference_lat=float(self.ref_lat_edit.text()),
                reference_lon=float(self.ref_lon_edit.text()),
                time_mode=self.time_mode_combo.currentText(),
                render_size=self.render_header_combo.currentText(),
                language=self.language_header_combo.currentText(),
                distance_unit=self.distance_unit_combo.currentText(),
                obs_min_altitude=float(self.obs_min_alt_edit.text() or 0),
                obs_sun_altitude_limit=float(self.obs_sun_alt_edit.text() or -12),
            )
            if is_sky_map:
                common_kwargs["reference_alt"] = float(self.ref_alt_edit.text() or 0)
                common_kwargs["star_magnitude_limit"] = float(self.star_magnitude_combo.currentText())
                builder = build_sky_figure
            else:
                common_kwargs.update(dict(
                    reference_enabled=self.cb_reference_point.isChecked(),
                    show_daynight=self.cb_daynight.isChecked(), show_civil=self.cb_civil.isChecked(),
                    show_nautical=self.cb_nautical.isChecked(), show_astro=self.cb_astro.isChecked(),
                    show_altitude=self.cb_altitude.isChecked(), show_terminator=self.cb_terminator.isChecked(),
                    obs_min_altitude=float(self.obs_min_alt_edit.text() or 0),
                    obs_sun_altitude_limit=float(self.obs_sun_alt_edit.text() or -12),
                    show_obs_box=self.cb_obs_box.isChecked(), obs_box_position=self.obs_box_pos_combo.currentData() or self.obs_box_pos_combo.currentText(),
                ))
                builder = build_visibility_figure
            object_query = self.object_edit.text().strip()
            fig, result = self._run_responsive(
                lambda _emit: builder(object_query, time_txt, **common_kwargs)
            )
            try:
                import matplotlib.pyplot as plt
                plt.close(fig)
            except Exception:
                pass

            self._distance_preview = (fig, output_png) if preview else None
            self.progress.setValue(90)
            self.set_player_frames([])
            self.clear_map_area()
            self.preview_label = QLabel(self.translator.tr("Click Generate Map to preview the selected chart type."))
            self.preview_label.setProperty("mapPreviewHint", not preview)
            self.preview_label.setAlignment(Qt.AlignCenter)
            self.preview_label.setStyleSheet("color:#9aa8b5;font-size:16px;")
            self.map_area_layout.addWidget(self.preview_label)
            if preview:
                self.show_png(output_png)
            else:
                self._update_preview_hint()

            vmag = result.get("vmag")
            ui_language = self.language_header_combo.currentText()
            vmag_txt = "—" if vmag is None else format_number(vmag,1,ui_language,False)
            geo_km = result.get("geo_km", 0)
            try:
                from astroquery.jplhorizons import Horizons
                instant = parse_input_time_for_mode(time_txt, self.time_mode_combo.currentText(), float(self.ref_lat_edit.text()), float(self.ref_lon_edit.text()))
                object_id = object_query.split("/", 1)[0].strip()
                vectors = Horizons(id=object_id, location="@sun", epochs=instant.jd, id_type="designation" if "/" in object_query else "smallbody").vectors()
                result["heliocentric_distance_au"] = sum(float(vectors[k][0]) ** 2 for k in ("x", "y", "z")) ** 0.5
                object_xy = (float(vectors["x"][0]), float(vectors["y"][0]))
                elements = Horizons(id=object_id, location="@sun", epochs=instant.jd, id_type="designation" if "/" in object_query else "smallbody").elements()
                orbit_angle = float(elements["Omega"][0]) + float(elements["w"][0])
                result["solar_object_xy"] = object_xy
                result["solar_orbit_angle"] = orbit_angle
            except Exception:
                result["heliocentric_distance_au"] = None
                result["solar_object_xy"] = None
                result["solar_orbit_angle"] = 0.0

            self.summary_object.setText(str(result.get("targetname", "—")))
            self.summary_time.setText(str(result.get("display_time", time_txt)).replace(".000", "") + " " + str(result.get("display_label", self.time_mode_combo.currentText())))
            self.summary_dist.setText(format_distance(geo_km, self.distance_unit_combo.currentText(), ui_language))
            self.summary_mag.setText(vmag_txt)
            if hasattr(self, "object_earth_distance"):
                self.object_earth_distance.setText(format_distance(geo_km, self.distance_unit_combo.currentText(), ui_language))
            if hasattr(self, "object_sun_distance"):
                sun_distance = result.get("heliocentric_distance_au")
                self.object_sun_distance.setText(
                    format_distance(float(sun_distance) * AU_KM, self.distance_unit_combo.currentText(), ui_language)
                    if sun_distance is not None else "—"
                )
            if hasattr(self, "object_magnitude"):
                self.object_magnitude.setText(vmag_txt)
            best_alt = result.get("best_altitude")
            best_time = result.get("best_altitude_display_time")
            best_label = result.get("best_altitude_display_label") or self.time_mode_combo.currentText()
            best_reason = result.get("best_altitude_reason", "")
            if best_alt is None:
                if str(best_reason).startswith("error:"):
                    self.summary_alt.setText(self.translator.tr("Unavailable"))
                    if hasattr(self, "object_best_alt"):
                        self.object_best_alt.setText(self.translator.tr("Unavailable"))
                elif best_reason == "no_sun_below_limit":
                    sun_limit_txt = self.obs_sun_alt_edit.text().strip() or "-12"
                    self.summary_alt.setText(self.translator.tr("No Sun ≤ {limit}° window", limit=sun_limit_txt))
                    if hasattr(self, "object_best_alt"):
                        self.object_best_alt.setText(self.translator.tr("No Sun ≤ {limit}° window", limit=sun_limit_txt))
                else:
                    self.summary_alt.setText(self.translator.tr("Not observable tonight"))
                    if hasattr(self, "object_best_alt"):
                        self.object_best_alt.setText(self.translator.tr("Not observable tonight"))
            elif best_alt <= 0:
                self.summary_alt.setText(self.translator.tr("{altitude}°\nBelow horizon at night", altitude=format_number(best_alt,1,ui_language,False)))
                if hasattr(self, "object_best_alt"):
                    self.object_best_alt.setText(self.translator.tr("{altitude}°\nBelow horizon at night", altitude=format_number(best_alt,1,ui_language,False)))
            else:
                time_short = str(best_time or "—")
                if len(time_short) >= 16:
                    time_short = time_short[11:16]
                label_short = "UTC" if "UTC" in str(best_label).upper() else "Local"
                self.summary_alt.setText(f"{format_number(best_alt,1,ui_language,False)}° @ {time_short} {label_short}")
                if hasattr(self, "object_best_alt"):
                    self.object_best_alt.setText(f"{format_number(best_alt,1,ui_language,False)}° @ {time_short} {label_short}")
            night = result.get("observing_night_label") or "—"
            w1 = result.get("observing_window_start_display") or "—"
            w2 = result.get("observing_window_stop_display") or "—"
            min_alt = result.get("obs_min_altitude", 0)
            time_mode_label = self.time_mode_combo.currentText()
            if w1 != "—" and w2 != "—":
                start_short = w1[11:16] if len(str(w1)) >= 16 else str(w1)
                end_short = w2[11:16] if len(str(w2)) >= 16 else str(w2)
                best_short = str(best_time or "—")
                if len(best_short) >= 16:
                    best_short = best_short[11:16]
                sun_limit = result.get("obs_sun_altitude_limit", float(self.obs_sun_alt_edit.text() or -12))
                if hasattr(self, "summary_window"):
                    self.summary_window.setText(self.translator.tr("{night}\nObj ≥{altitude}° / Sun ≤{sun}°: {start}–{end} {mode}", night=night, altitude=format_number(min_alt, 0, ui_language), sun=format_number(sun_limit, 0, ui_language), start=start_short, end=end_short, mode=time_mode_label))
                if hasattr(self, "window_start_label"):
                    tr = getattr(self, "translations", {})
                    self.window_start_label.setText(f"{tr.get('Start window', 'Start window')}\n{start_short} {time_mode_label}")
                    self.window_best_label.setText(f"{tr.get('Best time', 'Best time')}\n{best_short} {time_mode_label}")
                    self.window_end_label.setText(f"{tr.get('End window', 'End window')}\n{end_short} {time_mode_label}")
            else:
                if hasattr(self, "summary_window"):
                    self.summary_window.setText(str(night))
                if hasattr(self, "window_start_label"):
                    tr = getattr(self, "translations", {})
                    self.window_start_label.setText(tr.get("Start window", "Start window") + "\n—")
                    self.window_best_label.setText(tr.get("Best time", "Best time") + "\n—")
                    self.window_end_label.setText(tr.get("End window", "End window") + "\n—")
            self.summary_file.setText(output_png.name)
            if hasattr(self, "quick_site_label"):
                self.quick_site_label.setText(f"{self.ref_name_edit.text().strip()}\n{self.ref_lat_edit.text().strip()}, {self.ref_lon_edit.text().strip()} | {self.ref_alt_edit.text().strip()} m")
            if hasattr(self, "quick_time_mode"):
                self.quick_time_mode.setText(self.time_mode_combo.currentText())

            self.last_png = output_png if preview else None
            self.last_result = result
            self._object_validated = search_identity == (self.object_edit.text(), self.datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"))
            self._update_object_actions()
            # A validated object unlocks the next wizard stage.
            source = result.get("ephemeris_source", "JPL Horizons")
            source_note = " — " + self.translator.tr("MPC fallback") if source == "MPC fallback" else ""
            self.status_label.setText(self.translator.tr("Ready{source} — saved {path}", source=source_note, path=output_png))
            self.map_title.setText(getattr(self, "translations", {}).get("Map Preview", "Map Preview") + f" — {output_png.name}")
            self.progress.setValue(100)
            self.generate_btn.setEnabled(True)
            self.object_search_btn.setEnabled(True)

        except Exception as exc:
            self.generate_btn.setEnabled(True)
            self.object_search_btn.setEnabled(True)
            self.progress.setValue(0)
            if hasattr(self, "anim_progress_label"):
                self.anim_progress_label.setText(self.translator.tr("Animation error: {error}", error=exc))
            tb = getattr(exc, "worker_traceback", traceback.format_exc())
            logs = logs_dir()
            logs.mkdir(exist_ok=True)
            log_path = logs / "gui_error.log"
            log_path.write_text(tb, encoding="utf-8")
            if isinstance(exc, ObjectNotFoundError):
                tr = self.translator.tr
                message = tr("Object not found in the JPL or MPC databases. Check the name or designation and try again.")
                self.status_label.setText(message)
                self.anim_progress_label.setText("")
                QMessageBox.warning(self, tr("Object not found"), message)
            else:
                self.status_label.setText(self.translator.tr("Error: {error}", error=exc))
                QMessageBox.critical(self, self.translator.tr("NEOMapper Error"), self.translator.tr("{error}\n\nLog saved at:\n{path}", error=exc, path=log_path))
        finally:
            self._object_search_busy = False
            self._update_object_actions()



def run_app():
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setDesktopFileName("NEOMapper")
    app.setWindowIcon(QIcon(str(application_icon_path())))
    app.setStyleSheet(STYLE)
    window = NEOMapperMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
