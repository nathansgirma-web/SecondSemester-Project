# sampling.py
# PIO timer + FIFO sample collection at 250Hz.
# The ISR only reads ADC and stores in FIFO.
# Main loop drains FIFO via get_sample().

from piotimer import Piotimer
import config


class Sampler:
    """
    Manages 250Hz ADC sampling using PIO hard interrupt timer.
    Samples stored in SensorADC FIFO for main loop to consume.
    """

    def __init__(self, sensor):
        self._sensor = sensor
        self._timer  = None

    def start(self):
        """Start PIO timer at SAMPLE_RATE Hz."""
        self._timer = Piotimer(
            mode     = Piotimer.PERIODIC,
            freq     = config.SAMPLE_RATE,
            callback = self._sensor.handler
        )

    def stop(self):
        """Stop PIO timer and release resource."""
        if self._timer:
            self._timer.deinit()
            self._timer = None

    def has_data(self):
        """Return True if samples are waiting in FIFO."""
        return self._sensor.samples.has_data()

    def get_sample(self):
        """Return next sample from FIFO."""
        return self._sensor.samples.get()