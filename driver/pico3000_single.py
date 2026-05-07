import ctypes
import numpy as np

from picosdk.ps3000a import ps3000a as ps
from picosdk.PicoDeviceEnums import picoEnum as enums
from picosdk.functions import adc2mV, mV2adc, assert_pico_ok

from driver.picoscope import PicoScope
from driver.utils import StatusLog

ENABLED = 1
DISABLED = 0

class pico_handler(PicoScope):
    def __init__(self, samples=312500):

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

        self.activeA = 0
        self.activeB = 0
        self.activeC = 0
        self.activeD = 0

        self.rangeA = 0
        self.rangeB = 0
        self.rangeC = 0
        self.rangeD = 0

        self.status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(self.chandle), None)
        try:
            assert_pico_ok(self.status["openunit"])
        except:
            powerstate = self.status["openunit"]

            if powerstate == 282:
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 282)
            elif powerstate == 286:
                self.status["ChangePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, 286)
            else:
                raise

            assert_pico_ok(self.status["ChangePowerSource"])
        
        #Disable all channels
        self.status["setChA"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
        self.status["setChC"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_C'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
        self.status["setChD"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)


    def enable_channel_A(self, range):
        self.rangeA = range
        self.status["setChA"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                self.enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                range,
                                                self.analogue_offset)
        assert_pico_ok(self.status["setChA"])
        self.status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                     self.bufferCompleteA,
                                                     self.bufferCompleteAmin,
                                                     self.samples,
                                                     0,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersA"])
        self.activeA = 1

    def enable_channel_B(self, range):
        self.rangeB = range
        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                self.enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                range,
                                                self.analogue_offset)
        assert_pico_ok(self.status["setChB"])
        self.status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                     self.bufferCompleteB,
                                                     self.bufferCompleteBmin,
                                                     self.samples,
                                                     0,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersB"])
        self.activeB = 1

    def enable_channel_C(self, range):
        self.rangeC = range
        self.status["setChC"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_C'],
                                                self.enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                range,
                                                self.analogue_offset)
        assert_pico_ok(self.status["setChC"])
        self.status["setDataBuffersC"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_C'],
                                                     self.bufferCompleteC,
                                                     self.bufferCompleteCmin,
                                                     self.samples,
                                                     0,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersC"])
        self.activeC = 1

    def enable_channel_D(self, range):
        self.rangeD = range
        self.status["setChD"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'],
                                                self.enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                range,
                                                self.analogue_offset)
        assert_pico_ok(self.status["setChD"])
        self.status["setDataBuffersD"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'],
                                                     self.bufferCompleteD,
                                                     self.bufferCompleteDmin,
                                                     self.samples,
                                                     0,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersD"])
        self.activeD = 1

    def disable_channel_A(self):
        self.status["setChA"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
    def disable_channel_B(self):
        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
    def disable_channel_C(self):
        self.status["setChC"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_C'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)
    def disable_channel_D(self):
        self.status["setChD"] = ps.ps3000aSetChannel(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'], DISABLED, ps.PS3000A_COUPLING['PS3000A_DC'], 7, self.analogue_offset)

    def setup_trigger(self, range, threshold, channel):
        self.status["maximumValue"] = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(self.maxADC))
        assert_pico_ok(self.status["maximumValue"])
        adcTriggerLevel = mV2adc(threshold, range, self.maxADC)

        self.status["setTrigger"] = ps.ps3000aSetSimpleTrigger(self.chandle,
                                                        1,
                                                        channel,
                                                        adcTriggerLevel,
                                                        ps.PS3000A_THRESHOLD_DIRECTION["PS3000A_RISING"],
                                                        0,
                                                        0)
        assert_pico_ok(self.status["setTrigger"])

    def autotrigger(self, channel, ch_range):
        self.status["maximumValue"] = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(self.maxADC))
        assert_pico_ok(self.status["maximumValue"])
        adcTriggerLevel = mV2adc(100, ch_range, self.maxADC)

        self.status["setTrigger"] = ps.ps3000aSetSimpleTrigger(self.chandle,
                                                        1,
                                                        channel,
                                                        adcTriggerLevel,
                                                        ps.PS3000A_THRESHOLD_DIRECTION["PS3000A_RISING"],
                                                        0,
                                                        10000)
        assert_pico_ok(self.status["setTrigger"])

    def start_data_collect(self, timebase=5):
        c_timeIndisposedMs = ctypes.c_double(0)
        c_timebase = ctypes.c_uint32(timebase)

        self.status["runblock"] = ps.ps3000aRunBlock(self.chandle, 0, self.samples, c_timebase, 1, ctypes.byref(c_timeIndisposedMs), 0, None, None)
        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            self.status["isReady"] = ps.ps3000aIsReady(self.chandle, ctypes.byref(ready))

        overflow = ctypes.c_int16(0)
        nSamples = self.samples
        noOfSamples = ctypes.c_uint64(nSamples)
        self.status["getValues"] = ps.ps3000aGetValues(self.chandle, 0, ctypes.byref(noOfSamples), 1, ps.PS3000A_RATIO_MODE["PS3000A_RATIO_MODE_NONE"], 0, ctypes.byref(overflow))
        assert_pico_ok(self.status["getValues"])
    
    def return_data(self):
        data = np.full((self.samples, 4), np.nan, dtype=np.float32)

        if self.activeA:
            data[:, 0] = adc2mV(self.bufferCompleteA, self.rangeA, self.maxADC)
        if self.activeB:
            data[:, 1] = adc2mV(self.bufferCompleteB, self.rangeB, self.maxADC)
        if self.activeC:
            data[:, 2] = adc2mV(self.bufferCompleteC, self.rangeC, self.maxADC)
        if self.activeD:
            data[:, 3] = adc2mV(self.bufferCompleteC, self.rangeD, self.maxADC)

        return data
    
    def stop_pico(self):
        self.status["stop"] = ps.ps3000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])

        self.status["close"] = ps.ps3000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["close"])