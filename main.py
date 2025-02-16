import threading
import time
import serial
import RPi.GPIO as GPIO
import pynmea2
from flask import Flask, jsonify, render_template_string

# Global variables for storing raw data, pin status, and GPS coordinates
raw_data = ""
pin_status = {"GPIO14": None, "GPIO15": None, "GPIO18": None}
gps_data = {"lat": None, "lon": None}  # 解析結果の座標

# Initialize GPIO for AE-GPS connection (pins used per README)
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

# Open serial port (/dev/ttyS0 as per README)
def connect_serial():
    try:
        ser = serial.Serial(
            port='/dev/ttyS0',
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

# Background thread: continuously read raw data, parse NMEA and update global variables
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
                raw_data = decoded_line
                # 例として$GPRMCを解析し、座標を取得
                if decoded_line.startswith("$GPRMC"):
                    try:
                        msg = pynmea2.parse(decoded_line)
                        if msg.latitude and msg.longitude:
                            gps_data["lat"] = msg.latitude
                            gps_data["lon"] = msg.longitude
                    except Exception as parse_err:
                        print(f"NMEA解析エラー: {parse_err}")
                print(f"受信: {raw_data}")
        except Exception as e:
            print(f"読み取りエラー: {e}")
            time.sleep(1)

# Background thread: monitor pin states every 0.5秒 and update global variable
def monitor_pins():
    global pin_status
    while True:
        try:
            pin_status = {
                "GPIO14": GPIO.input(14),
                "GPIO15": GPIO.input(15),
                "GPIO18": GPIO.input(18)
            }
        except Exception as e:
            print(f"ピン読み取りエラー: {e}")
        time.sleep(0.5)

# Flask application
app = Flask(__name__)

@app.route("/status", methods=["GET"])
def get_status():
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
        <title>AE-GPS Real-Time Coordinates</title>
      </head>
      <body>
        <h1>AE-GPS 生データ＆座標情報</h1>
        <div>
          <h2>生データ:</h2>
          <pre id="raw">{{ raw }}</pre>
        </div>
        <div>
          <h2>座標情報:</h2>
          <ul>
            <li>緯度 (lat): <span id="lat">{{ gps.lat }}</span></li>
            <li>経度 (lon): <span id="lon">{{ gps.lon }}</span></li>
          </ul>
        </div>
        <div>
          <h2>ピン状態:</h2>
          <ul>
            <li>GPIO14: <span id="pin14">{{ pins.GPIO14 }}</span></li>
            <li>GPIO15: <span id="pin15">{{ pins.GPIO15 }}</span></li>
            <li>GPIO18: <span id="pin18">{{ pins.GPIO18 }}</span></li>
          </ul>
        </div>
        <script>
          async function fetchStatus() {
            const res = await fetch('/status');
            const data = await res.json();
            document.getElementById('raw').innerText = data.raw;
            document.getElementById('lat').innerText = data.gps.lat || '---';
            document.getElementById('lon').innerText = data.gps.lon || '---';
            document.getElementById('pin14').innerText = data.pins.GPIO14;
            document.getElementById('pin15').innerText = data.pins.GPIO15;
            document.getElementById('pin18').innerText = data.pins.GPIO18;
          }
          setInterval(fetchStatus, 500);
          fetchStatus();
        </script>
      </body>
    </html>
    """, raw=raw_data, pins=pin_status, gps=gps_data)

def cleanup():
    GPIO.cleanup()
    print("GPIOクリーンアップ完了")

if __name__ == "__main__":
    setup_gpio()
    thread_raw = threading.Thread(target=read_raw_data, daemon=True)
    thread_raw.start()
    thread_pins = threading.Thread(target=monitor_pins, daemon=True)
    thread_pins.start()
    try:
        app.run(host="0.0.0.0", port=7777)
    finally:
        cleanup()