"""Application theme / colour palette."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    background: str
    surface: str
    panel: str
    primary_accent: str
    secondary_accent: str
    highlight: str
    error: str
    text_primary: str
    text_secondary: str
    plot_background: str
    plot_grid: str
    border: str
    hover: str
    pressed: str


DARK_PALETTE = ColorPalette(
    background="#1E2228",
    surface="#242933",
    panel="#2D3440",
    primary_accent="#4C8DFF",
    secondary_accent="#2DD4BF",
    highlight="#FFB84D",
    error="#F87171",
    text_primary="#E6EDF3",
    text_secondary="#9AA4B2",
    plot_background="#20252E",
    plot_grid="#3A424F",
    border="#3A424F",
    hover="#363D49",
    pressed="#424A58",
)
