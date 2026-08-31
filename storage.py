# storage.py
# Saves and loads HRV sessions and patient number as JSON.

import json
import config

HISTORY_FILE = "hrv_history.json"
PATIENT_FILE = "patient.json"


class Storage:
    """
    Manages persistent HRV session history and current patient number.
    Sessions filterable and deletable per patient or individually.
    """

    def __init__(self):
        self._sessions        = self._load_sessions()
        self._current_patient = self._load_patient()

    def _load_patient(self):
        try:
            with open(PATIENT_FILE, "r") as f:
                return json.load(f).get("patient", 1)
        except:
            return 1

    def _save_patient(self):
        try:
            with open(PATIENT_FILE, "w") as f:
                json.dump({"patient": self._current_patient}, f)
        except Exception as e:
            print("Patient save error:", e)

    def get_patient(self):
        return self._current_patient

    def next_patient(self):
        self._current_patient += 1
        self._save_patient()
        print("Next patient:", self._current_patient)
        return self._current_patient

    def set_patient(self, number):
        self._current_patient = number
        self._save_patient()

    def _load_sessions(self):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []

    def _save_sessions(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self._sessions, f)
        except Exception as e:
            print("Save error:", e)

    def add_session(self, results, ppi_list, patient_num):
        """Add a new HRV session. Drops oldest if over MAX_SESSIONS."""
        number = self._sessions[-1]["session"] + 1 if self._sessions else 1
        self._sessions.append({
            "session":  number,
            "patient":  patient_num,
            "mean_ppi": results["mean_ppi"],
            "mean_hr":  results["mean_hr"],
            "sdnn":     results["sdnn"],
            "rmssd":    results["rmssd"],
            "ppi_list": ppi_list
        })
        if len(self._sessions) > config.MAX_SESSIONS:
            self._sessions = self._sessions[-config.MAX_SESSIONS:]
        self._save_sessions()
        print("Session", number, "saved for Patient", patient_num)

    def get_sessions(self):
        """Return all sessions newest first."""
        return list(reversed(self._sessions))

    def get_sessions_for_patient(self, patient_num):
        """Return sessions for a specific patient newest first."""
        return list(reversed([s for s in self._sessions
                               if s.get("patient") == patient_num]))

    def get_all_patients(self):
        """Return sorted list of unique patient numbers."""
        patients = list(set(s.get("patient", 1)
                            for s in self._sessions))
        patients.sort()
        return patients

    def delete_session(self, session_num):
        """Delete one specific session by session number."""
        self._sessions = [s for s in self._sessions
                          if s.get("session") != session_num]
        self._save_sessions()
        print("Deleted session", session_num)

    def delete_patient(self, patient_num):
        """Delete all sessions for one patient."""
        self._sessions = [s for s in self._sessions
                          if s.get("patient") != patient_num]
        self._save_sessions()
        print("Deleted all sessions for Patient", patient_num)

    def clear_all(self):
        """Delete all sessions and reset patient to 1."""
        self._sessions        = []
        self._current_patient = 1
        self._save_sessions()
        self._save_patient()
        print("All sessions cleared.")

    def count(self):
        return len(self._sessions)