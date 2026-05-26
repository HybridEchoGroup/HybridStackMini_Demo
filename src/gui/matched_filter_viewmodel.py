"""MatchedFilterViewModel — applies a matched filter to incoming data blocks.

Usage
-----
    mf_vm = MatchedFilterViewModel()
    mf_vm.load_reference("path/to/reference.bin")   # int16 binary file

    # Wire to the main acquisition VM:
    main_vm.live_data_ready.connect(lambda: mf_vm.process(main_vm.dataB))

    # The view subscribes to result_ready:
    mf_vm.result_ready.connect(lambda x, y: curve.setData(x, y))
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from config import SOUND_SPEED_MPS, CROSSTALK_SKIP_SAMPLES, DEFAULT_REFERENCE_FREQ_HZ
from gui.graph_viewmodel import N_SAMPLES, SAMPLE_RATE, _TIME_AXIS

import logging
_log = logging.getLogger(__name__)


class _FilterWorker(QRunnable):
    """Runs one matched-filter pass off the GUI thread."""

    def __init__(self, data: np.ndarray, ref_fft: np.ndarray, dist_axis: np.ndarray, callback) -> None:
        super().__init__()
        self._data      = data
        self._ref_fft   = ref_fft
        self._dist_axis = dist_axis
        self._cb        = callback

    def run(self) -> None:
        data = self._data.copy()
        data[:CROSSTALK_SKIP_SAMPLES] = 0.0
        rms = np.sqrt(np.mean(data ** 2))
        if rms > 0:
            data /= rms
        sig_fft = np.fft.rfft(data, n=N_SAMPLES)
        output  = np.abs(np.fft.irfft(sig_fft * self._ref_fft, n=N_SAMPLES))
        peak = output.max()
        if peak > 0:
            output = output / peak
        output = 20.0 * np.log10(np.maximum(output, 1e-6))  # floor at -120 dB
        self._cb(self._dist_axis, output)


class MatchedFilterViewModel(QObject):
    """Applies an FFT-based matched filter and emits the result.

    Signals
    -------
    result_ready(x, y)
        Emitted after each successful filter pass with the time axis (x)
        and the filter output magnitude (y).
    reference_changed
        Emitted when a new reference signal is loaded.
    """

    result_ready      = pyqtSignal(object, object)  # x array, y array
    reference_changed = pyqtSignal()
    ambiguity_ready   = pyqtSignal(object, object)  # lag axis (m), autocorr dB

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._reference: np.ndarray | None = None
        self._ref_fft:   np.ndarray | None = None   # cached conjugate FFT of reference
        self._acf_db:    np.ndarray | None = None   # cached autocorrelation magnitude (dB)
        self._sound_speed = SOUND_SPEED_MPS
        self._busy        = False
        self._pool        = QThreadPool.globalInstance()
        self.load_default_reference()

    @staticmethod
    def make_sine_reference(frequency: float = DEFAULT_REFERENCE_FREQ_HZ) -> np.ndarray:
        """Return a sine wave at *frequency* Hz sampled at SAMPLE_RATE over N_SAMPLES."""
        return np.sin(2 * np.pi * frequency * _TIME_AXIS)

    def load_default_reference(self) -> None:
        """Set the reference to a 7 MHz sine wave."""
        self.set_reference(self.make_sine_reference(DEFAULT_REFERENCE_FREQ_HZ))

    # ------------------------------------------------------------------
    # Reference management
    # ------------------------------------------------------------------

    def load_reference(self, path: str) -> None:
        """Load reference signal from a flat int16 binary file."""
        ref = np.fromfile(path, dtype=np.int16).astype(float)
        self.set_reference(ref)

    def set_reference(self, array: np.ndarray) -> None:
        """Set the reference signal directly from an array."""
        self._reference = np.asarray(array, dtype=float)
        rms = np.sqrt(np.mean(self._reference ** 2))
        if rms > 0:
            self._reference = self._reference / rms
        # Pre-compute and cache the conjugate FFT padded to N_SAMPLES
        ref_fft = np.fft.rfft(self._reference, n=N_SAMPLES)
        self._ref_fft = np.conj(ref_fft)

        # Cache autocorrelation magnitude — axis recomputed separately so
        # set_sound_speed() can re-emit without re-processing the reference.
        acf = np.abs(np.fft.irfft(ref_fft * np.conj(ref_fft), n=N_SAMPLES))
        acf = np.fft.fftshift(acf)
        if acf.max() > 0:
            acf /= acf.max()
        self._acf_db = 20.0 * np.log10(np.maximum(acf, 1e-6))
        _log.info("Reference set or updated")
        self._emit_ambiguity()

        self.reference_changed.emit()

    @property
    def reference(self) -> np.ndarray | None:
        return self._reference

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def set_sound_speed(self, mps: float) -> None:
        """Update the speed of sound used for the depth axis."""
        self._sound_speed = mps
        _log.info("Speed of sound changed")
        self._emit_ambiguity()

    def _emit_ambiguity(self) -> None:
        if self._acf_db is None:
            return
        lag_axis = (np.arange(N_SAMPLES) - N_SAMPLES // 2) / SAMPLE_RATE * self._sound_speed / 2.0
        self.ambiguity_ready.emit(lag_axis, self._acf_db)

    def process(self, data: np.ndarray) -> None:
        """Submit a matched-filter job to the thread pool.

        Drops the frame if a previous job is still running so that the
        GUI never accumulates a backlog during fast acquisitions.
        """
        if self._ref_fft is None or data is None or len(data) == 0:
            return
        if self._busy:
            return

        self._busy = True
        ref_fft_snapshot = self._ref_fft
        dist_snapshot    = _TIME_AXIS * self._sound_speed / 2.0
        worker = _FilterWorker(data, ref_fft_snapshot, dist_snapshot, self._on_result)
        self._pool.start(worker)

    def update_from_config(self) -> None:
        """Reload signal-processing constants from config without changing the reference."""
        global CROSSTALK_SKIP_SAMPLES
        import config as config
        CROSSTALK_SKIP_SAMPLES = config.CROSSTALK_SKIP_SAMPLES
        self._sound_speed = config.SOUND_SPEED_MPS
        _log.info("Config loaded")
        self._emit_ambiguity()

    def _on_result(self, x: np.ndarray, y: np.ndarray) -> None:
        self._busy = False
        self.result_ready.emit(x, y)
