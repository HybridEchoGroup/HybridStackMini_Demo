from abc import ABC, abstractmethod

class PicoScope(ABC):

    @abstractmethod
    def __init__(self, samples=312500):
        pass

    @abstractmethod
    def enable_channel_A(self, range):
        pass

    @abstractmethod
    def enable_channel_B(self, range):
        pass

    @abstractmethod
    def enable_channel_C(self, range):
        pass
    
    @abstractmethod
    def enable_channel_D(self, range):
        pass

    @abstractmethod
    def disable_channel_A(self):
        pass

    @abstractmethod
    def disable_channel_B(self):
        pass

    @abstractmethod
    def disable_channel_C(self):
        pass

    @abstractmethod
    def disable_channel_D(self):
        pass

    @abstractmethod
    def setup_trigger(self, range, threshold, channel):
        pass

    @abstractmethod
    def autotrigger(self, channel, ch_range):
        pass

    @abstractmethod
    def start_data_collect(self, timebase=5):
        pass

    @abstractmethod
    def return_data(self):
        pass

    @abstractmethod
    def stop_pico(self):
        pass

def create_backend(model: str):
    import importlib
    module = importlib.import_module(f"driver.pico{model}_single")
    return module.pico_handler