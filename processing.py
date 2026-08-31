# processing.py
# PPG signal processing: SMA filter, peak detection,
# PPI calculation, BPM and HRV analysis.

import math
import time
import config


def sma_filter(buf, value):
    """
    Simple moving average filter.
    buf: list used as rolling buffer (modified in place).
    Returns filtered integer value.
    """
    buf.append(value)
    if len(buf) > config.SMA_WINDOW:
        buf.pop(0)
    return sum(buf) // len(buf)


class PeakDetector:
    """
    Detects heartbeat peaks in smoothed PPG signal.
    Uses adaptive threshold: min + 75% of (max - min)
    recalculated every THRESHOLD_WINDOW samples (2 seconds).
    Refractory period prevents double-trigger on same beat.
    PPI measured from sample count difference x SAMPLE_INTERVAL.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all detection state."""
        self._sma_buf      = []
        self._win_count    = 0
        self._win_min      = (1 << 16) - 1
        self._win_max      = 0
        self._threshold    = None
        self._win_number   = 0
        self._above        = False
        self._cur_max      = 0
        self._cur_peak     = 0
        self._prev_peak    = 0
        self._sample_count = 0
        self.ppi_list      = []
        self.bpm           = 0
        self.start_time    = None

    def _update_threshold(self, value):
        """
        Track min/max over THRESHOLD_WINDOW samples.
        Recalculate threshold when window fills.
        """
        self._win_count += 1
        if value < self._win_min:
            self._win_min = value
        if value > self._win_max:
            self._win_max = value

        if self._win_count >= config.THRESHOLD_WINDOW:
            self._win_number += 1
            sig_range       = self._win_max - self._win_min
            self._threshold = int(self._win_min +
                                  sig_range * config.THRESHOLD_PCT)

            if self._win_number == config.CALIBRATION_WINS:
                self.start_time = time.ticks_ms()
                print("Calibration done. Collecting",
                      config.COLLECT_SECS, "s...")

            self._win_count = 0
            self._win_min   = (1 << 16) - 1
            self._win_max   = 0
            self._above     = False
            self._cur_max   = 0
            self._prev_peak = 0

    def process(self, raw):
        """
        Process one raw ADC sample.
        Returns True if a valid peak was just confirmed.
        """
        self._sample_count += 1
        smoothed = sma_filter(self._sma_buf, raw)
        self._update_threshold(smoothed)

        if (self._threshold is None or
                self._win_number < config.CALIBRATION_WINS):
            return False

        peak_found = False

        if smoothed > self._threshold:
            self._above = True
            if smoothed > self._cur_max:
                self._cur_max  = smoothed
                self._cur_peak = self._sample_count
        else:
            if self._above:
                if self._prev_peak > 0:
                    n      = self._cur_peak - self._prev_peak
                    ppi_ms = n * config.SAMPLE_INTERVAL

                    # Refractory period: reject peaks too close together
                    # and only accept physiologically valid PPI range
                    if (n >= config.PEAK_REFRACTORY and
                            config.PPI_MIN_MS < ppi_ms < config.PPI_MAX_MS):
                        self.ppi_list.append(ppi_ms)
                        self.bpm   = int(60000 / ppi_ms)
                        peak_found = True
                        print("PPI:", ppi_ms, "ms BPM:", self.bpm,
                              "n:", len(self.ppi_list))

                self._prev_peak = self._cur_peak
                self._above     = False
                self._cur_max   = 0

        return peak_found

    def is_calibrated(self):
        """Return True once calibration windows are complete."""
        return self._win_number >= config.CALIBRATION_WINS

    def elapsed_ms(self):
        """Return ms since collection started. 0 if not started."""
        if self.start_time is None:
            return 0
        return time.ticks_diff(time.ticks_ms(), self.start_time)

    def secs_left(self):
        """Return seconds remaining in collection window."""
        return max(0, config.COLLECT_SECS - self.elapsed_ms() // 1000)

    def collection_done(self):
        """Return True when 30 seconds of data collected."""
        return (self.start_time is not None and
                self.elapsed_ms() >= config.COLLECT_SECS * 1000)

    def draw_y(self, oled_graph_h):
        """
        Return current y pixel for waveform display.
        Returns None if not enough data yet.
        """
        if not self._sma_buf:
            return None
        sig_range = (self._win_max - self._win_min
                     if self._win_max > self._win_min else 1)
        val = self._sma_buf[-1]
        y   = int((1.0 - (val - self._win_min) / sig_range)
                  * (oled_graph_h - 1))
        return max(0, min(oled_graph_h - 1, y))


class HRVAnalyser:
    """
    Calculates HRV metrics from a list of PPI values.
    Returns dict with mean_ppi, mean_hr, sdnn, rmssd.
    """

    def calculate(self, ppi_list):
        """Returns HRV dict or None if not enough data."""
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