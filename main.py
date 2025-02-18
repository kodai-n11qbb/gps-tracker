import threading
import time
import serial
import RPi.GPIO as GPIO
import pynmea2
from flask import Flask, jsonify, render_template_string
from threading import Lock
import atexit

# グローバル変数: 生データ, ピン状態, GPS座標, ループ制御フラグ
raw_data = ""
pin_status = {"GPIO14": None, "GPIO15": None, "GPIO18": None}
gps_data = {"time": None, "lat": None, "lon": None}
running = True  # 追加: 終了制御用グローバルフラグ

# 排他制御用Lock
data_lock = Lock()

# GPIO初期化
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # AE-GPSのRX → RPiのTX: GPIO14 (入力 mode)
    # AE-GPSのTX → RPiのRX: GPIO15 (入力 mode)
    # GPIO.setup(14, GPIO.IN)
    # GPIO.setup(15, GPIO.IN)
    # 1PPS入力用: GPIO18
    GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("GPIOの初期化完了")

# Register GPIO cleanup for program exit
def cleanup():
    print("プログラム終了のためGPIOをクリーンアップします")
    GPIO.cleanup()
atexit.register(cleanup)

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

def read_raw_data():
    global gps_data, raw_data, running
    while running:
        ser = connect_serial()
        if not ser:
            print("シリアル接続に失敗。5秒後に再試行します。")
            time.sleep(5)
            continue
        try:
            while running:
                try:
                    line = ser.readline()
                    if line:
                        decoded_line = line.decode('utf-8', errors='replace').strip()
                        new_gps = {}
                        if decoded_line.startswith("$GPGGA"):
                            try:
                                msg = pynmea2.parse(decoded_line)
                                new_gps = {
                                    "time": str(msg.timestamp),
                                    "lat": float(msg.latitude) if msg.latitude else None,
                                    "lon": float(msg.longitude) if msg.longitude else None
                                }
                            except Exception as parse_err:
                                print(f"NMEA解析エラー (GPGGA): {parse_err}")
                        with data_lock:
                            raw_data = decoded_line
                            if new_gps:
                                gps_data.update(new_gps)
                        print(f"受信: {decoded_line}")
                except Exception as e:
                    print(f"読み取りエラー: {e}")
                time.sleep(1)
        finally:
            ser.close()
            print("シリアルポートをクローズしました")
        # If connection was lost, wait a bit before retrying.
        time.sleep(5)

# Flaskアプリケーション
app = Flask(__name__)

# Update /status to also include raw_data
@app.route("/status", methods=["GET"])
def get_status():
    with data_lock:
        return jsonify({**gps_data, "raw": raw_data})

# Update index route: top section shows text data; bottom section shows the map.
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPS Tracker</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-oA/7RMGGbj6Zy6k9QMIKjJcKtcF2NtFfX0F1h1z4rZU=" 
          crossorigin=""/>
    <style>
      html, body { margin: 0; padding: 0; height: 100%; }
      /* Top info area: 30% of the viewport height */
      #info { padding: 10px; height: 30vh; background: #f0f0f0; }
      /* Map area takes remaining 70% */
      #map { width: 100%; height: 70vh; }
    </style>
  </head>
  <body>
    <div id="info">
      <p>Time: <span id="time">---</span></p>
      <p>Latitude: <span id="lat">---</span></p>
      <p>Longitude: <span id="lon">---</span></p>
      <p>Raw Data: <span id="raw">---</span></p>
    </div>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" 
            integrity="sha256-o9N1jz8bLVLxw6J52dBX4fvZ8d9M2F8sJeDg8C+7uPs=" 
            crossorigin=""></script>
    <script>
      // Default coordinates set to Tokyo Station.
      var defaultLat = 35.681236, defaultLon = 139.767125;
      var map = L.map('map').setView([defaultLat, defaultLon], 15);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '© OpenStreetMap'
      }).addTo(map);
      var marker = L.marker([defaultLat, defaultLon]).addTo(map);
      
      function updateData() {
          fetch('/status')
          .then(response => response.json())
          .then(data => {
              var lat = data.lat || defaultLat;
              var lon = data.lon || defaultLon;
              marker.setLatLng([lat, lon]);
              map.setView([lat, lon]);
              document.getElementById('time').innerText = data.time || '---';
              document.getElementById('lat').innerText = data.lat ? parseFloat(data.lat).toFixed(6) : '---';
              document.getElementById('lon').innerText = data.lon ? parseFloat(data.lon).toFixed(6) : '---';
              document.getElementById('raw').innerText = data.raw || '---';
          });
      }
      updateData();
      setInterval(updateData, 2000);
    </script>
  </body>
</html>
""")

@app.route("/display")
def display():
    with data_lock:
        lat = gps_data.get("lat")
        lon = gps_data.get("lon")
    return render_template_string("""
<html>
  <head>
    <meta charset="UTF-8">
    <title>GPS Display</title>
  </head>
  <body>
    <h1>GPS Data</h1>
    <p>Latitude: {{ lat if lat is not none else '---' }}</p>
    <p>Longitude: {{ lon if lon is not none else '---' }}</p>
  </body>
</html>""", lat=lat, lon=lon)

if __name__ == "__main__":
    setup_gpio()
    # Start the thread for reading raw data
    raw_data_thread = threading.Thread(target=read_raw_data)