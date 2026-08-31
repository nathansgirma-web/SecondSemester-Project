# display.py
# All OLED drawing functions and screen layouts.

import time
import config

OLED_W  = 128
OLED_H  = 64
GRAPH_H = 40
TEXT_Y  = 50

# ------------------------------------------------------------------
# Icons — 8x8 pixel bitmaps
# ------------------------------------------------------------------

HEART_ICON = [
    0b00000000,
    0b01100110,
    0b11111111,
    0b11111111,
    0b11111111,
    0b01111110,
    0b00111100,
    0b00011000,
]

CHECK_ICON = [
    0b00000000,
    0b00000001,
    0b00000011,
    0b00000110,
    0b01001100,
    0b01111000,
    0b00110000,
    0b00000000,
]

PERSON_ICON = [
    0b00011000,
    0b00011000,
    0b00011000,
    0b01111110,
    0b11111111,
    0b00011000,
    0b00100100,
    0b01000010,
]

TRASH_ICON = [
    0b01111110,
    0b00011000,
    0b00011000,
    0b01111110,
    0b01111110,
    0b01111110,
    0b01111110,
    0b00111100,
]


# ------------------------------------------------------------------
# Large icons — 16x16 pixel bitmaps
# ------------------------------------------------------------------

HEART_LARGE = [
    0b0000000000000000,
    0b0000000000000000,
    0b0011100011100000,
    0b0111110111110000,
    0b1111111111111000,
    0b1111111111111000,
    0b1111111111111000,
    0b1111111111111000,
    0b0111111111110000,
    0b0011111111100000,
    0b0001111111000000,
    0b0000111110000000,
    0b0000011100000000,
    0b0000001000000000,
    0b0000000000000000,
    0b0000000000000000,
]

WIFI_ICON = [
    0b00000000,
    0b00111100,
    0b01111110,
    0b11000011,
    0b00011000,
    0b00111100,
    0b00100100,
    0b00011000,
]

MQTT_ICON = [
    0b11111111,
    0b10000001,
    0b10111101,
    0b10100101,
    0b10100101,
    0b10111101,
    0b10000001,
    0b11111111,
]


class Display:
    """All OLED screen drawing methods."""

    def __init__(self, oled):
        self._oled     = oled
        self._graph_x  = 0
        self._prev_y   = GRAPH_H // 2
        self._heart_on = False

    def _icon(self, icon, x, y, color=1):
        """Draw an 8x8 bitmap icon."""
        for row, byte in enumerate(icon):
            for col in range(8):
                if byte & (1 << (7 - col)):
                    self._oled.pixel(x + col, y + row, color)

    def _icon16(self, icon, x, y, color=1):
        """Draw a 16x16 bitmap icon (each row is a 16-bit int)."""
        for row, bits in enumerate(icon):
            for col in range(16):
                if bits & (1 << (15 - col)):
                    self._oled.pixel(x + col, y + row, color)

    def flash(self):
        """Brief white flash for screen transitions."""
        self._oled.fill(1)
        self._oled.show()
        time.sleep_ms(40)
        self._oled.fill(0)
        self._oled.show()

    def reset_graph(self):
        """Reset waveform graph state."""
        self._graph_x  = 0
        self._prev_y   = GRAPH_H // 2
        self._heart_on = False

    def draw_column(self, y):
        """
        Plot one waveform column.
        Connects to previous y to avoid gaps.
        Batch refresh every 8 columns.
        """
        for row in range(GRAPH_H):
            self._oled.pixel(self._graph_x, row, 0)
        for row in range(min(y, self._prev_y),
                         max(y, self._prev_y) + 1):
            self._oled.pixel(self._graph_x, row, 1)
        self._prev_y  = y
        self._graph_x = (self._graph_x + 1) % OLED_W
        if self._graph_x % 8 == 0:
            self._oled.show()

    def _dot_animation(self, step):
        """Return animated dots string: '.  ', '.. ', '...'"""
        dots = ["   ", ".  ", ".. ", "..."]
        return dots[step % 4]

    def splash(self):
        """Full animated boot splash sequence."""
        o = self._oled

        # --- Phase 1: fade in elements one by one ---
        o.fill(0)
        self._icon16(HEART_LARGE, 56, 4)
        o.show()
        time.sleep_ms(600)

        o.text("DontStress", 24, 26, 1)
        o.show()
        time.sleep_ms(500)

        o.hline(12, 42, 104, 1)
        o.show()
        time.sleep_ms(300)

        o.text("Initializing...", 16, 48, 1)
        o.show()
        time.sleep_ms(900)

        # --- Phase 2: double heartbeat pulse on the heart icon ---
        for _ in range(2):
            o.fill_rect(52, 0, 24, 22, 1)
            self._icon16(HEART_LARGE, 56, 4, color=0)
            o.show()
            time.sleep_ms(180)
            o.fill_rect(52, 0, 24, 22, 0)
            self._icon16(HEART_LARGE, 56, 4, color=1)
            o.show()
            time.sleep_ms(280)

        time.sleep_ms(600)

        # --- Phase 3: wipe out top half, draw ECG line sweeping across ---
        o.fill(0)
        o.hline(0, 30, OLED_W, 1)
        o.text("DontStress", 20, 38, 1)
        o.hline(0, 56, OLED_W, 1)
        o.show()
        time.sleep_ms(400)

        # ECG pulse path waypoints relative to baseline y=16
        ECG_Y = 16
        waypoints = [
            (0, 0), (30, 0), (38, -2), (44, -10), (48, 8), (52, 0),
            (60, -3), (66, 0), (128, 0)
        ]

        def ecg_y_at(x):
            for i in range(len(waypoints) - 1):
                x0, y0 = waypoints[i]
                x1, y1 = waypoints[i + 1]
                if x0 <= x <= x1:
                    t = (x - x0) / (x1 - x0) if x1 != x0 else 0
                    return ECG_Y + int(y0 + t * (y1 - y0))
            return ECG_Y

        prev_y = ECG_Y
        for x in range(OLED_W):
            cy = ecg_y_at(x)
            for yy in range(min(prev_y, cy), max(prev_y, cy) + 1):
                o.pixel(x, yy, 1)
            prev_y = cy
            if x % 4 == 0:
                o.show()
                time.sleep_ms(35)

        o.show()
        time.sleep_ms(1200)

        # --- Phase 4: wipe left-to-right to clear screen ---
        for x in range(0, OLED_W, 2):
            o.fill_rect(0, 0, x, OLED_H, 0)
            o.show()
            time.sleep_ms(20)

        o.fill(0)
        o.show()
        time.sleep_ms(150)

    def connecting_wifi(self, ssid):
        """Animated WiFi connecting screen. Returns when done drawing."""
        for step in range(8):
            self._oled.fill(0)
            self._icon(WIFI_ICON, 0, 0)
            self._oled.text("Connecting" + self._dot_animation(step), 12, 0, 1)
            self._oled.hline(0, 11, OLED_W, 1)
            self._oled.text("WiFi", 0, 18, 1)
            # Truncate SSID if too long
            label = ssid if len(ssid) <= 14 else ssid[:13] + "~"
            self._oled.text(label, 0, 30, 1)
            # Progress dots
            for d in range(step % 4 + 1):
                self._oled.fill_rect(4 + d * 10, 46, 6, 6, 1)
            self._oled.show()
            time.sleep_ms(300)

    def wifi_ok(self, ip):
        """WiFi connected confirmation."""
        self._oled.fill(0)
        self._icon(WIFI_ICON, 0, 0)
        self._oled.text("WiFi Connected", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text(ip, 0, 24, 1)
        # Draw a tick
        self._icon(CHECK_ICON, 56, 42)
        self._oled.show()
        time.sleep_ms(1000)

    def wifi_failed(self):
        """WiFi failed screen."""
        self._oled.fill(0)
        self._icon(WIFI_ICON, 0, 0)
        self._oled.text("WiFi Failed!", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text("Continuing", 0, 24, 1)
        self._oled.text("offline...", 0, 36, 1)
        self._oled.show()
        time.sleep_ms(1500)

    def connecting_mqtt(self, broker):
        """Animated MQTT connecting screen."""
        for step in range(6):
            self._oled.fill(0)
            self._icon(MQTT_ICON, 0, 0)
            self._oled.text("Connecting" + self._dot_animation(step), 12, 0, 1)
            self._oled.hline(0, 11, OLED_W, 1)
            self._oled.text("MQTT Broker", 0, 18, 1)
            label = broker if len(broker) <= 16 else broker[:15] + "~"
            self._oled.text(label, 0, 30, 1)
            for d in range(step % 4 + 1):
                self._oled.fill_rect(4 + d * 10, 46, 6, 6, 1)
            self._oled.show()
            time.sleep_ms(250)

    def mqtt_ok(self):
        """MQTT connected confirmation."""
        self._oled.fill(0)
        self._icon(MQTT_ICON, 0, 0)
        self._oled.text("MQTT Connected", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._icon(CHECK_ICON, 56, 30)
        self._oled.show()
        time.sleep_ms(800)

    def mqtt_failed(self):
        """MQTT failed screen."""
        self._oled.fill(0)
        self._icon(MQTT_ICON, 0, 0)
        self._oled.text("MQTT Failed!", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text("Local mode only", 0, 24, 1)
        self._oled.show()
        time.sleep_ms(1500)

    def status(self, line1, line2="", line3=""):
        """Generic three line status screen."""
        self._oled.fill(0)
        self._oled.hline(0, 0, OLED_W, 1)
        self._oled.text(line1, 0, 6, 1)
        self._oled.text(line2, 0, 24, 1)
        self._oled.text(line3, 0, 40, 1)
        self._oled.hline(0, 63, OLED_W, 1)
        self._oled.show()

    def menu(self, items, selected):
        """Main menu with heart icon and highlighted selection."""
        self._oled.fill(0)
        self._icon(HEART_ICON, 0, 0)
        self._oled.text("DontStress", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        for i, item in enumerate(items):
            y = 16 + i * 12
            if i == selected:
                self._oled.fill_rect(0, y - 2, OLED_W, 12, 1)
                self._oled.text("> " + item, 8, y, 0)
            else:
                self._oled.text("  " + item, 8, y, 1)
        self._oled.show()

    def patient_select(self, patient_num):
        """Patient selection screen — use existing patient."""
        self._oled.fill(0)
        self._icon(PERSON_ICON, 0, 0)
        self._oled.text("Select Patient", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        label = "Patient " + str(patient_num)
        x = (OLED_W - len(label) * 8) // 2
        self._oled.text(label, x, 22, 1)
        self._oled.text("Press = use this", 0, 38, 1)
        self._oled.text("Rot > = new pat.", 0, 50, 1)
        self._oled.show()

    def patient_select_new(self, next_num, can_cancel=True):
        """New patient confirmation screen."""
        self._oled.fill(0)
        self._icon(PERSON_ICON, 0, 0)
        self._oled.text("New Patient", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        label = "Patient " + str(next_num)
        x = (OLED_W - len(label) * 8) // 2
        self._oled.text(label, x, 22, 1)
        self._oled.text("Press = confirm", 0, 38, 1)
        if can_cancel:
            self._oled.text("Rot < = cancel", 0, 50, 1)
        self._oled.show()

    def calibrating(self):
        """Shown while waiting for calibration."""
        self._oled.fill(0)
        self._oled.hline(0, GRAPH_H + 2, OLED_W, 1)
        self._oled.text("Calibrating...", 0, TEXT_Y, 1)
        self._oled.show()

    def collecting(self, secs_left, bpm):
        """
        Bottom bar during 30s collection.
        Shows progress bar, BPM and static heart.
        Called once per second.
        """
        self._oled.fill_rect(0, GRAPH_H + 3, OLED_W,
                             OLED_H - GRAPH_H, 0)
        self._oled.hline(0, GRAPH_H + 2, OLED_W, 1)
        elapsed_pct = max(0.0, 1.0 - (secs_left / config.COLLECT_SECS))
        bar_w = int(elapsed_pct * (OLED_W - 2))
        self._oled.rect(0, GRAPH_H + 4, OLED_W, 5, 1)
        if bar_w > 0:
            self._oled.fill_rect(1, GRAPH_H + 5, bar_w, 3, 1)
        self._oled.text(str(secs_left) + "s " + str(bpm) + "bpm",
                        0, TEXT_Y + 2, 1)
        self._icon(HEART_ICON, OLED_W - 10, TEXT_Y, 1)
        self._oled.show()

    def local_results(self, results, session_num, patient_num):
        """Show local HRV results."""
        self._oled.fill(0)
        self._icon(CHECK_ICON, 0, 0)
        self._oled.text("P" + str(patient_num) +
                        "  S" + str(session_num), 12, 0, 1)
        self._oled.hline(0, 10, OLED_W, 1)
        self._oled.text("PPI: "  + str(results["mean_ppi"]) + "ms",  0, 14, 1)
        self._oled.text("HR:  "  + str(results["mean_hr"])  + "bpm", 0, 26, 1)
        self._oled.text("SDNN:"  + str(results["sdnn"])     + "ms",  0, 38, 1)
        self._oled.text("RMSSD:" + str(results["rmssd"])    + "ms",  0, 50, 1)
        self._oled.show()

    def kubios_results(self, data, patient_num):
        """Show Kubios HRV results."""
        self._oled.fill(0)
        self._oled.text("Kubios P" + str(patient_num), 0, 0, 1)
        self._oled.hline(0, 10, OLED_W, 1)
        try:
            result = data["data"]["analysis"]
            self._oled.text("HR:  " + str(round(
                result.get("mean_hr_bpm", 0))),    0, 14, 1)
            self._oled.text("RMSSD:" + str(round(
                result.get("rmssd_ms",   0))),     0, 26, 1)
            self._oled.text("SDNN: " + str(round(
                result.get("sdnn_ms",    0))),     0, 38, 1)
            self._oled.text("SNS:  " + str(round(
                result.get("sns_index",  0), 1)),  0, 50, 1)
        except Exception as e:
            self._oled.text("Parse error", 0, 30, 1)
            print("Kubios parse error:", e)
        self._oled.show()

    def history_patient_select(self, patient_num, session_count):
        """Patient history selection screen."""
        self._oled.fill(0)
        self._icon(PERSON_ICON, 0, 0)
        self._oled.text("History", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text("Patient " + str(patient_num), 24, 22, 1)
        self._oled.text(str(session_count) + " session(s)", 24, 36, 1)
        self._oled.text("<rotate  press>", 0, 52, 1)
        self._oled.show()

    def history_session(self, session, index, total):
        """Show one saved session."""
        self._oled.fill(0)
        patient = session.get("patient", 1)
        self._oled.text("P" + str(patient) +
                        " Session " + str(index + 1) +
                        "/" + str(total),
                        0, 0, 1)
        self._oled.hline(0, 10, OLED_W, 1)
        self._oled.text("PPI: "  + str(session["mean_ppi"]) + "ms",  0, 14, 1)
        self._oled.text("HR:  "  + str(session["mean_hr"])  + "bpm", 0, 26, 1)
        self._oled.text("SDNN:"  + str(session["sdnn"])     + "ms",  0, 38, 1)
        self._oled.text("RMSSD:" + str(session["rmssd"])    + "ms",  0, 50, 1)
        self._oled.show()

    def delete_session_option(self, session_num):
        """Delete single session confirmation screen."""
        self._oled.fill(0)
        self._icon(TRASH_ICON, 0, 0)
        self._oled.text("Delete session?", 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text("Session " + str(session_num), 0, 22, 1)
        self._oled.text("Press=confirm", 0, 38, 1)
        self._oled.text("Rotate=cancel", 0, 50, 1)
        self._oled.show()

    def delete_patient(self, patient_num):
        """Delete all sessions for one patient confirmation screen."""
        self._oled.fill(0)
        self._icon(TRASH_ICON, 0, 0)
        self._oled.text("Delete P" + str(patient_num), 12, 0, 1)
        self._oled.hline(0, 11, OLED_W, 1)
        self._oled.text("Remove all data", 0, 18, 1)
        self._oled.text("for Patient " + str(patient_num), 0, 30, 1)
        self._oled.text("Press=confirm", 0, 44, 1)
        self._oled.text("Rotate=cancel", 0, 54, 1)
        self._oled.show()

    def confirm_clear_all(self):
        """Confirm delete all history screen."""
        self._oled.fill(0)
        self._oled.text("Delete ALL", 20, 10, 1)
        self._oled.text("history?", 30, 24, 1)
        self._oled.text("Press = YES", 16, 40, 1)
        self._oled.text("Rotate = NO", 16, 52, 1)
        self._oled.show()