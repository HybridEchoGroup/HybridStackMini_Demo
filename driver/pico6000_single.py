import ctypes
import numpy as np

from picosdk.ps6000a import ps6000a as ps
from picosdk.PicoDeviceEnums import picoEnum as enums
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc

from driver.picoscope import PicoScope
from driver.utils import StatusLog


class pico_handler(PicoScope):
    """
    High-level handler for PicoScope 6000A devices.

    This class wraps the PicoSDK block-mode acquisition workflow,
    including channel configuration, triggering, signal generation,
    data acquisition, conversion, and storage.
    """

    def __init__(self, samples=312500):
        """
        Initialize the PicoScope device and internal data buffers.

        Opens the PicoScope 6000A unit, allocates memory buffers for
        all channels, disables all channels by default, and prepares
        the device for block-mode acquisition.

        Parameters
        ----------
        samples : int, optional
            Number of samples per acquisition (default: 312500).
        """

        self.status = StatusLog("logs/my_run.log")
        self.chandle = ctypes.c_int16()
        self.enabled = 1
        self.analogue_offset = 0.0

        self.samples = samples

        self.minADC = ctypes.c_int16()
        self.maxADC = ctypes.c_int16()

        self.bufferCompleteA = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteB = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteC = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteD = (ctypes.c_int16 * self.samples)()

        self.bufferCompleteAmin = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteBmin = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteCmin = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteDmin = (ctypes.c_int16 * self.samples)()

        self.bandwidth = enums.PICO_BANDWIDTH_LIMITER["PICO_BW_FULL"]

        self.activeA = 0
        self.activeB = 0
        self.activeC = 0
        self.activeD = 0

        self.rangeA = 0
        self.rangeB = 0
        self.rangeC = 0
        self.rangeD = 0 

        self.sig_active = 0

        self.status["openunit"] = ps.ps6000aOpenUnit(ctypes.byref(self.chandle), None, enums.PICO_DEVICE_RESOLUTION["PICO_DR_10BIT"])
        assert_pico_ok(self.status["openunit"])

        self.status["setChannelA"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_A"])
        self.status["setChannelB"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_B"])
        self.status["setChannelC"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_C"])
        self.status["setChannelD"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_D"])
        enums.PICO_CHANNEL["PICO_TRIGGER_AUX"]
    
    def set_sample(self, samples):
        self.samples = samples

    def enable_channel_A(self, range):
        """
        Enable Channel A and configure its data buffers.

        Activates Channel A with DC coupling, the specified voltage range,
        and assigns memory buffers for block-mode acquisition.

        Parameters
        ----------
        range : int
            PicoScope voltage range enum value (e.g. voltage_level.V2_v.value).
        """
        self.rangeA = range
        self.status["setChA"] = ps.ps6000aSetChannelOn(self.chandle,
                                                enums.PICO_CHANNEL["PICO_CHANNEL_A"],
                                                enums.PICO_COUPLING["PICO_DC"],
                                                range,
                                                0,
                                                self.bandwidth)
        assert_pico_ok(self.status["setChA"])
        self.bufferCompleteA = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteAmin = (ctypes.c_int16 * self.samples)()
        clear = enums.PICO_ACTION["PICO_CLEAR_ALL"]
        add = enums.PICO_ACTION["PICO_ADD"]
        action = clear|add
        self.status["setDataBuffersA"] = ps.ps6000aSetDataBuffers(self.chandle,
                                                    enums.PICO_CHANNEL["PICO_CHANNEL_A"],
                                                    self.bufferCompleteA,
                                                    self.bufferCompleteAmin,
                                                    self.samples,
                                                    enums.PICO_DATA_TYPE["PICO_INT16_T"],
                                                    0,
                                                    enums.PICO_RATIO_MODE["PICO_RATIO_MODE_RAW"],
                                                    add)
        assert_pico_ok(self.status["setDataBuffersA"])
        self.activeA = 1

    def enable_channel_B(self, range):
        """
        Enable Channel B and configure its data buffers.

        Parameters
        ----------
        range : int
            PicoScope voltage range enum value.
        """
        self.rangeB = range
        self.status["setChB"] = ps.ps6000aSetChannelOn(self.chandle,
                                                enums.PICO_CHANNEL["PICO_CHANNEL_B"],
                                                enums.PICO_COUPLING["PICO_DC"],
                                                range,
                                                0,
                                                self.bandwidth)
        assert_pico_ok(self.status["setChB"])
        self.bufferCompleteB = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteBmin = (ctypes.c_int16 * self.samples)()
        clear = enums.PICO_ACTION["PICO_CLEAR_ALL"]
        add = enums.PICO_ACTION["PICO_ADD"]
        action = clear|add
        self.status["setDataBuffersB"] = ps.ps6000aSetDataBuffers(self.chandle,
                                                    enums.PICO_CHANNEL["PICO_CHANNEL_B"],
                                                    self.bufferCompleteB,
                                                    self.bufferCompleteBmin,
                                                    self.samples,
                                                    enums.PICO_DATA_TYPE["PICO_INT16_T"],
                                                    0,
                                                    enums.PICO_RATIO_MODE["PICO_RATIO_MODE_RAW"],
                                                    add)
        assert_pico_ok(self.status["setDataBuffersB"])
        self.activeB = 1

    def enable_channel_C(self, range):
        """
        Enable Channel C and configure its data buffers.

        Parameters
        ----------
        range : int
            PicoScope voltage range enum value.
        """
        self.rangeC = range
        self.status["setChC"] = ps.ps6000aSetChannelOn(self.chandle,
                                                enums.PICO_CHANNEL["PICO_CHANNEL_C"],
                                                enums.PICO_COUPLING["PICO_DC"],
                                                range,
                                                0,
                                                self.bandwidth)
        assert_pico_ok(self.status["setChC"])
        self.bufferCompleteC = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteCmin = (ctypes.c_int16 * self.samples)()
        clear = enums.PICO_ACTION["PICO_CLEAR_ALL"]
        add = enums.PICO_ACTION["PICO_ADD"]
        action = clear|add
        self.status["setDataBuffersC"] = ps.ps6000aSetDataBuffers(self.chandle,
                                                    enums.PICO_CHANNEL["PICO_CHANNEL_C"],
                                                    self.bufferCompleteC,
                                                    self.bufferCompleteCmin,
                                                    self.samples,
                                                    enums.PICO_DATA_TYPE["PICO_INT16_T"],
                                                    0,
                                                    enums.PICO_RATIO_MODE["PICO_RATIO_MODE_RAW"],
                                                    add)
        assert_pico_ok(self.status["setDataBuffersC"])
        self.activeC = 1
    
    def enable_channel_D(self, range):
        """
        Enable Channel D and configure its data buffers.

        Parameters
        ----------
        range : int
            PicoScope voltage range enum value.
        """
        self.rangeD = range
        self.status["setChD"] = ps.ps6000aSetChannelOn(self.chandle,
                                                enums.PICO_CHANNEL["PICO_CHANNEL_D"],
                                                enums.PICO_COUPLING["PICO_DC"],
                                                range,
                                                0,
                                                self.bandwidth)
        assert_pico_ok(self.status["setChD"])
        self.bufferCompleteD = (ctypes.c_int16 * self.samples)()
        self.bufferCompleteDmin = (ctypes.c_int16 * self.samples)()
        clear = enums.PICO_ACTION["PICO_CLEAR_ALL"]
        add = enums.PICO_ACTION["PICO_ADD"]
        action = clear|add
        self.status["setDataBuffersD"] = ps.ps6000aSetDataBuffers(self.chandle,
                                                    enums.PICO_CHANNEL["PICO_CHANNEL_D"],
                                                    self.bufferCompleteD,
                                                    self.bufferCompleteDmin,
                                                    self.samples,
                                                    enums.PICO_DATA_TYPE["PICO_INT16_T"],
                                                    0,
                                                    enums.PICO_RATIO_MODE["PICO_RATIO_MODE_RAW"],
                                                    add)
        assert_pico_ok(self.status["setDataBuffersD"])
        self.activeD = 1

    def disable_channel_A(self):
        self.status["setChA"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_A"])
    def disable_channel_B(self):
        self.status["setChB"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_B"])
    def disable_channel_C(self):
        self.status["setChC"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_C"])
    def disable_channel_D(self):
        self.status["setChD"] = ps.ps6000aSetChannelOff(self.chandle, enums.PICO_CHANNEL["PICO_CHANNEL_D"])

    def setup_trigger(self, range, threshold, channel): 
        """
        Configure a simple rising-edge trigger.

        Converts the trigger threshold from millivolts to ADC counts
        and applies a simple trigger on the specified channel.

        Parameters
        ----------
        range : int
            Voltage range enum value used for ADC conversion.
        threshold : float or int
            Trigger threshold in millivolts.
        channel : int
            Trigger source channel enum value
            (e.g. channels.Channel_A.value).
        """
        self.status["getAdcLimits"] = ps.ps6000aGetAdcLimits(self.chandle, 1, ctypes.byref(self.minADC), ctypes.byref(self.maxADC))
        assert_pico_ok(self.status["getAdcLimits"])
        adcTriggerLevel = mV2adc(threshold, range, self.maxADC)

        self.status["setTrigger"] = ps.ps6000aSetSimpleTrigger(self.chandle,
                                                        1,
                                                        channel,
                                                        adcTriggerLevel,
                                                        enums.PICO_THRESHOLD_DIRECTION["PICO_RISING"],
                                                        0,
                                                        0)
        assert_pico_ok(self.status["setTrigger"])

    def setup_ext_trigger(self): 
        """
        Configures the Aug trigger of the Picoscope (needs a 2.5V trigger)
        """
        self.status["getAdcLimits"] = ps.ps6000aGetAdcLimits(self.chandle, 1, ctypes.byref(self.minADC), ctypes.byref(self.maxADC))
        assert_pico_ok(self.status["getAdcLimits"])
        adcTriggerLevel = 0

        self.status["setTrigger"] = ps.ps6000aSetSimpleTrigger(self.chandle,
                                                        1,
                                                        1001,
                                                        adcTriggerLevel,
                                                        enums.PICO_THRESHOLD_DIRECTION["PICO_RISING"],
                                                        0,
                                                        0)
        assert_pico_ok(self.status["setTrigger"])

    def autotrigger(self, channel, ch_range):
        self.status["getAdcLimits"] = ps.ps6000aGetAdcLimits(self.chandle, 1, ctypes.byref(self.minADC), ctypes.byref(self.maxADC))
        assert_pico_ok(self.status["getAdcLimits"])
        adcTriggerLevel = mV2adc(100, ch_range, self.maxADC)

        self.status["setTrigger"] = ps.ps6000aSetSimpleTrigger(self.chandle,
                                                        1,
                                                        channel,
                                                        adcTriggerLevel,
                                                        enums.PICO_THRESHOLD_DIRECTION["PICO_RISING"],
                                                        0,
                                                        10000)
        assert_pico_ok(self.status["setTrigger"])

    
    def generate_signal(self, freq = 1000000):
        """
        Enable and configure the internal signal generator.

        Generates a continuous sine wave with fixed amplitude and
        duty cycle at the specified frequency.

        Parameters
        ----------
        freq : int, optional
            Output frequency in Hz (default: 1 MHz).
        """
        wavetype = enums.PICO_WAVE_TYPE["PICO_SINE"]
        bufferlength = 1000
        buffer = (ctypes.c_int16 * bufferlength)()
        self.status["sigGenWaveform"] = ps.ps6000aSigGenWaveform(self.chandle, wavetype, ctypes.byref(buffer), bufferlength)
        assert_pico_ok(self.status["sigGenWaveform"])
        peakToPeakVolts = 2
        offsetVolts = 0
        self.status["sigGenRange"] = ps.ps6000aSigGenRange(self.chandle, peakToPeakVolts, offsetVolts)
        assert_pico_ok(self.status["sigGenRange"])
        dutyCyclePercent = 50
        self.status["sigGenDutyCycle"] = ps.ps6000aSigGenWaveformDutyCycle(self.chandle, dutyCyclePercent)
        assert_pico_ok(self.status["sigGenDutyCycle"])
        frequencyHz = freq
        self.status["sigGenFreq"] = ps.ps6000aSigGenFrequency(self.chandle, frequencyHz)
        assert_pico_ok(self.status["sigGenFreq"])
        sigGenEnabled = 1
        sweepEnabled = 0
        triggerEnabled = 0
        automaticClockOptimisationEnabled = 0
        overrideAutomaticClockAndPrescale = 0
        frequency = ctypes.c_int16(frequencyHz)
        self.status["sigGenApply"] = ps.ps6000aSigGenApply(self.chandle, 
                                                    sigGenEnabled, 
                                                    sweepEnabled, 
                                                    triggerEnabled, 
                                                    automaticClockOptimisationEnabled, 
                                                    overrideAutomaticClockAndPrescale, 
                                                    ctypes.byref(frequency), 
                                                    None,
                                                    None,
                                                    None
                                                    )
        assert_pico_ok(self.status["sigGenApply"])
        if self.sig_active:
            self.status["sigGenRestart"] = ps.ps6000aSigGenRestart(self.chandle)
            assert_pico_ok(self.status["sigGenRestart"])
    
    def stop_sig_gen(self):
        """
        Pause the internal signal generator output.

        Disables the signal generator without resetting its configuration.
        """
        self.sig_active = 1
        self.status["sigGenPause"] = ps.ps6000aSigGenPause(self.chandle)
        assert_pico_ok(self.status["sigGenPause"])


    def start_data_collect(self, timebase=5):
        """
        Start a block-mode acquisition and wait until completion.

        Initiates a block capture, polls the device until data is ready,
        and transfers the acquired samples into the configured buffers.

        Parameters
        ----------
        timebase : int, optional
            PicoScope timebase index (default: 5).
        """
        c_timeIndisposedMs = ctypes.c_double(0)
        c_timebase = ctypes.c_uint32(timebase)

        ps.ps6000aRunBlock(self.chandle, 0, self.samples, c_timebase, ctypes.byref(c_timeIndisposedMs), 0, None, None)
        self.time = c_timeIndisposedMs

        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            ps.ps6000aIsReady(self.chandle, ctypes.byref(ready))

        overflow = ctypes.c_int16(0)
        nSamples = self.samples
        noOfSamples = ctypes.c_uint64(nSamples)
        status_getValues = ps.ps6000aGetValues(self.chandle, 0, ctypes.byref(noOfSamples), 1, enums.PICO_RATIO_MODE["PICO_RATIO_MODE_RAW"], 0, ctypes.byref(overflow))
        assert_pico_ok(status_getValues)


    def return_data(self):
        """
        Return acquired data as a NumPy array.

        Returns a (samples x 4) array containing channel data in millivolts.
        Inactive channels are filled with NaN.

        Parameters
        ----------
        range : int
            Voltage range enum value used for ADC conversion.

        Returns
        -------
        numpy.ndarray
            Array of shape (samples, 4) containing channel data in mV.
        """
        data = np.full((self.samples, 4), np.nan, dtype=np.float32)

        if self.activeA:
            data[:, 0] = adc2mV(self.bufferCompleteA, self.rangeA, self.maxADC)
        if self.activeB:
            data[:, 1] = adc2mV(self.bufferCompleteB, self.rangeB, self.maxADC)
        if self.activeC:
            data[:, 2] = adc2mV(self.bufferCompleteC, self.rangeC, self.maxADC)
        if self.activeD:
            data[:, 3] = adc2mV(self.bufferCompleteD, self.rangeD, self.maxADC)

        return data
    
    def pause_pico(self):
        """
        Pauses the picoscope recording. Allows to restart recording
        without initializing the picoscope from the ground.
        """
        self.status["pause_unit"] = ps.ps6000aStop(self.chandle)
        assert_pico_ok(self.status["pause_unit"])
    
    def stop_pico(self):
        """
        Close the PicoScope device and release all resources.

        Must be called before program termination to properly
        close the device connection.
        """
        self.status["closeunit"] = ps.ps6000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["closeunit"])
