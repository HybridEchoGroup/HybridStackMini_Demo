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

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal


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


@dataclass
class ChannelData:
    name: str
    x: np.ndarray
    y: np.ndarray
    color: str
    width: int = 2
    visible: bool = True


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

    def __init__(
        self,
        title: str = "",
        x_label: str = "Time",
        x_unit: str = "s",
        y_label: str = "Amplitude",
        y_unit: str = "V",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)

        self._title = title
        self._x_label = x_label
        self._x_unit = x_unit
        self._y_label = y_label
        self._y_unit = y_unit
        self._channels: dict[str, ChannelData] = {}

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
