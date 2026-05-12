"""Main application window (View layer)."""

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QLabel,
)

_ASSETS = Path(__file__).parent.parent / "assets"
_LOGO_H = 50  # logo height in pixels

from gui.graph_viewmodel import (
    AcquisitionStatus, ConnectionStatus, GraphViewModel, N_SAMPLES, PicoscopeModel,
    SAMPLE_RATE, V_RANGE,
)
from gui.matched_filter_viewmodel import MatchedFilterViewModel, MF_MAX_DEPTH_M
from gui.theme import DARK_PALETTE as P

_STATUS_COLOR = {
    ConnectionStatus.DISCONNECTED: P.error,
    ConnectionStatus.CONNECTING:   P.highlight,
    ConnectionStatus.CONNECTED:    P.secondary_accent,
    ConnectionStatus.ERROR:        P.error,
}

_STATUS_MESSAGE = {
    ConnectionStatus.DISCONNECTED: "Disconnected",
    ConnectionStatus.CONNECTING:   "Connecting...",
    ConnectionStatus.CONNECTED:    "Connected",
    ConnectionStatus.ERROR:        "Connection failed",
}

_ACQ_COLOR = {
    AcquisitionStatus.IDLE:    P.text_secondary,
    AcquisitionStatus.RUNNING: P.secondary_accent,
    AcquisitionStatus.PAUSED:  P.highlight,
}

_ACQ_LABEL = {
    AcquisitionStatus.IDLE:    "Idle",
    AcquisitionStatus.RUNNING: "Running",
    AcquisitionStatus.PAUSED:  "Paused",
}

_MSG_MARGIN   = 12   # px from window edges
_MSG_DURATION = 3000 # ms


class MainWindow(QMainWindow):
    """View — owns no data, reacts to GraphViewModel signals.

    channels_changed      → full structural rebuild of curve items
    channel_data_changed  → in-place setData() on a single curve (fast path)
    meta_changed          → update title / axis labels only
    """

    def __init__(self, viewmodel: GraphViewModel | None = None) -> None:
        super().__init__()
        self.setWindowTitle("HybridStackMini Demo")
        self.resize(900, 500)

        self.setStyleSheet(f"background-color: {P.background};")

        central = QWidget()
        self.setCentralWidget(central)

        # Top-left overlay: connection dot + acquisition status label
        _DOT = 10
        _dot_style = "border-radius: 5px;"
        _lbl_style = f"color: {{}}; font-size: 11px; background: transparent;"

        self._status_dot = QLabel(central)
        self._status_dot.setFixedSize(QSize(_DOT, _DOT))
        self._status_dot.move(12, 12)
        self._status_dot.setStyleSheet(f"background-color: {P.error}; {_dot_style}")
        self._status_dot.raise_()

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

        # Status message — absolute overlay, bottom-left corner
        self._msg_label = QLabel("", central)
        self._msg_label.setStyleSheet(f"""
            color: {P.text_secondary};
            background-color: {P.panel};
            border: 1px solid {P.border};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
        """)
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

        self._logo_left  = _logo_label("ekfz_logo.png")
        self._logo_right = _logo_label("hybridecho_logo.png")

        layout = QVBoxLayout(central)
        layout.setContentsMargins(120, 32, 120, 32)
        layout.setSpacing(12)

        pg.setConfigOption("background", P.plot_background)
        pg.setConfigOption("foreground", P.text_secondary)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.4)
        self._plot_widget.getPlotItem().getAxis("bottom").setPen(pg.mkPen(P.border))
        self._plot_widget.getPlotItem().getAxis("left").setPen(pg.mkPen(P.border))
        self._plot_widget.setStyleSheet(f"border: 1px solid {P.border}; border-radius: 4px;")
        # Y axis: fixed to ±V_RANGE, mouse interaction disabled
        # X axis: interactive zoom/pan, clamped to the data window
        _duration = N_SAMPLES / SAMPLE_RATE        # 0.002 s
        self._plot_widget.setXRange(0, _duration, padding=0)
        self._plot_widget.setYRange(-V_RANGE, V_RANGE, padding=0)
        self._plot_widget.setLimits(xMin=0, xMax=_duration)
        self._plot_widget.setMouseEnabled(x=True, y=False)

        layout.addWidget(self._plot_widget)

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
        self._mf_plot.setXRange(0, MF_MAX_DEPTH_M, padding=0)
        self._mf_plot.setYRange(-80, 0, padding=0)
        self._mf_plot.setLimits(xMin=0, xMax=MF_MAX_DEPTH_M, yMin=-120, yMax=0)
        self._mf_plot.setMouseEnabled(x=True, y=True)
        self._mf_curve = self._mf_plot.plot(
            [], [], pen=pg.mkPen(color=P.secondary_accent, width=2)
        )
        layout.addWidget(self._mf_plot)

        # Matched filter ViewModel — call load_reference() to arm it
        self._mf_vm = MatchedFilterViewModel(self)
        self._mf_vm.result_ready.connect(self._on_mf_result)

        # --- Model toggle buttons ---
        toggle_style = f"""
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
        self._model_buttons: dict[PicoscopeModel, QPushButton] = {}
        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        for model in PicoscopeModel:
            btn = QPushButton(model.name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(toggle_style)
            btn.clicked.connect(lambda checked, m=model: self._on_model_toggled(m, checked))
            self._model_buttons[model] = btn
            toggle_row.addWidget(btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        def _btn(label: str, color: str, slot) -> QPushButton:
            b = QPushButton(label)
            b.clicked.connect(slot)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(f"""
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
            """)
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

        # name → PlotDataItem, kept in sync with the ViewModel's channels
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._vm: GraphViewModel | None = None
        self.set_viewmodel(viewmodel or GraphViewModel())

        QTimer.singleShot(0, self._reposition_logos)

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

    def _reposition_logos(self) -> None:
        cw = self.centralWidget()
        if cw is None:
            return
        w, h = cw.width(), cw.height()
        m = _MSG_MARGIN
        self._logo_left.move(m, h - self._logo_left.height() - m)
        self._logo_right.move(w - self._logo_right.width() - m, h - self._logo_right.height() - m)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._msg_label.isVisible():
            self._reposition_msg_label()
        self._reposition_logos()

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
        self._mf_vm.process(self._vm.dataB)

    def _on_mf_result(self, x: np.ndarray, y: np.ndarray) -> None:
        self._mf_curve.setData(x, y)

    def _on_acq_status_changed(self, status: AcquisitionStatus) -> None:
        color = _ACQ_COLOR.get(status, P.text_secondary)
        text  = _ACQ_LABEL.get(status, "")
        self._acq_dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        self._acq_label.setText(text)
        self._acq_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        self._acq_label.adjustSize()

    def _on_status_changed(self, status: ConnectionStatus) -> None:
        color = _STATUS_COLOR.get(status, P.error)
        self._status_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )
        self._show_message(_STATUS_MESSAGE.get(status, "Unknown status"))

    def _on_model_toggled(self, model: PicoscopeModel, checked: bool) -> None:
        assert self._vm is not None
        # Uncheck the other button, then update the ViewModel
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

    def _on_meta_changed(self) -> None:
        assert self._vm is not None
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

        self._plot_widget.addLegend(
            labelTextColor=P.text_primary,
            brush=pg.mkBrush(QColor(P.panel)),
            pen=pg.mkPen(P.border),
        )

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
