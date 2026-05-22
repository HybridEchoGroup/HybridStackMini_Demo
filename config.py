"""Application configuration — loaded from config.toml at project root.

Falls back to hardcoded defaults if the file is missing so the app still
starts without a config file present.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.toml"

def _load() -> dict:
    try:
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}

_cfg = _load()

def _get(key_path: str, default):
    node = _cfg
    for key in key_path.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


# ---------------------------------------------------------------------------
# PicoScope
# ---------------------------------------------------------------------------

PICOSCOPE_MODEL          = _get("picoscope.model",                   "PS3406B")
N_SAMPLES                = _get("picoscope.samples",                 312_500)
TIMEBASE                 = _get("picoscope.timebase",                5)
ACQUISITION_INTERVAL_MS  = _get("picoscope.acquisition_interval_ms", 300)

CH_A_VOLTAGE_RANGE       = _get("picoscope.channel_a.voltage_range", 9)
CH_B_VOLTAGE_RANGE       = _get("picoscope.channel_b.voltage_range", 1)

TRIGGER_CHANNEL          = _get("picoscope.trigger.channel",          0)
TRIGGER_THRESHOLD_MV     = _get("picoscope.trigger.threshold_mv",     2600)
TRIGGER_VOLTAGE_RANGE    = _get("picoscope.trigger.voltage_range",    9)

# Sample rate derived from timebase (6000-series values)
_TIMEBASE_TO_RATE: dict[int, float] = {
    3: 625e6,
    4: 312.5e6,
    5: 156.25e6,
    6: 78.125e6,
    7: 39.0625e6,
}
SAMPLE_RATE: float = _TIMEBASE_TO_RATE.get(TIMEBASE, 156.25e6)

# ---------------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------------

SOUND_SPEED_MPS           = _get("signal_processing.sound_speed_mps",           1480.0)
CROSSTALK_SKIP_SAMPLES    = _get("signal_processing.crosstalk_skip_samples",     1000)
DEFAULT_REFERENCE_FREQ_HZ = _get("signal_processing.default_reference_freq_hz", 7_000_000)
LOOPBACK_EXTRA_SAMPLES    = _get("signal_processing.loopback_extra_samples",     500)

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

MF_MAX_DEPTH_M        = _get("display.mf_max_depth_m",     0.1)
CH_A_DISPLAY_RANGE_MV = _get("display.channel_a_range_mv", 10_000.0)
CH_B_DISPLAY_RANGE_MV = _get("display.channel_b_range_mv", 10.0)


def reload(path: str | None = None) -> None:
    """Re-read a TOML config file and update all module-level constants in place.

    If *path* is given it becomes the new config path for subsequent reloads.
    Calling with no argument re-reads the current config file.
    N_SAMPLES / SAMPLE_RATE / TIMEBASE are updated but only take effect on the
    next application restart (they are baked into pre-computed arrays at startup).
    All other constants take effect immediately.
    """
    global _cfg, _CONFIG_PATH
    if path is not None:
        _CONFIG_PATH = Path(path)
    _cfg = _load()
    g = globals()
    g["PICOSCOPE_MODEL"]           = _get("picoscope.model",                    "PS3406B")
    g["N_SAMPLES"]                 = _get("picoscope.samples",                  312_500)
    g["TIMEBASE"]                  = _get("picoscope.timebase",                 5)
    g["ACQUISITION_INTERVAL_MS"]   = _get("picoscope.acquisition_interval_ms",  300)
    g["CH_A_VOLTAGE_RANGE"]        = _get("picoscope.channel_a.voltage_range",  9)
    g["CH_B_VOLTAGE_RANGE"]        = _get("picoscope.channel_b.voltage_range",  1)
    g["TRIGGER_CHANNEL"]           = _get("picoscope.trigger.channel",          0)
    g["TRIGGER_THRESHOLD_MV"]      = _get("picoscope.trigger.threshold_mv",     2600)
    g["TRIGGER_VOLTAGE_RANGE"]     = _get("picoscope.trigger.voltage_range",    9)
    g["SAMPLE_RATE"]               = _TIMEBASE_TO_RATE.get(g["TIMEBASE"], 156.25e6)
    g["SOUND_SPEED_MPS"]           = _get("signal_processing.sound_speed_mps",            1480.0)
    g["CROSSTALK_SKIP_SAMPLES"]    = _get("signal_processing.crosstalk_skip_samples",      1000)
    g["DEFAULT_REFERENCE_FREQ_HZ"] = _get("signal_processing.default_reference_freq_hz",  7_000_000)
    g["LOOPBACK_EXTRA_SAMPLES"]    = _get("signal_processing.loopback_extra_samples",      500)
    g["MF_MAX_DEPTH_M"]            = _get("display.mf_max_depth_m",      0.1)
    g["CH_A_DISPLAY_RANGE_MV"]     = _get("display.channel_a_range_mv",  10_000.0)
    g["CH_B_DISPLAY_RANGE_MV"]     = _get("display.channel_b_range_mv",  10.0)
