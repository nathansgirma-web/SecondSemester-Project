# config.py
# All hardware pin assignments and system constants.

# --- I2C / OLED ---
I2C_ID  = 1
I2C_SCL = 15
I2C_SDA = 14

# --- Buttons ---
SW0 = 9
SW1 = 8
SW2 = 7

# --- Rotary Encoder ---
ROT_A  = 10
ROT_B  = 11
ROT_SW = 12

# --- LED ---
LED_PIN = 22

# --- ADC ---
ADC_PIN = 26

# --- Sampling ---
SAMPLE_RATE      = 250
SAMPLE_INTERVAL  = 4
FIFO_SIZE        = 512

# --- SMA filter ---
SMA_WINDOW = 5

# --- Threshold ---
THRESHOLD_WINDOW = 500
THRESHOLD_PCT    = 0.65     # raised from 0.65 to filter noise

# --- BPM / PPI limits ---
MIN_BPM    = 30
MAX_BPM    = 240
PPI_MIN_MS = 250
PPI_MAX_MS = 2000

# --- Peak detection ---
PEAK_REFRACTORY = 62        # min samples between peaks (250ms at 250Hz)

# --- HRV collection ---
COLLECT_SECS     = 30
CALIBRATION_WINS = 2

# --- Storage ---
MAX_SESSIONS = 10

# --- WiFi ---
WIFI_SSID     = "KME759_group07"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# --- MQTT ---
MQTT_BROKER    = "192.168.7.253"
MQTT_PORT      = 21883
MQTT_CLIENT_ID = "pico_hrm"
MQTT_TOPIC_REQ = "kubios/request"
MQTT_TOPIC_RES = "kubios/response"