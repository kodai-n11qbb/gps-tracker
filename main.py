import threading
import time
import serial
import serial.tools.list_ports
import subprocess
import datetime
import pynmea2
import RPi.GPIO as GPIO
from flask import Flask, render_template_string, jsonify

# GPSTracker クラス: GPIO初期化、1PPS設定、シリアル接続・データ解析、ピン監視を統合
class GPSTracker:
    def __init__(self):
        self.ser = None
        self.current_location = {
            "lat": 40.7128,
            "lon": -74.0060,
            "speed": 0,
            "course": 0,
            "timestamp": "",
            "satellites": 0,
            "pin_status": {
                "tx": False,
                "rx": False,
                "pps": False,
                "raw_data": ""
            }
        }
        self.setup_gpio()
        self.setup_pps()

    def setup_gpio(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            # AE-GPS 接続に合わせたGPIO設定
            # AE-GPSのRX → RPiのTX: GPIO14（UART制御のため入力モード）
            # AE-GPSのTX → RPiのRX: GPIO15（UART制御のため入力モード）
            GPIO.setup(14, GPIO.IN)
            GPIO.setup(15, GPIO.IN)
            # 1PPS入力用: GPIO18
            GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            print("GPIOの初期化が完了しました")
        except Exception as e:
            print(f"GPIOの初期化に失敗: {e}")

    def setup_pps(self):
        try:
            GPIO.add_event_detect(18, GPIO.RISING, callback=self.pps_callback)
            print("1PPS割り込み設定完了")
        except Exception as e:
            print(f"1PPS設定エラー: {e}")

    def pps_callback(self, channel):
        now = datetime.datetime.now()
        self.current_location["timestamp"] = now.strftime("%H:%M:%S")

    def connect_serial(self):
        # READMEでは/dev/ttyS0の使用を確認するためこちらを採用
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(
                port='/dev/ttyS0',  # README記載のシリアルポート
                baudrate=9600,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print("シリアルポート接続成功")
            return True
        except Exception as e:
            print(f"シリアル接続エラー: {e}")
            return False

    def read_gps_data(self):
        while True:
            if not self.ser or not self.ser.is_open:
                if not self.connect_serial():
                    time.sleep(5)
                    continue

            try:
                line = self.ser.readline()
                if not line:
                    continue
                line = line.decode('utf-8').strip()
                self.parse_nmea(line)
            except serial.SerialException as e:
                print(f"シリアル読み取りエラー: {e}")
                self.ser = None
                time.sleep(1)
            except Exception as e:
                print(f"データ処理エラー: {e}")
                time.sleep(0.1)

    def parse_nmea(self, line):
        try:
            if line.startswith('$GPRMC'):
                msg = pynmea2.parse(line)
                if msg.latitude and msg.longitude:
                    self.current_location.update({
                        "lat": msg.latitude,
                        "lon": msg.longitude,
                        "speed": msg.spd_over_grnd if msg.spd_over_grnd else 0,
                        "course": msg.true_course if msg.true_course else 0,
                        "timestamp": msg.timestamp.strftime("%H:%M:%S")
                    })
            elif line.startswith('$GPGGA'):
                msg = pynmea2.parse(line)
                self.current_location["satellites"] = msg.num_sats
        except Exception as e:
            print(f"NMEA解析エラー: {e}")

    def monitor_pins(self):
        while True:
            try:
                # AE-GPSのTXはRPiのRX(GPIO15)、AE-GPSのRXはRPiのTX(GPIO14)
                tx_state = GPIO.input(15)  
                rx_state = GPIO.input(14)  
                pps_state = GPIO.input(18)
                try:
                    raw = subprocess.check_output(
                        ['xxd', '-l', '32', '/dev/ttyS0'],
                        stderr=subprocess.PIPE
                    )
                    raw_hex = raw.decode('utf-8')
                except Exception:
                    raw_hex = "データなし"

                self.current_location["pin_status"].update({
                    "tx": bool(tx_state),
                    "rx": bool(rx_state),
                    "pps": bool(pps_state),
                    "raw_data": raw_hex
                })
                print(f"TX(GPIO15): {'HIGH' if tx_state else 'LOW'}")
                print(f"RX(GPIO14): {'HIGH' if rx_state else 'LOW'}")
                print(f"PPS(GPIO18): {'HIGH' if pps_state else 'LOW'}")
                print(f"Raw data: {raw_hex}")
            except Exception as e:
                print(f"ピンモニタリングエラー: {e}")
            time.sleep(0.5)

    def cleanup(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        GPIO.cleanup()
        print("GPIOおよびシリアルポートのクリーンアップ完了")

# Flaskアプリの作成とGPSTrackerインスタンスの初期化
gps_tracker = GPSTracker()
app = Flask(__name__)

@app.route("/location", methods=["GET"])
def location():
    return jsonify(gps_tracker.current_location)

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <title>GPS Tracker</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
          #map { height: 400px; width: 100%; margin-top: 20px; }
          .data-container { margin: 20px 0; }
          .pin-status { display: inline-block; width: 20px; height: 20px; border-radius: 50%; margin-right: 10px; }
          .pin-active { background-color: #00ff00; }
          .pin-inactive { background-color: #ff0000; }
          .raw-data { font-family: monospace; background: #f0f0f0; padding: 10px; margin: 10px 0; }
        </style>
      </head>
      <body>
        <h1>GPS Tracker</h1>
        <div class="data-container">
          <h2>GPIO ピン状態:</h2>
          <p>TX (GPIO14): <span id="tx-status" class="pin-status pin-inactive"></span> <span id="tx-text">LOW</span></p>
          <p>RX (GPIO15): <span id="rx-status" class="pin-status pin-inactive"></span> <span id="rx-text">LOW</span></p>
          <p>生データ:</p>
          <pre id="raw-data" class="raw-data">待機中...</pre>
        </div>
        <div class="data-container">
          <p>緯度経度: <span id="location"></span></p>
          <p>速度: <span id="speed"></span> ノット</p>
          <p>進行方向: <span id="course"></span>°</p>
          <p>時刻: <span id="timestamp"></span></p>
          <p>衛星数: <span id="satellites"></span></p>
        </div>
        <div id="map"></div>
        <script>
          let map, marker;
          function initMap() {
            map = L.map('map').setView([35.6895, 139.6917], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
              attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);
            marker = L.marker([35.6895, 139.6917]).addTo(map);
          }
          async function updatePinStatus() {
            const res = await fetch('/location');
            const data = await res.json();
            document.getElementById('tx-status').className = 'pin-status ' + (data.pin_status.tx ? 'pin-active' : 'pin-inactive');
            document.getElementById('rx-status').className = 'pin-status ' + (data.pin_status.rx ? 'pin-active' : 'pin-inactive');
            document.getElementById('tx-text').textContent = data.pin_status.tx ? 'HIGH' : 'LOW';
            document.getElementById('rx-text').textContent = data.pin_status.rx ? 'HIGH' : 'LOW';
            document.getElementById('raw-data').textContent = data.pin_status.raw_data;
          }
          async function fetchLocation() {
            const res = await fetch('/location');
            const data = await res.json();
            document.getElementById('location').innerText = `${data.lat}, ${data.lon}`;
            document.getElementById('speed').innerText = data.speed;
            document.getElementById('course').innerText = data.course;
            document.getElementById('timestamp').innerText = data.timestamp;
            document.getElementById('satellites').innerText = data.satellites;
            marker.setLatLng([Number(data.lat), Number(data.lon)]);
            map.setView([Number(data.lat), Number(data.lon)]);
            await updatePinStatus();
          }
          initMap();
          setInterval(fetchLocation, 1000);
          fetchLocation();
        </script>
      </body>
    </html>
    """)

if __name__ == "__main__":
    try:
        gps_thread = threading.Thread(target=gps_tracker.read_gps_data, daemon=True)
        monitor_thread = threading.Thread(target=gps_tracker.monitor_pins, daemon=True)
        gps_thread.start()
        monitor_thread.start()
        app.run(host="0.0.0.0", port=7777)
    finally:
        gps_tracker.cleanup()
