# menu.py
# Menu logic and navigation state machine.
# Short press = select/confirm.
# Long press  = back to previous screen.

import time
import math
import config
from display import GRAPH_H

# --- App states ---
STATE_MENU            = 0
STATE_PATIENT_SELECT  = 1
STATE_MEASURING       = 2
STATE_LOCAL_RESULTS   = 3
STATE_KUBIOS_WAIT     = 4
STATE_KUBIOS_RESULTS  = 5
STATE_HISTORY_PATIENT = 6
STATE_HISTORY         = 7
STATE_CONFIRM_CLEAR          = 8
STATE_CONFIRM_DELETE_SESSION = 9

MENU_ITEMS     = ["Start", "Kubios", "History", "Clear All"]
KUBIOS_TIMEOUT = 15000
DRAW_EVERY     = 10


class HRVAnalyser:
    """Calculates mean PPI, mean HR, SDNN and RMSSD."""

    def calculate(self, ppi_list):
        n = len(ppi_list)
        if n < 2:
            return None
        mean_ppi = sum(ppi_list) / n
        mean_hr  = 60000 / mean_ppi
        variance = sum((p - mean_ppi) ** 2 for p in ppi_list) / n
        sdnn     = math.sqrt(variance)
        diffs_sq = [(ppi_list[i] - ppi_list[i-1]) ** 2
                    for i in range(1, n)]
        rmssd    = math.sqrt(sum(diffs_sq) / len(diffs_sq))
        return {
            "mean_ppi": round(mean_ppi),
            "mean_hr":  round(mean_hr),
            "sdnn":     round(sdnn),
            "rmssd":    round(rmssd)
        }


def sma_update(buf, value):
    """Simple moving average filter."""
    buf.append(value)
    if len(buf) > config.SMA_WINDOW:
        buf.pop(0)
    return sum(buf) // len(buf)


def reset_measurement():
    """Return a fresh measurement state dictionary."""
    return {
        "sma_buf":      [],
        "win_count":    0,
        "win_min":      (1 << 16) - 1,
        "win_max":      0,
        "threshold":    None,
        "win_number":   0,
        "above":        False,
        "cur_max":      0,
        "cur_peak":     0,
        "prev_peak":    0,
        "sample_count": 0,
        "bpm":          0,
        "draw_counter": 0,
        "ppi_list":     [],
        "start_time":   None,
        "last_display_ms": 0,
    }


class AppMenu:
    """
    App state machine.
    Short press = select. Long press = back.
    """

    def __init__(self, display, storage, network, sensor, led):
        self._disp    = display
        self._stor    = storage
        self._net     = network
        self._sensor  = sensor
        self._led     = led
        self._hrv     = HRVAnalyser()
        self._timer   = None

        self._state               = STATE_MENU
        self._menu_idx            = 0
        self._current_patient     = storage.get_patient()
        self._patient_new_mode    = False
        self._next_patient_num    = self._current_patient + 1
        self._last_ppi_list       = []
        self._kubios_start        = 0
        self._history_sessions         = []
        self._history_index            = 0
        self._history_patient_idx      = 0
        self._last_viewed_session_idx  = 0
        self._m                   = reset_measurement()

        print("Current patient:", self._current_patient)

    def update(self, encoder):
        """Call every main loop iteration."""
        if self._state == STATE_MENU:
            self._handle_menu(encoder)
        elif self._state == STATE_PATIENT_SELECT:
            self._handle_patient_select(encoder)
        elif self._state == STATE_MEASURING:
            self._handle_measuring(encoder)
        elif self._state == STATE_LOCAL_RESULTS:
            self._handle_local_results(encoder)
        elif self._state == STATE_KUBIOS_WAIT:
            self._handle_kubios_wait()
        elif self._state == STATE_KUBIOS_RESULTS:
            self._handle_kubios_results(encoder)
        elif self._state == STATE_CONFIRM_CLEAR:
            self._handle_confirm_clear(encoder)
        elif self._state == STATE_HISTORY_PATIENT:
            self._handle_history_patient(encoder)
        elif self._state == STATE_HISTORY:
            self._handle_history(encoder)
        elif self._state == STATE_CONFIRM_DELETE_SESSION:
            self._handle_confirm_delete_session(encoder)

    def _go_to_menu(self):
        """Return to main menu."""
        self._state = STATE_MENU
        self._disp.flash()
        self._disp.menu(MENU_ITEMS, self._menu_idx)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _handle_menu(self, encoder):
        encoder.consume_back()
        if encoder.delta != 0:
            self._menu_idx = ((self._menu_idx + encoder.delta)
                              % len(MENU_ITEMS))
            self._disp.menu(MENU_ITEMS, self._menu_idx)
            time.sleep_ms(5)
        if encoder.consume_press():
            time.sleep_ms(200)
            self._on_menu_select()

    def _on_menu_select(self):
        if self._menu_idx == 0:
            self._patient_new_mode = False
            all_nums = self._stor.get_all_patients()
            self._next_patient_num = (max(all_nums) + 1
                                      if all_nums else 1)
            self._disp.flash()
            if not all_nums:
                # No patients yet — go straight to new patient screen
                self._patient_new_mode = True
                self._disp.patient_select_new(self._next_patient_num,
                                              can_cancel=False)
            else:
                self._disp.patient_select(self._current_patient)
            self._state = STATE_PATIENT_SELECT

        elif self._menu_idx == 1:
            sessions = self._stor.get_sessions()
            if not sessions:
                self._disp.status("No sessions yet.",
                                  "Run Start first.", "")
                time.sleep_ms(2000)
                self._disp.menu(MENU_ITEMS, self._menu_idx)
            elif not self._net.is_connected():
                self._disp.status("No MQTT", "connection.", "")
                time.sleep_ms(2000)
                self._disp.menu(MENU_ITEMS, self._menu_idx)
            else:
                last         = sessions[0]
                ppi_list     = last.get("ppi_list", [])
                last_patient = last.get("patient", 1)
                if not ppi_list:
                    self._disp.status("No PPI data",
                                      "in last session.", "")
                    time.sleep_ms(2000)
                    self._disp.menu(MENU_ITEMS, self._menu_idx)
                else:
                    self._send_kubios(ppi_list, last_patient)

        elif self._menu_idx == 2:
            all_p = self._stor.get_all_patients()
            if all_p:
                self._history_patient_idx = 0
                p        = all_p[0]
                sessions = self._stor.get_sessions_for_patient(p)
                self._disp.flash()
                self._disp.history_patient_select(p, len(sessions))
                self._state = STATE_HISTORY_PATIENT
            else:
                self._disp.status("No history yet.",
                                  "Run a session", "first.")
                time.sleep_ms(2000)
                self._disp.menu(MENU_ITEMS, self._menu_idx)

        elif self._menu_idx == 3:
            self._disp.confirm_clear_all()
            self._state = STATE_CONFIRM_CLEAR

    # ------------------------------------------------------------------
    # Patient select
    # ------------------------------------------------------------------

    def _handle_patient_select(self, encoder):
        if encoder.consume_back():
            self._go_to_menu()
            return

        if not self._patient_new_mode:
            # --- Current patient mode ---
            if encoder.delta > 0:
                # Rotate right → switch to new patient mode
                self._patient_new_mode = True
                self._disp.patient_select_new(self._next_patient_num)
                time.sleep_ms(5)
            if encoder.consume_press():
                time.sleep_ms(200)
                self._stor.set_patient(self._current_patient)
                self._disp.flash()
                self._start_measuring()
                print("Patient", self._current_patient, "selected.")
        else:
            # --- New patient mode ---
            if encoder.delta < 0:
                # Rotate left → cancel only if there's an existing patient
                all_nums = self._stor.get_all_patients()
                if all_nums:
                    self._patient_new_mode = False
                    self._disp.patient_select(self._current_patient)
                    time.sleep_ms(5)
            if encoder.consume_press():
                time.sleep_ms(200)
                # Promote next patient number as current
                self._current_patient = self._next_patient_num
                self._stor.set_patient(self._current_patient)
                self._disp.flash()
                self._start_measuring()
                print("New patient", self._current_patient, "selected.")

    # ------------------------------------------------------------------
    # Measuring
    # ------------------------------------------------------------------

    def _handle_measuring(self, encoder):
        if encoder.consume_back() or encoder.consume_press():
            time.sleep_ms(200)
            self._stop_measuring()
            self._m = reset_measurement()
            self._go_to_menu()
            return

        m = self._m

        peak_this_round    = False
        samples_this_round = 0

        while self._sensor.samples.has_data():
            raw      = self._sensor.samples.get()
            filtered = sma_update(m["sma_buf"], raw)
            m["sample_count"] += 1
            m["draw_counter"] += 1
            samples_this_round += 1

            if filtered < m["win_min"]:
                m["win_min"] = filtered
            if filtered > m["win_max"]:
                m["win_max"] = filtered

            m["win_count"] += 1
            if m["win_count"] >= config.THRESHOLD_WINDOW:
                m["win_number"] += 1
                sig_range      = m["win_max"] - m["win_min"]
                m["threshold"] = int(m["win_min"] +
                                     sig_range * config.THRESHOLD_PCT)
                if m["win_number"] == config.CALIBRATION_WINS:
                    m["start_time"] = time.ticks_ms()
                    print("Calibration done. Collecting 30s...")
                m["win_count"] = 0
                m["win_min"]   = (1 << 16) - 1
                m["win_max"]   = 0
                m["above"]     = False
                m["cur_max"]   = 0
                m["prev_peak"] = 0

            if (m["threshold"] is None or
                    m["win_number"] < config.CALIBRATION_WINS):
                continue

            if filtered > m["threshold"]:
                m["above"] = True
                if filtered > m["cur_max"]:
                    m["cur_max"]  = filtered
                    m["cur_peak"] = m["sample_count"]
            else:
                if m["above"]:
                    if m["prev_peak"] > 0:
                        n      = m["cur_peak"] - m["prev_peak"]
                        ppi_ms = n * config.SAMPLE_INTERVAL
                        if config.PPI_MIN_MS < ppi_ms < config.PPI_MAX_MS:
                            m["ppi_list"].append(ppi_ms)
                            m["bpm"] = int(60000 / ppi_ms)
                            self._led.off()
                            self._led.on()
                            print("PPI:", ppi_ms, "ms BPM:", m["bpm"],
                                  "n:", len(m["ppi_list"]))
                    m["prev_peak"] = m["cur_peak"]
                    m["above"]     = False
                    m["cur_max"]   = 0

        # Draw waveform every DRAW_EVERY samples
        if m["draw_counter"] % DRAW_EVERY == 0 and m["sma_buf"]:
            sig_range = (m["win_max"] - m["win_min"]
                         if m["win_max"] > m["win_min"] else 1)
            val = m["sma_buf"][-1]
            y   = int((1.0 - (val - m["win_min"]) / sig_range)
                      * (GRAPH_H - 1))
            y   = max(0, min(GRAPH_H - 1, y))
            self._disp.draw_column(y)

        # Update bottom bar every real second
        if m["start_time"]:
            elapsed   = time.ticks_diff(time.ticks_ms(), m["start_time"])
            secs_left = max(0, config.COLLECT_SECS - elapsed // 1000)
            now = time.ticks_ms()
            if time.ticks_diff(now, m["last_display_ms"]) >= 1000:
                m["last_display_ms"] = now
                self._disp.collecting(secs_left, m["bpm"])

        # Check 30 seconds done
        if m["start_time"]:
            elapsed = time.ticks_diff(time.ticks_ms(), m["start_time"])
            if elapsed >= config.COLLECT_SECS * 1000:
                self._stop_measuring()
                self._finish_collection()

    # ------------------------------------------------------------------
    # Local results
    # ------------------------------------------------------------------

    def _handle_local_results(self, encoder):
        if encoder.consume_back():
            self._go_to_menu()
            return
        if encoder.consume_press():
            time.sleep_ms(200)
            if self._net.is_connected() and self._last_ppi_list:
                self._send_kubios(self._last_ppi_list,
                                  self._current_patient)
            else:
                self._go_to_menu()

    # ------------------------------------------------------------------
    # Kubios wait
    # ------------------------------------------------------------------

    def _handle_kubios_wait(self):
        elapsed = time.ticks_diff(time.ticks_ms(), self._kubios_start)
        self._disp.status("Waiting for",
                          "Kubios...",
                          str(elapsed // 1000) + "s")
        response = self._net.get_kubios_response()
        if response:
            print("Kubios result:", response)
            self._disp.flash()
            self._disp.kubios_results(response, self._current_patient)
            self._state = STATE_KUBIOS_RESULTS
        elif elapsed > KUBIOS_TIMEOUT:
            self._disp.status("Kubios timeout.", "No response.", "")
            time.sleep_ms(2000)
            self._go_to_menu()

    # ------------------------------------------------------------------
    # Kubios results
    # ------------------------------------------------------------------

    def _handle_kubios_results(self, encoder):
        if encoder.consume_back():
            self._go_to_menu()
            return
        if encoder.consume_press():
            time.sleep_ms(200)
            self._go_to_menu()

    # ------------------------------------------------------------------
    # Confirm clear all
    # ------------------------------------------------------------------

    def _handle_confirm_clear(self, encoder):
        if encoder.consume_back():
            self._disp.status("Cancelled.", "", "")
            time.sleep_ms(1000)
            self._go_to_menu()
            return
        if encoder.delta != 0:
            self._disp.status("Cancelled.", "", "")
            time.sleep_ms(1000)
            self._go_to_menu()
        if encoder.consume_press():
            time.sleep_ms(200)
            self._stor.clear_all()
            self._current_patient = 1
            self._disp.flash()
            self._disp.status("History cleared.",
                              "Patient reset", "to 1.")
            time.sleep_ms(2000)
            self._go_to_menu()

    # ------------------------------------------------------------------
    # History patient select
    # ------------------------------------------------------------------

    def _handle_history_patient(self, encoder):
        if encoder.consume_back():
            self._go_to_menu()
            return
        all_p = self._stor.get_all_patients()
        if encoder.delta != 0 and all_p:
            self._history_patient_idx = ((self._history_patient_idx +
                                          encoder.delta) % len(all_p))
            p        = all_p[self._history_patient_idx]
            sessions = self._stor.get_sessions_for_patient(p)
            self._disp.history_patient_select(p, len(sessions))
            time.sleep_ms(5)
        if encoder.consume_press():
            time.sleep_ms(200)
            if all_p:
                p = all_p[self._history_patient_idx]
                self._history_sessions = \
                    self._stor.get_sessions_for_patient(p)
                if self._history_sessions:
                    self._history_index = 0
                    self._last_viewed_session_idx = 0
                    self._disp.flash()
                    self._disp.history_session(
                        self._history_sessions[0], 0,
                        len(self._history_sessions))
                    self._state = STATE_HISTORY
                else:
                    self._disp.status("No sessions for",
                                      "Patient " + str(p), "")
                    time.sleep_ms(2000)
            else:
                self._go_to_menu()

    # ------------------------------------------------------------------
    # History session view + delete session + delete patient
    # ------------------------------------------------------------------

    def _handle_history(self, encoder):
        """
        Rotate = browse sessions. Last slot = delete patient.
        Press on a session = delete that session confirmation.
        Long press = back to patient select.
        """
        if encoder.consume_back():
            all_p = self._stor.get_all_patients()
            if all_p:
                p        = all_p[self._history_patient_idx]
                sessions = self._stor.get_sessions_for_patient(p)
                self._disp.flash()
                self._disp.history_patient_select(p, len(sessions))
                self._state = STATE_HISTORY_PATIENT
            else:
                self._go_to_menu()
            return

        all_p       = self._stor.get_all_patients()
        n           = len(self._history_sessions)
        total_slots = n + 1   # sessions + delete patient

        if encoder.delta != 0:
            self._history_index = ((self._history_index + encoder.delta)
                                   % total_slots)
            if self._history_index < n:
                self._disp.history_session(
                    self._history_sessions[self._history_index],
                    self._history_index, n)
            else:
                # Delete patient slot
                if all_p:
                    p = all_p[self._history_patient_idx]
                    self._disp.delete_patient(p)
            time.sleep_ms(5)

        if encoder.consume_press():
            time.sleep_ms(200)

            if self._history_index < n:
                # Press on a session → show delete confirmation
                session = self._history_sessions[self._history_index]
                self._disp.delete_session_option(self._history_index + 1)
                self._state = STATE_CONFIRM_DELETE_SESSION

            else:
                # Press on delete patient slot → confirm and delete
                if all_p:
                    p = all_p[self._history_patient_idx]
                    self._stor.delete_patient(p)
                    self._disp.flash()
                    self._disp.status("Patient " + str(p),
                                      "deleted.", "")
                    time.sleep_ms(1500)
                    remaining = self._stor.get_all_patients()
                    if remaining:
                        self._history_patient_idx = 0
                        rp       = remaining[0]
                        sessions = self._stor\
                            .get_sessions_for_patient(rp)
                        self._disp.history_patient_select(
                            rp, len(sessions))
                        self._state = STATE_HISTORY_PATIENT
                    else:
                        self._go_to_menu()

    # ------------------------------------------------------------------
    # Confirm delete session
    # ------------------------------------------------------------------

    def _handle_confirm_delete_session(self, encoder):
        """
        Press = confirm delete. Rotate or long press = cancel.
        """
        if encoder.consume_back() or encoder.delta != 0:
            # Cancel — go back to session view
            session = self._history_sessions[self._history_index]
            self._disp.history_session(session,
                                       self._history_index,
                                       len(self._history_sessions))
            self._state = STATE_HISTORY
            return

        if encoder.consume_press():
            time.sleep_ms(200)
            session = self._history_sessions[self._history_index]
            self._stor.delete_session(session["session"])
            self._disp.flash()
            self._disp.status("Session deleted.", "", "")
            time.sleep_ms(1500)
            # Refresh session list
            all_p = self._stor.get_all_patients()
            if all_p:
                p = all_p[self._history_patient_idx]
                self._history_sessions = \
                    self._stor.get_sessions_for_patient(p)
                if self._history_sessions:
                    self._history_index = 0
                    self._last_viewed_session_idx = 0
                    self._disp.history_session(
                        self._history_sessions[0], 0,
                        len(self._history_sessions))
                    self._state = STATE_HISTORY
                else:
                    sessions = self._stor.get_sessions_for_patient(p)
                    self._disp.history_patient_select(p, len(sessions))
                    self._state = STATE_HISTORY_PATIENT
            else:
                self._go_to_menu()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _start_measuring(self):
        from piotimer import Piotimer
        self._m = reset_measurement()
        self._disp.reset_graph()
        self._disp.calibrating()
        self._timer = Piotimer(
            mode     = Piotimer.PERIODIC,
            freq     = config.SAMPLE_RATE,
            callback = self._sensor.handler
        )
        self._state = STATE_MEASURING
        print("Started. Patient", self._current_patient,
              "calibrating...")

    def _stop_measuring(self):
        if self._timer:
            self._timer.deinit()
            self._timer = None
        self._led.off()

    def _finish_collection(self):
        results = self._hrv.calculate(self._m["ppi_list"])
        if results:
            self._last_ppi_list = self._m["ppi_list"][:]
            self._stor.add_session(results, self._last_ppi_list,
                                   self._current_patient)
            session_num = self._stor.get_sessions()[0]["session"]
            self._print_results(results, session_num)
            self._disp.flash()
            self._disp.local_results(results, session_num,
                                     self._current_patient)
            self._state = STATE_LOCAL_RESULTS
        else:
            self._disp.status("Not enough data.", "Try again.", "")
            time.sleep_ms(2000)
            self._go_to_menu()

    def _send_kubios(self, ppi_list, patient_num):
        self._disp.status("Sending to",
                          "Kubios...",
                          str(len(ppi_list)) + " PPIs")
        ok = self._net.publish_kubios(ppi_list, patient_num)
        if ok:
            self._kubios_start = time.ticks_ms()
            self._disp.flash()
            self._state = STATE_KUBIOS_WAIT
        else:
            self._disp.status("MQTT failed.",
                              "Check connection.", "")
            time.sleep_ms(2000)
            self._disp.menu(MENU_ITEMS, self._menu_idx)

    def _print_results(self, results, session_num):
        print("--- Patient", self._current_patient,
              "Session", session_num, "---")
        print("Mean PPI:", results["mean_ppi"], "ms")
        print("Mean HR: ", results["mean_hr"],  "bpm")
        print("SDNN:    ", results["sdnn"],     "ms")
        print("RMSSD:   ", results["rmssd"],    "ms")
        print("--------------------")