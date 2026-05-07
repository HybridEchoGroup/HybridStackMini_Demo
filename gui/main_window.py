"""Main application window (View layer)."""

import pyqtgraph as pg
from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy, QLabel,
)

from gui.graph_viewmodel import ConnectionStatus, GraphViewModel, PicoscopeModel
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

        # Status dot — absolute overlay, top-left corner
        _DOT = 10
        self._status_dot = QLabel(central)
        self._status_dot.setFixedSize(QSize(_DOT, _DOT))
        self._status_dot.move(12, 12)
        self._status_dot.setStyleSheet(
            f"background-color: {P.error}; border-radius: {_DOT // 2}px;"
        )
        self._status_dot.raise_()

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
        layout.addWidget(self._plot_widget)

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

        # --- Connect button ---
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        self._connect_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {P.primary_accent};
                color: {P.text_primary};
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {P.hover};
            }}
            QPushButton:pressed {{
                background-color: {P.pressed};
            }}
        """)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._connect_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # name → PlotDataItem, kept in sync with the ViewModel's channels
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._vm: GraphViewModel | None = None
        self.set_viewmodel(viewmodel or GraphViewModel.with_mock_data())

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

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._msg_label.isVisible():
            self._reposition_msg_label()

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

        self._vm = vm
        vm.channels_changed.connect(self._on_channels_changed)
        vm.channel_data_changed.connect(self._on_channel_data_changed)
        vm.meta_changed.connect(self._on_meta_changed)
        vm.model_changed.connect(self._on_model_changed)
        vm.picoscope_status_changed.connect(self._on_status_changed)

        self._on_meta_changed()
        self._on_channels_changed()
        self._on_model_changed(vm.selected_model)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

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
