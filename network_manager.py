# network_manager.py
# WiFi connection and MQTT communication.
# Kubios request/response flow.

import network
import ubinascii
import time
import json
from umqtt.simple import MQTTClient
import config


class NetworkManager:
    """
    Manages WiFi and MQTT connections.
    Call check_messages() every main loop iteration.
    """

    def __init__(self):
        self._wlan            = network.WLAN(network.STA_IF)
        self._mqtt            = None
        self._connected_wifi  = False
        self._connected_mqtt  = False
        self._kubios_response = None
        self._mac             = None

    def connect_wifi(self, display):
        display.connecting_wifi(config.WIFI_SSID)

        self._wlan.active(True)
        if not self._wlan.isconnected():
            self._wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            start = time.ticks_ms()
            while not self._wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > 10000:
                    display.wifi_failed()
                    print("WiFi failed.")
                    return False
                time.sleep_ms(250)

        mac_bytes            = self._wlan.config("mac")
        self._mac            = ubinascii.hexlify(mac_bytes).decode().upper()
        self._connected_wifi = True
        ip = self._wlan.ifconfig()[0]
        display.wifi_ok(ip)
        print("WiFi connected:", ip, "MAC:", self._mac)
        return True

    def connect_mqtt(self, display):
        display.connecting_mqtt(config.MQTT_BROKER)
        try:
            self._mqtt = MQTTClient(
                client_id = self._mac,
                server    = config.MQTT_BROKER,
                port      = config.MQTT_PORT
            )
            self._mqtt.set_callback(self._on_message)
            self._mqtt.connect()
            self._mqtt.subscribe(config.MQTT_TOPIC_RES)
            self._connected_mqtt = True
            display.mqtt_ok()
            print("MQTT connected.")
            return True
        except Exception as e:
            display.mqtt_failed()
            print("MQTT failed:", e)
            return False

    def _on_message(self, topic, msg):
        if topic != config.MQTT_TOPIC_RES.encode():
            return
        try:
            data = json.loads(msg)
            if data.get("mac") == self._mac:
                self._kubios_response = data
                print("Kubios response received.")
        except Exception as e:
            print("Response parse error:", e)

    def check_messages(self):
        if self._connected_mqtt:
            try:
                self._mqtt.check_msg()
            except Exception as e:
                print("MQTT check error:", e)
                self._connected_mqtt = False

    def publish_kubios(self, ppi_list, patient_num):
        if not self._connected_mqtt:
            print("MQTT not connected.")
            return False
        payload = json.dumps({
            "mac":      self._mac,
            "type":     "RRI",
            "data":     ppi_list,
            "analysis": {"type": "readiness"},
            "patient":  "Patient " + str(patient_num)
        })
        try:
            self._mqtt.publish(config.MQTT_TOPIC_REQ, payload)
            self._kubios_response = None
            print("Kubios request sent:", len(ppi_list),
                  "PPIs for Patient", patient_num)
            return True
        except Exception as e:
            print("Publish failed:", e)
            return False

    def get_kubios_response(self):
        r = self._kubios_response
        self._kubios_response = None
        return r

    def is_connected(self):
        return self._connected_wifi and self._connected_mqtt