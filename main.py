# main.py
# Entry point. Boots hardware, connects network,
# then runs the main loop.

from machine import Pin, ADC, I2C
from fifo import Fifo
from ssd1306 import SSD1306_I2C
from storage import Storage
from network_manager import NetworkManager
from display import Display
from menu import AppMenu
import config
import time


class SensorADC:
    """ADC sensor with FIFO buffer for interrupt-safe sampling."""
    def __init__(self):
        self.adc     = ADC(Pin(config.ADC_PIN))
        self.samples = Fifo(config.FIFO_SIZE)

    def handler(self, tid):
        self.samples.put(self.adc.read_u16())


class Encoder:
    """
    Rotary encoder with push button.
    Short press (<600ms) = select/confirm.
    Long press  (>600ms) = back.
    Call update() every main loop iteration.
    """

    LONG_PRESS_MS = 600

    def __init__(self):
        self.a         = Pin(config.ROT_A,  Pin.IN, Pin.PULL_UP)
        self.b         = Pin(config.ROT_B,  Pin.IN, Pin.PULL_UP)
        self.sw        = Pin(config.ROT_SW, Pin.IN, Pin.PULL_UP)
        self._prev_a   = self.a.value()
        self._prev_sw  = self.sw.value()
        self._press_ms = None
        self.delta     = 0
        self.pressed   = False   # short press
        self.back      = False   # long press

    def update(self):
        # --- Rotation ---
        curr_a = self.a.value()
        if self._prev_a == 1 and curr_a == 0:
            self.delta = -1 if self.b.value() == 0 else 1
        else:
            self.delta = 0
        self._prev_a = curr_a

        # --- Button ---
        curr_sw = self.sw.value()
        if self._prev_sw == 1 and curr_sw == 0:
            # Pressed down — record time
            self._press_ms = time.ticks_ms()
        elif self._prev_sw == 0 and curr_sw == 1:
            # Released — classify as short or long
            if self._press_ms is not None:
                duration = time.ticks_diff(
                    time.ticks_ms(), self._press_ms)
                if duration >= self.LONG_PRESS_MS:
                    self.back = True
                else:
                    self.pressed = True
                self._press_ms = None
        self._prev_sw = curr_sw

    def consume_press(self):
        """Return and clear short press flag."""
        p = self.pressed
        self.pressed = False
        return p

    def consume_back(self):
        """Return and clear long press (back) flag."""
        b = self.back
        self.back = False
        return b


class LED:
    def __init__(self):
        self._pin = Pin(config.LED_PIN, Pin.OUT)

    def on(self):
        self._pin.on()

    def off(self):
        self._pin.off()

    def toggle(self):
        self._pin.toggle()


# --- Init hardware ---
i2c      = I2C(config.I2C_ID,
               scl=Pin(config.I2C_SCL),
               sda=Pin(config.I2C_SDA),
               freq=400000)
raw_oled = SSD1306_I2C(128, 64, i2c)
disp     = Display(raw_oled)
sensor   = SensorADC()
encoder  = Encoder()
led      = LED()
stor     = Storage()
net      = NetworkManager()

# --- Boot ---
disp.splash()
wifi_ok = net.connect_wifi(disp)
if wifi_ok:
    net.connect_mqtt(disp)

# --- Init app ---
app = AppMenu(disp, stor, net, sensor, led)

# --- Show menu ---
disp.flash()
from menu import MENU_ITEMS
disp.menu(MENU_ITEMS, 0)

# --- Main loop ---
while True:
    encoder.update()
    net.check_messages()
    app.update(encoder)