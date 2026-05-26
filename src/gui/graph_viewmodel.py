"""GraphViewModel — channel state and plot metadata for the waveform view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from config import N_SAMPLES, SAMPLE_RATE, TIMEBASE   # baked into _TIME_AXIS at startup

import logging
_log = logging.getLogger(__name__)

_TIME_AXIS = np.linspace(0, N_SAMPLES / SAMPLE_RATE, N_SAMPLES)  # seconds

# Default colour palette (matplotlib tab10 subset)
_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
]


@dataclass
class ChannelData:
    name:    str
    x:       np.ndarray
    y:       np.ndarray
    color:   str
    width:   int  = 2
    visible: bool = True


class GraphViewModel(QObject):
    """Holds channel state and notifies the view of changes via signals.

    Signals
    -------
    channels_changed
        Emitted when channels are added, removed, or have their visibility /
        style changed.  The view does a structural rebuild on this signal.
    channel_data_changed(name)
        Emitted when only the x/y data of an existing channel changed.
        The view calls setData() in-place — suitable for high-frequency updates.
    meta_changed
        Emitted when the title or axis labels change.
    """

    channels_changed     = pyqtSignal()
    channel_data_changed = pyqtSignal(str)
    meta_changed         = pyqtSignal()

    def __init__(
        self,
        title:   str = "",
        x_label: str = "Time",
        x_unit:  str = "s",
        y_label: str = "Voltage",
        y_unit:  str = "mV",
        parent:  Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._title   = title
        self._x_label = x_label
        self._x_unit  = x_unit
        self._y_label = y_label
        self._y_unit  = y_unit
        self._channels: dict[str, ChannelData] = {}

    # ------------------------------------------------------------------
    # Meta properties
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
        return self._x_label, self._x_unit

    def set_x_label(self, label: str, unit: str = "") -> None:
        self._x_label, self._x_unit = label, unit
        self.meta_changed.emit()

    @property
    def y_label(self) -> tuple[str, str]:
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
        if name in self._channels:
            del self._channels[name]
            self.channels_changed.emit()

    def set_channel_visible(self, name: str, visible: bool) -> None:
        if name in self._channels and self._channels[name].visible != visible:
            self._channels[name].visible = visible
            self.channels_changed.emit()

    def clear(self) -> None:
        if self._channels:
            self._channels.clear()
            self.channels_changed.emit()

    # ------------------------------------------------------------------
    # Live data update  →  triggers channel_data_changed (fast path)
    # ------------------------------------------------------------------

    def update_channel(self, name: str, x: np.ndarray, y: np.ndarray) -> None:
        """Replace the data of an existing channel without a structural rebuild.

        Falls back to set_channel() if the channel does not exist yet.
        """
        if name not in self._channels:
            self.set_channel(name, x, y)
            return
        ch = self._channels[name]
        ch.x = x if (isinstance(x, np.ndarray) and x.dtype == np.float64) else np.asarray(x, dtype=np.float64)
        ch.y = y if (isinstance(y, np.ndarray) and y.dtype == np.float64) else np.asarray(y, dtype=np.float64)
        self.channel_data_changed.emit(name)

    # ------------------------------------------------------------------
    # Read-only access
    # ------------------------------------------------------------------

    @property
    def channels(self) -> list[ChannelData]:
        return list(self._channels.values())

    def get_channel(self, name: str) -> Optional[ChannelData]:
        return self._channels.get(name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_color(self) -> str:
        return _PALETTE[len(self._channels) % len(_PALETTE)]

    @classmethod
    def with_mock_data(cls) -> "GraphViewModel":
        vm = cls(title="Mock Signal")
        t = np.linspace(0, 2 * np.pi, 500)
        vm.set_channel("Channel 1", t, np.sin(t))
        vm.set_channel("Channel 2", t, np.sin(2 * t) * 0.5)
        return vm
