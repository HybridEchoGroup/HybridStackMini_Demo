"""Main application window (View layer)."""

import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from gui.graph_viewmodel import GraphViewModel


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

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self._plot_widget)

        # name → PlotDataItem, kept in sync with the ViewModel's channels
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._vm: GraphViewModel | None = None
        self.set_viewmodel(viewmodel or GraphViewModel.with_mock_data())

    # ------------------------------------------------------------------
    # ViewModel binding
    # ------------------------------------------------------------------

    def set_viewmodel(self, vm: GraphViewModel) -> None:
        """Detach from the old ViewModel and attach to a new one."""
        if self._vm is not None:
            self._vm.channels_changed.disconnect(self._on_channels_changed)
            self._vm.channel_data_changed.disconnect(self._on_channel_data_changed)
            self._vm.meta_changed.disconnect(self._on_meta_changed)

        self._vm = vm
        vm.channels_changed.connect(self._on_channels_changed)
        vm.channel_data_changed.connect(self._on_channel_data_changed)
        vm.meta_changed.connect(self._on_meta_changed)

        self._on_meta_changed()
        self._on_channels_changed()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_meta_changed(self) -> None:
        assert self._vm is not None
        self._plot_widget.setTitle(self._vm.title)
        x_label, x_unit = self._vm.x_label
        y_label, y_unit = self._vm.y_label
        self._plot_widget.setLabel("bottom", x_label, units=x_unit)
        self._plot_widget.setLabel("left", y_label, units=y_unit)

    def _on_channels_changed(self) -> None:
        """Full structural rebuild: reconcile curves dict with ViewModel."""
        assert self._vm is not None

        vm_names = {ch.name for ch in self._vm.channels}

        # Remove curves that no longer exist in the ViewModel
        for name in list(self._curves):
            if name not in vm_names:
                self._plot_widget.removeItem(self._curves.pop(name))

        # Rebuild legend before adding/updating items
        self._plot_widget.addLegend()

        for ch in self._vm.channels:
            if not ch.visible:
                # Hide existing curve if present, skip creating a new one
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
                curve = self._plot_widget.plot(
                    ch.x, ch.y, pen=pen, name=ch.name
                )
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
            # Channel appeared for the first time — fall back to full rebuild
            self._on_channels_changed()
