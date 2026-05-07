"""ViewModel for the graph view.

Usage
-----
    vm = GraphViewModel()

    # --- One-time / structural changes ---
    vm.set_channel("CH A", x, y)        # add channel (picks colour automatically)
    vm.remove_channel("CH A")           # remove channel
    vm.set_channel_visible("CH A", False)
    vm.clear()
    vm.title = "Voltage"
    vm.set_y_label("Voltage", "mV")

    # --- Live / high-frequency data updates ---
    # Call update_channel() in your acquisition callback or QTimer slot.
    # It only updates the stored arrays and emits channel_data_changed(name),
    # which lets the view call setData() in-place — no full redraw needed.
    vm.update_channel("CH A", new_x, new_y)

The view subscribes to all signals; callers never touch the view directly.
"""

from __future__ import annotations
from enum import Enum, auto

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from driver.picoscope import PicoScope, create_backend
from driver.utils import channels, voltage_level


# Default colour palette (matplotlib tab10 subset)
_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]

class PicoscopeModel(Enum):
    """Supported PicoScope hardware models."""
    PS6424E = "6000s"
    PS3406B = "3000s"

class ConnectionStatus(Enum):
    """Connection status for a device."""
    DISCONNECTED = auto()
    CONNECTING   = auto()
    CONNECTED    = auto()
    ERROR        = auto()

@dataclass
class ChannelData:
    name: str
    x: np.ndarray
    y: np.ndarray
    color: str
    width: int = 2
    visible: bool = True

class _WorkerSignals(QObject):
    """Signals for QRunnable workers (QRunnable itself cannot have signals)."""
    finished = pyqtSignal(object)   # carries result on success
    error    = pyqtSignal(str)      # carries error message on failure

class _PicoConnectRunnable(QRunnable):
    def __init__(self, model: str) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self.signals = _WorkerSignals()
        self._model = model

    def run(self) -> None:
        try:
            handler_cls = create_backend(self._model)
            handle = handler_cls()
            self.signals.finished.emit(handle)
        except Exception as e:
            self.signals.error.emit(str(e))

class GraphViewModel(QObject):
    """Holds graph state and notifies the view of changes via signals.

    Signals
    -------
    channels_changed
        Emitted when channels are added, removed, or have their visibility /
        style changed.  The view does a structural rebuild on this signal.
    channel_data_changed(name)
        Emitted when only the x/y data of an existing channel changed.
        The view calls setData() in-place — no full rebuild, suitable for
        high-frequency live updates (e.g. from a PicoScope).
    meta_changed
        Emitted when the title or axis labels change.
    """

    channels_changed = pyqtSignal()
    channel_data_changed = pyqtSignal(str)   # carries the channel name
    meta_changed = pyqtSignal()
    model_changed = pyqtSignal(object)       # carries PicoscopeModel | None

    picoscope_status_changed = pyqtSignal(object) 

    def __init__(self, title: str = "", x_label: str = "Time", x_unit: str = "s",
        y_label: str = "Amplitude", y_unit: str = "V", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._title = title
        self._x_label = x_label
        self._x_unit = x_unit
        self._y_label = y_label
        self._y_unit = y_unit
        self._channels: dict[str, ChannelData] = {}

        self.picoscope_handle: PicoScope | None      = None
        self._picoscope_status = ConnectionStatus.DISCONNECTED
        self._selected_model: PicoscopeModel | None  = None

        self._active: set[str] = set()

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)

    # ------------------------------------------------------------------
    # Meta properties (title / axis labels)
    # ------------------------------------------------------------------

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        if self._title != value:
            self._title = value
            self.meta_changed.emit()

    @property
    def x_label(self) -> tuple[str, str]:
        """Returns (label, unit)."""
        return self._x_label, self._x_unit

    def set_x_label(self, label: str, unit: str = "") -> None:
        self._x_label, self._x_unit = label, unit
        self.meta_changed.emit()

    @property
    def y_label(self) -> tuple[str, str]:
        """Returns (label, unit)."""
        return self._y_label, self._y_unit

    def set_y_label(self, label: str, unit: str = "") -> None:
        self._y_label, self._y_unit = label, unit
        self.meta_changed.emit()

    # ------------------------------------------------------------------
    # Structural channel management  →  triggers channels_changed
    # ------------------------------------------------------------------

    def set_channel(
        self,
        name: str,
        x: np.ndarray,
        y: np.ndarray,
        *,
        color: Optional[str] = None,
        width: int = 2,
    ) -> None:
        """Add a new channel or replace an existing one (full rebuild in view)."""
        if color is None:
            existing = self._channels.get(name)
            color = existing.color if existing else self._next_color()

        self._channels[name] = ChannelData(
            name=name,
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            color=color,
            width=width,
        )
        self.channels_changed.emit()

    def remove_channel(self, name: str) -> None:
        """Remove a channel. No-op if the name does not exist."""
        if name in self._channels:
            del self._channels[name]
            self.channels_changed.emit()

    def set_channel_visible(self, name: str, visible: bool) -> None:
        if name in self._channels and self._channels[name].visible != visible:
            self._channels[name].visible = visible
            self.channels_changed.emit()

    def clear(self) -> None:
        """Remove all channels."""
        if self._channels:
            self._channels.clear()
            self.channels_changed.emit()

    # ------------------------------------------------------------------
    # Live data update  →  triggers channel_data_changed (fast path)
    # ------------------------------------------------------------------

    def update_channel(self, name: str, x: np.ndarray, y: np.ndarray) -> None:
        """Replace the data of an *existing* channel without a structural rebuild.

        The view will call setData() on the existing curve item, which is
        significantly faster than clearing and re-adding all items.
        Use this in your acquisition loop / QTimer slot for live data.

        If the channel does not exist yet, falls back to set_channel().
        """
        if name not in self._channels:
            self.set_channel(name, x, y)
            return

        ch = self._channels[name]
        ch.x = np.asarray(x, dtype=float)
        ch.y = np.asarray(y, dtype=float)
        self.channel_data_changed.emit(name)

    # ------------------------------------------------------------------
    # Read-only access
    # ------------------------------------------------------------------

    @property
    def channels(self) -> list[ChannelData]:
        """Ordered snapshot of all channel data."""
        return list(self._channels.values())

    def get_channel(self, name: str) -> Optional[ChannelData]:
        return self._channels.get(name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_color(self) -> str:
        return _PALETTE[len(self._channels) % len(_PALETTE)]
    
    def _submit(self, key: str, runnable: QRunnable) -> bool:
        """Submit *runnable* to the pool under *key*.

        Returns False (and does not submit) if that key is already active,
        preventing duplicate operations from racing each other.
        """
        if key in self._active:
            return False
        self._active.add(key)
        self._pool.start(runnable)
        return True

    def _release(self, key: str) -> None:
        """Release the active-task guard for *key*."""
        self._active.discard(key)

    # ------------------------------------------------------------------
    # Model selection
    # ------------------------------------------------------------------

    @property
    def selected_model(self) -> PicoscopeModel | None:
        return self._selected_model

    def set_model(self, model: PicoscopeModel | None) -> None:
        if self._selected_model != model:
            self._selected_model = model
            self.model_changed.emit(model)

    # ------------------------------------------------------------------
    # Device control
    # ------------------------------------------------------------------

    def connect(self, model: PicoscopeModel | None) -> None:
        """Connect to the Picoscope"""
        task = _PicoConnectRunnable(model.value if model else "")
        task.signals.finished.connect(self._on_pico_connected)
        task.signals.finished.connect(lambda _: self._release("pico_connect"))
        task.signals.error.connect(self._on_pico_failed)
        task.signals.error.connect(lambda _: self._release("pico_connect"))

        if not self._submit("pico_connect", task):
            return False

        self._picoscope_status = ConnectionStatus.CONNECTING
        self.picoscope_status_changed.emit(self._picoscope_status)
        return True
    
    def disconnect_picoscope(self) -> None:
        if self.picoscope_handle is not None:
            self.picoscope_handle.stop_pico()
        self.picoscope_handle = None
        self._trigger_configured = False
        self._picoscope_status = ConnectionStatus.DISCONNECTED
        self.picoscope_status_changed.emit(self._picoscope_status)

    def _on_pico_connected(self, handle: PicoScope) -> None:
        self.picoscope_handle = handle
        self._trigger_configured = False
        self._picoscope_status = ConnectionStatus.CONNECTED
        self.picoscope_status_changed.emit(self._picoscope_status)

    def _on_pico_failed(self, _msg: str) -> None:
        self._picoscope_status = ConnectionStatus.ERROR
        self.picoscope_status_changed.emit(self._picoscope_status)

    # ------------------------------------------------------------------
    # Mock-data factory
    # ------------------------------------------------------------------

    @classmethod
    def with_mock_data(cls) -> "GraphViewModel":
        """Return a pre-populated ViewModel with two sine-wave channels."""
        vm = cls(title="Mock Signal")
        t = np.linspace(0, 2 * np.pi, 500)
        vm.set_channel("Channel 1", t, np.sin(t))
        vm.set_channel("Channel 2", t, np.sin(2 * t) * 0.5)
        return vm
