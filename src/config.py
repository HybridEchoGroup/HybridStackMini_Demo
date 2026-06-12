"""Application configuration — loaded from config.toml at project root.

Falls back to hardcoded defaults if the file is missing so the app still
starts without a config file present.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from driver.utils import timebase, timebase_3000

_CONFIG_PATH = Path(__file__).parent / "config.toml"
_log = logging.getLogger(__name__)


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
# Timebase rate maps and selection
# ---------------------------------------------------------------------------

_RATE_MAP_6000: dict[timebase, float] = {
    timebase.Freq_625MHz:      625e6,
    timebase.Freq_312_5MHz:    312.5e6,
    timebase.Freq_156_25MHz:   156.25e6,
    timebase.Freq_78_125MHz:   78.125e6,
    timebase.Freq_39_0625MHz:  39.0625e6,
}

_RATE_MAP_3000: dict[timebase_3000, float] = {
    timebase_3000.Freq_250MHz:   250e6,
    timebase_3000.Freq_125MHz:   125e6,
    timebase_3000.Freq_62_5MHz:  62.5e6,
    timebase_3000.Freq_41_66MHz: 125e6 / 3,
    timebase_3000.Freq_31_25MHz: 31.25e6,
    timebase_3000.Freq_25MHz:    25e6,
}


def _best_timebase(target_hz: float, model: str) -> tuple:
    """Return (timebase_member, actual_rate_hz) closest to target_hz."""
    rate_map = _RATE_MAP_3000 if ("PS3" in model or model == "3000") else _RATE_MAP_6000
    return min(rate_map.items(), key=lambda kv: abs(kv[1] - target_hz))


# ---------------------------------------------------------------------------
# PicoScope
# ---------------------------------------------------------------------------

PICOSCOPE_MODEL          = _get("picoscope.model",                   "PS3406B")
N_SAMPLES                = _get("picoscope.samples",                 312_500)
ACQUISITION_INTERVAL_MS  = _get("picoscope.acquisition_interval_ms", 200)

CH_A_VOLTAGE_RANGE       = _get("picoscope.channel_a.voltage_range", 9)
CH_B_VOLTAGE_RANGE       = _get("picoscope.channel_b.voltage_range", 1)

TRIGGER_CHANNEL          = _get("picoscope.trigger.channel",          0)
TRIGGER_THRESHOLD_MV     = _get("picoscope.trigger.threshold_mv",     2600)
TRIGGER_VOLTAGE_RANGE    = _get("picoscope.trigger.voltage_range",    9)

_target_rate = _get("picoscope.target_sample_rate_hz", 156.25e6)
_selected_tb, _selected_rate = _best_timebase(_target_rate, PICOSCOPE_MODEL)
TIMEBASE: int = int(_selected_tb)
SAMPLE_RATE: float = _selected_rate

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


def timebase_for_model(model_str: str) -> int:
    """Return the best-fit timebase index for *model_str* using the current target rate."""
    tb, _ = _best_timebase(_target_rate, model_str)
    return int(tb)


def log_config() -> None:
    """Log the active timebase selection as INFO. Call once after log.setup()."""
    _log.info(
        "Selected timebase %s (index %d, %.6g MHz) for target %.6g MHz [model: %s]",
        _selected_tb.name, int(_selected_tb), _selected_rate / 1e6,
        _target_rate / 1e6, PICOSCOPE_MODEL,
    )


def reload(path: str | None = None) -> None:
    """Re-read a TOML config file and update all module-level constants in place.

    If *path* is given it becomes the new config path for subsequent reloads.
    Calling with no argument re-reads the current config file.
    N_SAMPLES / SAMPLE_RATE / TIMEBASE are updated but only take effect on the
    next application restart (they are baked into pre-computed arrays at startup).
    All other constants take effect immediately.
    """
    global _cfg, _CONFIG_PATH, _target_rate, _selected_tb, _selected_rate
    if path is not None:
        _CONFIG_PATH = Path(path)
    _cfg = _load()
    g = globals()
    g["PICOSCOPE_MODEL"]           = _get("picoscope.model",                    "PS3406B")
    g["N_SAMPLES"]                 = _get("picoscope.samples",                  312_500)
    g["ACQUISITION_INTERVAL_MS"]   = _get("picoscope.acquisition_interval_ms",  200)
    g["CH_A_VOLTAGE_RANGE"]        = _get("picoscope.channel_a.voltage_range",  9)
    g["CH_B_VOLTAGE_RANGE"]        = _get("picoscope.channel_b.voltage_range",  1)
    g["TRIGGER_CHANNEL"]           = _get("picoscope.trigger.channel",          0)
    g["TRIGGER_THRESHOLD_MV"]      = _get("picoscope.trigger.threshold_mv",     2600)
    g["TRIGGER_VOLTAGE_RANGE"]     = _get("picoscope.trigger.voltage_range",    9)

    _target_rate  = _get("picoscope.target_sample_rate_hz", 156.25e6)
    tb, rate      = _best_timebase(_target_rate, g["PICOSCOPE_MODEL"])
    _selected_tb  = tb
    _selected_rate = rate
    g["TIMEBASE"]    = int(tb)
    g["SAMPLE_RATE"] = rate

    g["SOUND_SPEED_MPS"]           = _get("signal_processing.sound_speed_mps",            1480.0)
    g["CROSSTALK_SKIP_SAMPLES"]    = _get("signal_processing.crosstalk_skip_samples",      1000)
    g["DEFAULT_REFERENCE_FREQ_HZ"] = _get("signal_processing.default_reference_freq_hz",  7_000_000)
    g["LOOPBACK_EXTRA_SAMPLES"]    = _get("signal_processing.loopback_extra_samples",      500)
    g["MF_MAX_DEPTH_M"]            = _get("display.mf_max_depth_m",      0.1)
    g["CH_A_DISPLAY_RANGE_MV"]     = _get("display.channel_a_range_mv",  10_000.0)
    g["CH_B_DISPLAY_RANGE_MV"]     = _get("display.channel_b_range_mv",  10.0)

    log_config()
