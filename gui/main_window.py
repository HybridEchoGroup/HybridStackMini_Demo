"""Main application window (View layer)."""

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QLabel,
    QFileDialog,
)

_ASSETS = Path(__file__).parent.parent / "assets"
_LOGO_H = 90          # logo height for dark-mode HE logo
_LOGO_H_LIGHT_HE = 135  # compensates for the narrower aspect ratio of the light-mode HE logo

import config
from gui.graph_viewmodel import (
    AcquisitionStatus, ConnectionStatus, GraphViewModel, N_SAMPLES, PicoscopeModel,
    SAMPLE_RATE, _TIME_AXIS,
)
from gui.matched_filter_viewmodel import MatchedFilterViewModel
from gui.theme import DARK_PALETTE, LIGHT_PALETTE

_STATUS_MESSAGE = {
    ConnectionStatus.DISCONNECTED: "Disconnected",
    ConnectionStatus.CONNECTING:   "Connecting...",
    ConnectionStatus.CONNECTED:    "Connected",
    ConnectionStatus.ERROR:        "Connection failed",
}

_ACQ_LABEL = {
    AcquisitionStatus.IDLE:    "Idle",
    AcquisitionStatus.RUNNING: "Running",
    AcquisitionStatus.PAUSED:  "Paused",
}

_MSG_MARGIN     = 12   # px from window edges
_MSG_DURATION   = 3000 # ms
_THEME_BTN_SIZE = 28


class MainWindow(QMainWindow):
    """Main Window view
        -> everything data or work related is shifted to viewmodels
        and threads
    """

    def __init__(self, viewmodel: GraphViewModel | None = None) -> None:
        super().__init__()

        self._palette = DARK_PALETTE
        self._is_dark = True
        self._current_conn_status = ConnectionStatus.DISCONNECTED
        self._current_acq_status = AcquisitionStatus.IDLE
        self._use_loopback = False
        self._loaded_ref_length: int | None = None

        self.setWindowTitle("HybridStackMini Demo")
        self.resize(900, 500)

        P = self._palette
        self.setStyleSheet(f"background-color: {P.background};")

        central = QWidget()
        self.setCentralWidget(central)

        # Top-left overlay: connection dot + acquisition status label
        _DOT = 10
        _dot_style = "border-radius: 5px;"
        _lbl_style = "color: {}; font-size: 11px; background: transparent;"

        self._status_dot = QLabel(central)
        self._status_dot.setFixedSize(QSize(_DOT, _DOT))
        self._status_dot.move(12, 12)
        self._status_dot.setStyleSheet(f"background-color: {P.error}; {_dot_style}")
        self._status_dot.raise_()

        self._status_label = QLabel("Idle", central)
        self._status_label.setStyleSheet(_lbl_style.format(P.text_secondary))
        self._status_label.adjustSize()
        self._status_label.move(26, 8)
        self._status_label.raise_()

        self._acq_dot = QLabel(central)
        self._acq_dot.setFixedSize(QSize(_DOT, _DOT))
        self._acq_dot.move(12, 30)
        self._acq_dot.setStyleSheet(f"background-color: {P.text_secondary}; {_dot_style}")
        self._acq_dot.raise_()

        self._acq_label = QLabel("Idle", central)
        self._acq_label.setStyleSheet(_lbl_style.format(P.text_secondary))
        self._acq_label.adjustSize()
        self._acq_label.move(26, 26)
        self._acq_label.raise_()

        # Top-right overlay: dark/light mode toggle
        self._theme_btn = QPushButton("☀", central)
        self._theme_btn.setFixedSize(QSize(_THEME_BTN_SIZE, _THEME_BTN_SIZE))
        self._theme_btn.setToolTip("Switch to light mode")
        self._theme_btn.setStyleSheet(self._theme_btn_style())
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn.raise_()

        # Status message — absolute overlay, bottom-left corner
        self._msg_label = QLabel("", central)
        self._msg_label.setStyleSheet(self._msg_style())
        self._msg_label.hide()
        self._msg_label.raise_()

        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(self._msg_label.hide)

        def _logo_label(filename: str) -> QLabel:
            lbl = QLabel(central)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            px = QPixmap(str(_ASSETS / filename))
            lbl.setPixmap(px.scaledToHeight(_LOGO_H, Qt.TransformationMode.SmoothTransformation))
            lbl.adjustSize()
            lbl.raise_()
            return lbl

        self._logo_left  = _logo_label("ekfz_logo_white.png")
        self._logo_right = _logo_label("hybridecho_logo.png")

        layout = QVBoxLayout(central)
        layout.setContentsMargins(120, 32, 120, 32)
        layout.setSpacing(12)

        pg.setConfigOption("background", P.plot_background)
        pg.setConfigOption("foreground", P.text_secondary)
        pg.setConfigOption("useOpenGL", True)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.4)
        self._plot_widget.getPlotItem().getAxis("bottom").setPen(pg.mkPen(P.border))
        self._plot_widget.getPlotItem().getAxis("left").setPen(pg.mkPen(P.border))
        self._plot_widget.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
        _duration = N_SAMPLES / SAMPLE_RATE        # 0.002 s
        self._plot_widget.setXRange(0, _duration, padding=0)
        self._plot_widget.setYRange(-config.CH_B_DISPLAY_RANGE_MV, config.CH_B_DISPLAY_RANGE_MV, padding=0)
        self._plot_widget.setLimits(xMin=0, xMax=_duration)
        self._plot_widget.setMouseEnabled(x=True, y=False)

        # --- Loopback plot (CH A) ---
        self._loopback_plot = pg.PlotWidget()
        self._loopback_plot.setTitle("Loopback", color=P.text_primary, size="11pt")
        self._loopback_plot.showGrid(x=True, y=True, alpha=0.4)
        self._loopback_plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen(P.border))
        self._loopback_plot.getPlotItem().getAxis("left").setPen(pg.mkPen(P.border))
        self._loopback_plot.setLabel("bottom", "Time", units="s",
                                     **{"color": P.text_secondary, "font-size": "10pt"})
        self._loopback_plot.setLabel("left", "Voltage", units="mV",
                                     **{"color": P.text_secondary, "font-size": "10pt"})
        self._loopback_plot.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
        self._loopback_plot.setXRange(0, _duration, padding=0)
        self._loopback_plot.setYRange(-config.CH_A_DISPLAY_RANGE_MV, config.CH_A_DISPLAY_RANGE_MV, padding=0)
        self._loopback_plot.setLimits(xMin=0, xMax=_duration)
        self._loopback_plot.setMouseEnabled(x=True, y=False)
        self._loopback_curve = self._loopback_plot.plot(
            [], [], pen=pg.mkPen(color=P.highlight, width=2)
        )

        upper_row = QHBoxLayout()
        upper_row.setSpacing(12)
        upper_row.addWidget(self._plot_widget)
        upper_row.addWidget(self._loopback_plot)
        layout.addLayout(upper_row)

        # --- Matched filter plot ---
        self._mf_plot = pg.PlotWidget()
        self._mf_plot.setTitle("Matched Filter Output", color=P.text_primary, size="11pt")
        self._mf_plot.showGrid(x=True, y=True, alpha=0.4)
        self._mf_plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen(P.border))
        self._mf_plot.getPlotItem().getAxis("left").setPen(pg.mkPen(P.border))
        self._mf_plot.setLabel("bottom", "Depth", units="m",
                               **{"color": P.text_secondary, "font-size": "10pt"})
        self._mf_plot.setLabel("left", "Correlation",
                               units="dBFS", **{"color": P.text_secondary, "font-size": "10pt"})
        self._mf_plot.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
        self._mf_plot.setXRange(0, config.MF_MAX_DEPTH_M, padding=0)
        self._mf_plot.setYRange(-60, 0, padding=0)
        self._mf_plot.setLimits(xMin=0, xMax=config.MF_MAX_DEPTH_M, yMin=-60, yMax=0)
        self._mf_plot.setMouseEnabled(x=True, y=False)
        self._mf_curve = self._mf_plot.plot(
            [], [], pen=pg.mkPen(color=P.secondary_accent, width=2)
        )

        # --- Ambiguity function plot (autocorrelation of reference) ---
        self._af_plot = pg.PlotWidget()
        self._af_plot.setTitle("Ambiguity Function", color=P.text_primary, size="11pt")
        self._af_plot.showGrid(x=True, y=True, alpha=0.4)
        self._af_plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen(P.border))
        self._af_plot.getPlotItem().getAxis("left").setPen(pg.mkPen(P.border))
        self._af_plot.setLabel("bottom", "Lag", units="m",
                               **{"color": P.text_secondary, "font-size": "10pt"})
        self._af_plot.setLabel("left", "Autocorrelation",
                               units="dB", **{"color": P.text_secondary, "font-size": "10pt"})
        self._af_plot.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
        self._af_plot.setXRange(-config.MF_MAX_DEPTH_M, config.MF_MAX_DEPTH_M, padding=0)
        self._af_plot.setYRange(-60, 0, padding=0)
        self._af_plot.setLimits(xMin=-config.MF_MAX_DEPTH_M, xMax=config.MF_MAX_DEPTH_M, yMin=-60, yMax=0)
        self._af_plot.setMouseEnabled(x=True, y=False)
        self._af_curve = self._af_plot.plot(
            [], [], pen=pg.mkPen(color=P.highlight, width=2)
        )

        lower_row = QHBoxLayout()
        lower_row.setSpacing(12)
        lower_row.addWidget(self._mf_plot)
        lower_row.addWidget(self._af_plot)
        layout.addLayout(lower_row)

        # Matched filter ViewModel — call load_reference() to arm it
        self._mf_vm = MatchedFilterViewModel(self)
        self._mf_vm.result_ready.connect(self._on_mf_result)
        self._mf_vm.ambiguity_ready.connect(self._on_af_result)

        # --- Model toggle buttons ---
        self._model_buttons: dict[PicoscopeModel, QPushButton] = {}
        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        for model in PicoscopeModel:
            btn = QPushButton(model.name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(self._toggle_style())
            btn.clicked.connect(lambda checked, m=model: self._on_model_toggled(m, checked))
            self._model_buttons[model] = btn
            toggle_row.addWidget(btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        def _btn(label: str, color: str, slot) -> QPushButton:
            b = QPushButton(label)
            b.clicked.connect(slot)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(self._action_btn_style(color))
            return b

        # --- Connect / Disconnect row ---
        self._connect_btn    = _btn("Connect",    P.primary_accent,    self._on_connect_clicked)
        self._disconnect_btn = _btn("Disconnect", P.panel,             self._on_disconnect_clicked)

        conn_row = QHBoxLayout()
        conn_row.addStretch()
        conn_row.addWidget(self._connect_btn)
        conn_row.addWidget(self._disconnect_btn)
        conn_row.addStretch()
        layout.addLayout(conn_row)

        # --- Start / Pause row ---
        self._start_btn = _btn("Start", P.secondary_accent, self._on_start_clicked)
        self._pause_btn = _btn("Pause", P.highlight,        self._on_pause_clicked)

        ctrl_row = QHBoxLayout()
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._start_btn)
        ctrl_row.addWidget(self._pause_btn)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # --- Load Reference / Loopback / Load Config row ---
        self._load_ref_btn = _btn("Load Reference", P.panel, self._on_load_reference_clicked)
        self._load_ref_btn.setStyleSheet(self._load_ref_style())

        self._loopback_btn = QPushButton("Loopback: CH A")
        self._loopback_btn.setCheckable(True)
        self._loopback_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._loopback_btn.setStyleSheet(self._toggle_style())
        self._loopback_btn.setToolTip("Use live Channel A signal as matched filter reference")
        self._loopback_btn.clicked.connect(self._on_loopback_toggled)

        self._load_config_btn = _btn("Load Config", P.panel, self._on_load_config_clicked)
        self._load_config_btn.setStyleSheet(self._load_ref_style())

        ref_row = QHBoxLayout()
        ref_row.addStretch()
        ref_row.addWidget(self._load_ref_btn)
        ref_row.addWidget(self._loopback_btn)
        ref_row.addWidget(self._load_config_btn)
        ref_row.addStretch()
        layout.addLayout(ref_row)

        # name → PlotDataItem, kept in sync with the ViewModel's channels
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._vm: GraphViewModel | None = None
        self.set_viewmodel(viewmodel or GraphViewModel())

        QTimer.singleShot(0, self._reposition_overlays)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    def _toggle_style(self) -> str:
        P = self._palette
        return f"""
            QPushButton {{
                background-color: {P.panel};
                color: {P.text_secondary};
                border: 1px solid {P.border};
                border-radius: 4px;
                padding: 5px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {P.hover};
                color: {P.text_primary};
            }}
            QPushButton:checked {{
                background-color: {P.primary_accent};
                color: {P.text_primary};
                border-color: {P.primary_accent};
            }}
        """

    def _action_btn_style(self, color: str) -> str:
        P = self._palette
        return f"""
            QPushButton {{
                background-color: {color};
                color: {P.text_primary};
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }}
            QPushButton:hover   {{ background-color: {P.hover}; }}
            QPushButton:pressed {{ background-color: {P.pressed}; }}
        """

    def _load_ref_style(self) -> str:
        P = self._palette
        return f"""
            QPushButton {{
                background-color: {P.panel};
                color: {P.text_secondary};
                border: 1px solid {P.border};
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }}
            QPushButton:hover   {{ background-color: {P.hover}; color: {P.text_primary}; }}
            QPushButton:pressed {{ background-color: {P.pressed}; }}
        """

    def _theme_btn_style(self) -> str:
        P = self._palette
        return f"""
            QPushButton {{
                background-color: {P.panel};
                color: {P.text_primary};
                border: 1px solid {P.border};
                border-radius: 4px;
                font-size: 15px;
                padding: 0px;
            }}
            QPushButton:hover   {{ background-color: {P.hover}; }}
            QPushButton:pressed {{ background-color: {P.pressed}; }}
        """

    def _msg_style(self) -> str:
        P = self._palette
        return f"""
            color: {P.text_secondary};
            background-color: {P.panel};
            border: 1px solid {P.border};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
        """

    # ------------------------------------------------------------------
    # Theme toggle
    # ------------------------------------------------------------------

    def _toggle_theme(self) -> None:
        self._is_dark = not self._is_dark
        self._palette = DARK_PALETTE if self._is_dark else LIGHT_PALETTE
        self._theme_btn.setText("☀" if self._is_dark else "🌙")
        self._theme_btn.setToolTip(
            "Switch to light mode" if self._is_dark else "Switch to dark mode"
        )
        self._apply_theme()

    def _apply_theme(self) -> None:
        P = self._palette

        self.setStyleSheet(f"background-color: {P.background};")
        self._msg_label.setStyleSheet(self._msg_style())

        for plot in (self._plot_widget, self._mf_plot, self._loopback_plot, self._af_plot):
            plot.setBackground(P.plot_background)
            plot.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
            for axis_name in ("bottom", "left"):
                axis = plot.getPlotItem().getAxis(axis_name)
                axis.setPen(pg.mkPen(P.border))
                axis.setTextPen(pg.mkPen(P.text_secondary))

        self._mf_plot.setTitle("Matched Filter Output", color=P.text_primary, size="11pt")
        self._mf_plot.setLabel("bottom", "Depth", units="m",
                               **{"color": P.text_secondary, "font-size": "10pt"})
        self._mf_plot.setLabel("left", "Correlation",
                               units="dBFS", **{"color": P.text_secondary, "font-size": "10pt"})
        self._mf_curve.setPen(pg.mkPen(color=P.secondary_accent, width=2))

        self._af_plot.setTitle("Ambiguity Function", color=P.text_primary, size="11pt")
        self._af_plot.setLabel("bottom", "Lag", units="m",
                               **{"color": P.text_secondary, "font-size": "10pt"})
        self._af_plot.setLabel("left", "Autocorrelation",
                               units="dB", **{"color": P.text_secondary, "font-size": "10pt"})
        self._af_curve.setPen(pg.mkPen(color=P.highlight, width=2))

        self._loopback_plot.setTitle("Loopback (CH A)", color=P.text_primary, size="11pt")
        self._loopback_plot.setLabel("bottom", "Time", units="s",
                                     **{"color": P.text_secondary, "font-size": "10pt"})
        self._loopback_plot.setLabel("left", "Voltage", units="mV",
                                     **{"color": P.text_secondary, "font-size": "10pt"})
        self._loopback_curve.setPen(pg.mkPen(color=P.highlight, width=2))

        for btn in self._model_buttons.values():
            btn.setStyleSheet(self._toggle_style())

        self._connect_btn.setStyleSheet(self._action_btn_style(P.primary_accent))
        self._disconnect_btn.setStyleSheet(self._action_btn_style(P.panel))
        self._start_btn.setStyleSheet(self._action_btn_style(P.secondary_accent))
        self._pause_btn.setStyleSheet(self._action_btn_style(P.highlight))
        self._load_ref_btn.setStyleSheet(self._load_ref_style())
        self._load_config_btn.setStyleSheet(self._load_ref_style())
        self._loopback_btn.setStyleSheet(self._toggle_style())
        self._theme_btn.setStyleSheet(self._theme_btn_style())

        pg.setConfigOption("background", P.plot_background)
        pg.setConfigOption("foreground", P.text_secondary)

        he_logo = "hybridecho_logo.png" if self._is_dark else "HE_logo_rot_transparent.png"
        he_h = _LOGO_H if self._is_dark else _LOGO_H_LIGHT_HE
        px = QPixmap(str(_ASSETS / he_logo))
        self._logo_right.setPixmap(px.scaledToHeight(he_h, Qt.TransformationMode.SmoothTransformation))
        self._logo_right.adjustSize()

        ekfz_logo = "ekfz_logo_white.png" if self._is_dark else "ekfz_logo_blue.png"
        ekfz_h = _LOGO_H
        px = QPixmap(str(_ASSETS / ekfz_logo))
        self._logo_left.setPixmap(px.scaledToHeight(ekfz_h, Qt.TransformationMode.SmoothTransformation))
        self._logo_left.adjustSize()

        # Re-apply current status colours without triggering the status message popup
        self._on_status_changed(self._current_conn_status, show_message=False)
        self._on_acq_status_changed(self._current_acq_status)
        self._on_meta_changed()
        self._on_channels_changed()
        self._reposition_overlays()

    # ------------------------------------------------------------------
    # Overlay helpers
    # ------------------------------------------------------------------

    def _show_message(self, text: str, duration_ms: int = _MSG_DURATION) -> None:
        self._msg_label.setText(text)
        self._msg_label.adjustSize()
        self._reposition_msg_label()
        self._msg_label.show()
        self._msg_label.raise_()
        self._msg_timer.start(duration_ms)

    def _reposition_msg_label(self) -> None:
        cw = self.centralWidget()
        if cw is None:
            return
        h = cw.height()
        lh = self._msg_label.height()
        self._msg_label.move(_MSG_MARGIN, h - lh - _MSG_MARGIN)

    def _reposition_overlays(self) -> None:
        cw = self.centralWidget()
        if cw is None:
            return
        w, h = cw.width(), cw.height()
        m = _MSG_MARGIN
        self._logo_left.move(m, h - self._logo_left.height() - m)
        self._logo_right.move(w - self._logo_right.width() - m, h - self._logo_right.height() - m)
        self._theme_btn.move(w - _THEME_BTN_SIZE - m, m)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._msg_label.isVisible():
            self._reposition_msg_label()
        self._reposition_overlays()

    # ------------------------------------------------------------------
    # ViewModel binding
    # ------------------------------------------------------------------

    def set_viewmodel(self, vm: GraphViewModel) -> None:
        """Detach from the old ViewModel and attach to a new one."""
        if self._vm is not None:
            self._vm.channels_changed.disconnect(self._on_channels_changed)
            self._vm.channel_data_changed.disconnect(self._on_channel_data_changed)
            self._vm.meta_changed.disconnect(self._on_meta_changed)
            self._vm.model_changed.disconnect(self._on_model_changed)
            self._vm.picoscope_status_changed.disconnect(self._on_status_changed)
            self._vm.acquisition_status_changed.disconnect(self._on_acq_status_changed)
            self._vm.live_data_ready.disconnect(self._on_live_data_ready)

        self._vm = vm
        vm.channels_changed.connect(self._on_channels_changed)
        vm.channel_data_changed.connect(self._on_channel_data_changed)
        vm.meta_changed.connect(self._on_meta_changed)
        vm.model_changed.connect(self._on_model_changed)
        vm.picoscope_status_changed.connect(self._on_status_changed)
        vm.acquisition_status_changed.connect(self._on_acq_status_changed)
        vm.live_data_ready.connect(self._on_live_data_ready)

        self._on_meta_changed()
        self._on_channels_changed()
        self._on_model_changed(vm.selected_model)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_live_data_ready(self) -> None:
        assert self._vm is not None
        if len(self._vm.dataA) > 0:
            self._loopback_curve.setData(_TIME_AXIS, self._vm.dataA)
            if self._use_loopback:
                if self._loaded_ref_length is not None:
                    crop = min(self._loaded_ref_length, len(self._vm.dataA))
                else:
                    ref = self._mf_vm.reference
                    crop = min(len(ref) + config.LOOPBACK_EXTRA_SAMPLES, len(self._vm.dataA)) if ref is not None else len(self._vm.dataA)
                self._mf_vm.set_reference(self._vm.dataA[:crop])
        self._mf_vm.process(self._vm.dataB)

    def _on_mf_result(self, x: np.ndarray, y: np.ndarray) -> None:
        self._mf_curve.setData(x / 2, y)

    def _on_af_result(self, x: np.ndarray, y: np.ndarray) -> None:
        self._af_curve.setData(x, y)

    def _on_acq_status_changed(self, status: AcquisitionStatus) -> None:
        self._current_acq_status = status
        P = self._palette
        color = {
            AcquisitionStatus.IDLE:    P.text_secondary,
            AcquisitionStatus.RUNNING: P.secondary_accent,
            AcquisitionStatus.PAUSED:  P.highlight,
        }.get(status, P.text_secondary)
        text = _ACQ_LABEL.get(status, "")
        self._acq_dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self._acq_label.setText(text)
        self._acq_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        self._acq_label.adjustSize()

    def _on_status_changed(self, status: ConnectionStatus, *, show_message: bool = True) -> None:
        self._current_conn_status = status
        P = self._palette
        color = {
            ConnectionStatus.DISCONNECTED: P.error,
            ConnectionStatus.CONNECTING:   P.highlight,
            ConnectionStatus.CONNECTED:    P.secondary_accent,
            ConnectionStatus.ERROR:        P.error,
        }.get(status, P.error)
        text = _STATUS_MESSAGE.get(status, "")
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        self._status_label.adjustSize()
        if show_message:
            self._show_message(_STATUS_MESSAGE.get(status, "Unknown status"))

    def _on_model_toggled(self, model: PicoscopeModel, checked: bool) -> None:
        assert self._vm is not None
        for m, btn in self._model_buttons.items():
            if m != model:
                btn.setChecked(False)
        self._vm.set_model(model if checked else None)

    def _on_model_changed(self, model: PicoscopeModel | None) -> None:
        for m, btn in self._model_buttons.items():
            btn.setChecked(m == model)
        if model is not None:
            self._show_message(f"Model {model.name} selected")

    def _on_connect_clicked(self) -> None:
        assert self._vm is not None
        self._vm.connect(self._vm.selected_model)

    def _on_disconnect_clicked(self) -> None:
        assert self._vm is not None
        self._vm.disconnect()

    def _on_start_clicked(self) -> None:
        assert self._vm is not None
        self._vm.start()

    def _on_pause_clicked(self) -> None:
        assert self._vm is not None
        self._vm.pause()

    def _on_loopback_toggled(self, checked: bool) -> None:
        self._use_loopback = checked
        if checked:
            self._show_message("Loopback: using CH A as reference")
        else:
            self._mf_vm.load_default_reference()
            self._show_message("Loopback off: using ideal reference")

    def _on_load_reference_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Reference Signal", "", "Binary files (*.bin);;All files (*)"
        )
        if path:
            self._mf_vm.load_reference(path)
            ref = self._mf_vm.reference
            self._loaded_ref_length = len(ref) if ref is not None else None
            self._show_message(f"Reference loaded: {Path(path).name}")

    def _on_load_config_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "", "TOML files (*.toml);;All files (*)"
        )
        if not path:
            return
        config.reload(path)
        self._mf_vm.update_from_config()
        self._plot_widget.setYRange(-config.CH_B_DISPLAY_RANGE_MV, config.CH_B_DISPLAY_RANGE_MV, padding=0)
        self._loopback_plot.setYRange(-config.CH_A_DISPLAY_RANGE_MV, config.CH_A_DISPLAY_RANGE_MV, padding=0)
        self._mf_plot.setXRange(0, config.MF_MAX_DEPTH_M, padding=0)
        self._mf_plot.setLimits(xMin=0, xMax=config.MF_MAX_DEPTH_M, yMin=-60, yMax=0)
        self._af_plot.setXRange(-config.MF_MAX_DEPTH_M, config.MF_MAX_DEPTH_M, padding=0)
        self._af_plot.setLimits(xMin=-config.MF_MAX_DEPTH_M, xMax=config.MF_MAX_DEPTH_M, yMin=-60, yMax=0)
        self._show_message(f"Config loaded: {Path(path).name} — hardware settings apply on next Start")

    def _on_meta_changed(self) -> None:
        assert self._vm is not None
        P = self._palette
        self._plot_widget.setTitle(self._vm.title, color=P.text_primary, size="11pt")
        x_label, x_unit = self._vm.x_label
        y_label, y_unit = self._vm.y_label
        label_style = {"color": P.text_secondary, "font-size": "10pt"}
        self._plot_widget.setLabel("bottom", x_label, units=x_unit, **label_style)
        self._plot_widget.setLabel("left", y_label, units=y_unit, **label_style)

    def _on_channels_changed(self) -> None:
        """Full structural rebuild: reconcile curves dict with ViewModel."""
        assert self._vm is not None

        vm_names = {ch.name for ch in self._vm.channels}

        for name in list(self._curves):
            if name not in vm_names:
                self._plot_widget.removeItem(self._curves.pop(name))

        for ch in self._vm.channels:
            if not ch.visible:
                if ch.name in self._curves:
                    self._curves[ch.name].setVisible(False)
                continue

            pen = pg.mkPen(color=ch.color, width=ch.width)

            if ch.name in self._curves:
                curve = self._curves[ch.name]
                curve.setData(ch.x, ch.y)
                curve.setPen(pen)
                curve.setVisible(True)
            else:
                curve = self._plot_widget.plot(ch.x, ch.y, pen=pen, name=ch.name)
                self._curves[ch.name] = curve

    def _on_channel_data_changed(self, name: str) -> None:
        """Fast path: update a single curve's data without any rebuild."""
        assert self._vm is not None
        ch = self._vm.get_channel(name)
        if ch is None:
            return

        if name in self._curves:
            self._curves[name].setData(ch.x, ch.y)
        else:
            self._on_channels_changed()
