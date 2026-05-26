"""AcquisitionViewModel — PicoScope connection, acquisition threads, and raw data buffers."""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, pyqtSignal

import config as _config
import logging

from driver.picoscope import PicoScope, create_backend

import logging
_log = logging.getLogger(__name__)


class PicoscopeModel(Enum):
    """Supported PicoScope hardware models."""
    PS6424E = "6000"
    PS3406B = "3000"


class ConnectionStatus(Enum):
    DISCONNECTED = auto()
    CONNECTING   = auto()
    CONNECTED    = auto()
    ERROR        = auto()


class AcquisitionStatus(Enum):
    IDLE    = auto()
    RUNNING = auto()
    PAUSED  = auto()


class _WorkerSignals(QObject):
    """Signals for QRunnable workers (QRunnable itself cannot have signals)."""
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)


class _PicoConnectRunnable(QRunnable):
    def __init__(self, model: str) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self.signals = _WorkerSignals()
        self._model = model

    def run(self) -> None:
        try:
            handler_cls = create_backend(self._model)
            self.signals.finished.emit(handler_cls())
        except Exception as e:
            _log.error("PicoScope connection failed: %s", e)
            self.signals.error.emit(str(e))


class PicoDataCollector(QObject):
    """Fires the PicoScope acquisition on a timer and emits raw data."""
    collect     = pyqtSignal(object)
    stop_signal = pyqtSignal()

    def __init__(self, handle: PicoScope, timebase: int) -> None:
        super().__init__()
        self._pico_handle = handle
        self._timebase = timebase
        self._timer: QTimer | None = None

    def start(self) -> None:
        self._timer = QTimer()
        self._timer.setInterval(_config.ACQUISITION_INTERVAL_MS)
        self._timer.timeout.connect(self._collect)
        self.stop_signal.connect(self._stop)
        self._timer.start()

    def _collect(self) -> None:
        self._pico_handle.start_data_collect(self._timebase)
        self.collect.emit(self._pico_handle.return_data())

    def _stop(self) -> None:
        if self._timer:
            self._timer.stop()


class _DataProcessor(QObject):
    """Converts raw scope data to float64 arrays off the GUI thread."""
    data_ready = pyqtSignal(object, object)  # dataA, dataB (float64 ndarray)

    def process(self, data) -> None:
        if data is None or len(data) == 0:
            return
        self.data_ready.emit(
            data[:, 0].astype(np.float64, copy=False),
            data[:, 1].astype(np.float64, copy=False),
        )


class AcquisitionViewModel(QObject):
    """Owns the PicoScope connection, acquisition threads, and raw data buffers.

    Signals
    -------
    picoscope_status_changed(ConnectionStatus)
    acquisition_status_changed(AcquisitionStatus)
    model_changed(PicoscopeModel | None)
    live_data_ready   — emitted each time a new frame is ready in dataA / dataB
    """

    picoscope_status_changed   = pyqtSignal(object)
    acquisition_status_changed = pyqtSignal(object)
    model_changed              = pyqtSignal(object)
    live_data_ready            = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.picoscope_handle: PicoScope | None       = None
        self._picoscope_status                        = ConnectionStatus.DISCONNECTED
        self._acquisition_status                      = AcquisitionStatus.IDLE
        self._selected_model: PicoscopeModel | None   = None
        self._active: set[str]                        = set()
        self._pool                                    = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self.dataA = np.array([])
        self.dataB = np.array([])

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
        task = _PicoConnectRunnable(model.value if model else "")
        task.signals.finished.connect(self._on_pico_connected)
        task.signals.finished.connect(lambda _: self._release("pico_connect"))
        task.signals.error.connect(self._on_pico_failed)
        task.signals.error.connect(lambda _: self._release("pico_connect"))
        if not self._submit("pico_connect", task):
            return
        self._picoscope_status = ConnectionStatus.CONNECTING
        self.picoscope_status_changed.emit(self._picoscope_status)

    def disconnect(self) -> None:
        self._disconnect_picoscope()

    def start(self) -> None:
        self.picoscope_handle.enable_channel_A(_config.CH_A_VOLTAGE_RANGE)
        self.picoscope_handle.enable_channel_B(_config.CH_B_VOLTAGE_RANGE)
        self.picoscope_handle.setup_trigger(
            _config.TRIGGER_VOLTAGE_RANGE,
            _config.TRIGGER_THRESHOLD_MV,
            _config.TRIGGER_CHANNEL,
        )

        model_str = self._selected_model.value if self._selected_model else ""
        tb = _config.timebase_for_model(model_str)
        _log.info("Using timebase index %d for model %s", tb, model_str)

        self._sr_thread = QThread()
        self._sr_worker = PicoDataCollector(self.picoscope_handle, tb)
        self._sr_worker.moveToThread(self._sr_thread)
        self._sr_thread.started.connect(self._sr_worker.start)
        self._sr_thread.finished.connect(self._sr_worker.deleteLater)
        self._sr_thread.finished.connect(self._sr_thread.deleteLater)

        self._proc_thread = QThread()
        self._processor = _DataProcessor()
        self._processor.moveToThread(self._proc_thread)
        self._sr_worker.collect.connect(self._processor.process)
        self._processor.data_ready.connect(self._on_data_processed)
        self._proc_thread.finished.connect(self._processor.deleteLater)
        self._proc_thread.finished.connect(self._proc_thread.deleteLater)

        self._proc_thread.start()
        self._sr_thread.start()

        self._acquisition_status = AcquisitionStatus.RUNNING
        _log.info("Picoscope acquisition started")
        self.acquisition_status_changed.emit(self._acquisition_status)

    def pause(self) -> None:
        if hasattr(self, '_sr_worker'):
            self._sr_worker.stop_signal.emit()
        if hasattr(self, '_sr_thread'):
            self._sr_thread.quit()
        if hasattr(self, '_proc_thread'):
            self._proc_thread.quit()
        self._acquisition_status = AcquisitionStatus.IDLE
        self.acquisition_status_changed.emit(self._acquisition_status)
        if self.picoscope_handle:
            self.picoscope_handle.pause_pico()
            _log.info("Picoscope acquisition paused")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _disconnect_picoscope(self) -> None:
        if self.picoscope_handle is not None:
            self.picoscope_handle.stop_pico()
        self.picoscope_handle = None
        self._picoscope_status = ConnectionStatus.DISCONNECTED
        _log.info("Disconnected Picoscope")
        self.picoscope_status_changed.emit(self._picoscope_status)

    def _on_data_processed(self, dataA: np.ndarray, dataB: np.ndarray) -> None:
        self.dataA = dataA
        self.dataB = dataB
        self.live_data_ready.emit()

    def _on_pico_connected(self, handle: PicoScope) -> None:
        self.picoscope_handle = handle
        self._picoscope_status = ConnectionStatus.CONNECTED
        _log.info("Connected Picoscope")
        self.picoscope_status_changed.emit(self._picoscope_status)

    def _on_pico_failed(self, _msg: str) -> None:
        self._picoscope_status = ConnectionStatus.ERROR
        _log.warning("Picoscope not connected")
        self.picoscope_status_changed.emit(self._picoscope_status)

    def _submit(self, key: str, runnable: QRunnable) -> bool:
        if key in self._active:
            return False
        self._active.add(key)
        self._pool.start(runnable)
        return True

    def _release(self, key: str) -> None:
        self._active.discard(key)
