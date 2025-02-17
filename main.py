import threading
import time
import serial
import RPi.GPIO as GPIO
import pynmea2
from flask import Flask, jsonify, render_template_string
from threading import Lock

# グローバル変数: 生データ, ピン状態, GPS座標
raw_data = ""
pin_status = {"GPIO14": None, "GPIO15": None, "GPIO18": None}
gps_data = {"lat": None, "lon": None}

# 排他制御用Lock
data_lock = Lock()

# GPIO初期化
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # AE-GPSのRX → RPiのTX: GPIO14 (入力 mode)
    # AE-GPSのTX → RPiのRX: GPIO15 (入力 mode)
    GPIO.setup(14, GPIO.IN)
    GPIO.setup(15, GPIO.IN)
    # 1PPS入力用: GPIO18
    GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("GPIOの初期化完了")

# シリアルポート接続
def connect_serial():
    try:
        ser = serial.Serial(
            port='/dev/ttyAMA0',  # Changed from /dev/ttyS0 based on minicom testing
            baudrate=9600,
            timeout=1,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        print("シリアルポート接続成功")
        return ser
    except Exception as e:
        print(f"シリアル接続エラー: {e}")
        return None

# 生データ読み込み、NMEA解析、グローバル変数更新
def read_raw_data():
    global raw_data, gps_data
    ser = connect_serial()
    if not ser:
        return
    while True:
        try:
            line = ser.readline()
            if line:
                decoded_line = line.decode('utf-8', errors='replace').strip()
                with data_lock:
                    raw_data = decoded_line

                # $GPRMC または $GPGGA を解析
                if decoded_line.startswith("$GPRMC"):
                    try:
                        msg = pynmea2.parse(decoded_line)
                        if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                            with data_lock:
                                gps_data["lat"] = msg.latitude
                                gps_data["lon"] = msg.longitude
                    except Exception as parse_err:
                        print(f"NMEA解析エラー (GPRMC): {parse_err}")
                elif decoded_line.startswith("$GPGGA"):
                    try:
                        msg = pynmea2.parse(decoded_line)
                        if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                            with data_lock:
                                gps_data["lat"] = msg.latitude
                                gps_data["lon"] = msg.longitude
                    except Exception as parse_err:
                        print(f"NMEA解析エラー (GPGGA): {parse_err}")

                print(f"受信: {raw_data}")
        except Exception as e:
            print(f"読み取りエラー: {e}")
        time.sleep(1)

# ピン状態監視、グローバル変数更新
def monitor_pins():
    global pin_status
    while True:
        try:
            with data_lock:
                pin_status = {
                    "GPIO14": GPIO.input(14),
                    "GPIO15": GPIO.input(15),
                    "GPIO18": GPIO.input(18)
                }
        except Exception as e:
            print(f"ピン読み取りエラー: {e}")
        time.sleep(0.5)

# Flaskアプリケーション
app = Flask(__name__)

@app.route("/status", methods=["GET"])
def get_status():
    with data_lock:
        return jsonify({
            "raw": raw_data,
            "pins": pin_status,
            "gps": gps_data
        })

@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    
    <title>GPS Status</title>
</head>
<body>
    
        Raw Data: 
        Pins: 
        GPS Data: Lat: {{ gps.lat or '---' }}, Lon: {{ gps.lon or '---' }}
    

    <script>
        setInterval(() => {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                document.getElementById('raw-data').innerText = 'Raw Data: ' + data.raw;
                document.getElementById('pins').innerText = 'Pins: ' + JSON.stringify(data.pins);
                document.getElementById('gps-data').innerText = `GPS Data: Lat: ${data.gps.lat || '---'}, Lon: ${data.gps.lon || '---'}`;
            });
        }, 500);  // 0.5秒間隔
    </script>
</body>
</html>
""", raw=raw_data, pins=pin_status, gps=gps_data)


if __name__ == "__main__":
    setup_gpio()
    raw_data_thread = threading.Thread(target=read_raw_data)
    pin_monitor_thread = threading.Thread(target=monitor_pins)
    raw_data_thread.daemon = True
    pin_monitor_thread.daemon = True
    raw_data_thread.start()
    pin_monitor_thread.start()
    app.run(debug=True, host='0.0.0.0', port=5000)
