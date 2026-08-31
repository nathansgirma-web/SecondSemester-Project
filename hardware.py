# [hardware.py](http://hardware.py)
# Hardware initialization: OLED, sensor, LED, encoder.
# All physical pin setup lives here.
from machine import Pin, ADC, I2C
from fifo import Fifo
from ssd1306 import SSD1306_I2C
from led import Led
import config
class SensorADC:
    """ADC sensor with FIFO buffer for interrupt-safe sampling."""
    def __init__(self):
        self.adc     = ADC(Pin(config.ADC_PIN))
        self.samples = Fifo(config.FIFO_SIZE)
    def handler(self, tid):
        # ISR: only read ADC and push to FIFO — nothing else
        self.samples.put([self.adc.read](http://self.adc.read)_u16())
class Encoder:
    """
    Rotary encoder with push button.
    Rotation right = positive delta (scroll down).
    Rotation left  = negative delta (scroll up).
    Call update() every main loop iteration.
    """
    def __init__(self):
        self.a        = Pin(config.ROT_A,  [Pin.IN](http://Pin.IN), Pin.PULL_UP)
        self.b        = Pin(config.ROT_B,  [Pin.IN](http://Pin.IN), Pin.PULL_UP)
        self.sw       = Pin(config.ROT_SW, [Pin.IN](http://Pin.IN), Pin.PULL_UP)
        self._prev_a  = self.a.value()
        self._prev_sw = self.sw.value()
        [self.delta](http://self.delta)    = 0
        self.pressed  = False
    def update(self):
        """Poll encoder state. Call every loop iteration."""
        curr_a = self.a.value()
        if self._prev_a == 1 and curr_a == 0:
            # Right = scroll down (+1), Left = scroll up (-1)
            [self.delta](http://self.delta) = 1 if self.b.value() == 0 else -1
        else:
            [self.delta](http://self.delta) = 0
        self._prev_a = curr_a
        curr_sw = self.sw.value()
        if self._prev_sw == 1 and curr_sw == 0:
            self.pressed = True
        self._prev_sw = curr_sw
    def consume_press(self):
        """Return and clear pressed flag."""
        p = self.pressed
        self.pressed = False
        return p
class LED:
    """Dimmable LED wrapper at 75% brightness."""
    def __init__(self):
        self._led = Led(config.LED_PIN, brightness=75)
    def on(self):
        self._led.on()
    def off(self):
        self._led.off()
    def toggle(self):
        self._led.toggle()
def make_oled():
    """Initialise and return the SSD1306 OLED display."""
    i2c = I2C(config.I2C_ID,
              scl=Pin(config.I2C_SCL),
              sda=Pin(config.I2C_SDA),
              freq=400000)
    return SSD1306_I2C(128, 64, i2c)