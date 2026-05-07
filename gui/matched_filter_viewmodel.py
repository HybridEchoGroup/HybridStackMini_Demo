"""MatchedFilterViewModel — applies a matched filter to incoming data blocks.

Usage
-----
    mf_vm = MatchedFilterViewModel()
    mf_vm.load_reference("path/to/reference.bin")   # float32 binary file

    # Wire to the main acquisition VM:
    main_vm.live_data_ready.connect(lambda: mf_vm.process(main_vm.dataB))

    # The view subscribes to result_ready:
    mf_vm.result_ready.connect(lambda x, y: curve.setData(x, y))
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from gui.graph_viewmodel import N_SAMPLES, SAMPLE_RATE, _TIME_AXIS


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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._reference: np.ndarray | None = None
        self._ref_fft:   np.ndarray | None = None   # cached FFT of reference

    # ------------------------------------------------------------------
    # Reference management
    # ------------------------------------------------------------------

    def load_reference(self, path: str) -> None:
        """Load reference signal from a flat float32 binary file."""
        ref = np.fromfile(path, dtype=np.float32).astype(float)
        self.set_reference(ref)

    def set_reference(self, array: np.ndarray) -> None:
        """Set the reference signal directly from an array."""
        self._reference = np.asarray(array, dtype=float)
        # Pre-compute and cache the conjugate FFT padded to N_SAMPLES
        self._ref_fft = np.conj(np.fft.rfft(self._reference, n=N_SAMPLES))
        self.reference_changed.emit()

    @property
    def reference(self) -> np.ndarray | None:
        return self._reference

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(self, data: np.ndarray) -> None:
        """Apply the matched filter to *data* and emit result_ready.

        Silently skips if data is empty or no reference has been loaded.
        """
        if self._ref_fft is None or data is None or len(data) == 0:
            return

        sig_fft = np.fft.rfft(data, n=N_SAMPLES)
        output  = np.abs(np.fft.irfft(sig_fft * self._ref_fft, n=N_SAMPLES))
        self.result_ready.emit(_TIME_AXIS, output)
