from flask import Flask, render_template_string, jsonify
import serial
import threading
import time
import pynmea2
import RPi.GPIO as GPIO  # 追加
import serial.tools.list_ports  # 追加
import subprocess

app = Flask(__name__)

# グローバル変数を拡張
current_location = {
    "lat": 40.7128,  # New York City latitude
    "lon": -74.0060,  # New York City longitude
    "speed": 0,
    "course": 0,
    "timestamp": "",
    "satellites": 0,
    "pin_status": {
        "tx": False,
        "rx": False,
        "raw_data": ""
    }
}

# GPIOとUARTの初期化
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # UARTピンの設定
    GPIO.setup(14, GPIO.OUT)  # TX
    GPIO.setup(15, GPIO.IN)   # RX
    print("GPIOの初期化が完了しました")

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    print("利用可能なシリアルポート:")
    for port in ports:
        print(f"- {port.device}")

def read_gps():
    global current_location
    
    try:
        setup_gpio()  # GPIO初期化を再有効化
    except Exception as e:
        print(f"GPIOの初期化に失敗: {str(e)}")
        print("GPIO初期化エラーを無視して続行します")
    
    while True:
        try:
            print("シリアルポートに接続を試みます...")
            ser = serial.Serial(
                port='/dev/ttyAMA0',  # ttyS0からttyAMA0に変更
                baudrate=9600,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            print("シリアルポートに接続成功")
            
            while True:
                try:
                    line = ser.readline()
                    if line:
                        print(f"受信データ: {line}")  # デバッグ用
                        line = line.decode('utf-8').strip()
                        if line.startswith('$GPRMC'):
                            msg = pynmea2.parse(line)
                            if msg.latitude and msg.longitude:
                                current_location.update({
                                    "lat": msg.latitude,
                                    "lon": msg.longitude,
                                    "speed": msg.spd_over_grnd if msg.spd_over_grnd else 0,
                                    "course": msg.true_course if msg.true_course else 0,
                                    "timestamp": msg.timestamp.strftime("%H:%M:%S")
                                })
                        elif line.startswith('$GPGGA'):
                            msg = pynmea2.parse(line)
                            current_location["satellites"] = msg.num_sats
                except UnicodeDecodeError:
                    print(f"デコードエラー: {line}")
                except Exception as e:
                    print(f"データ処理エラー: {str(e)}")
                time.sleep(0.1)
                
        except serial.SerialException as e:
            print(f"シリアル接続エラー: {str(e)}")
            time.sleep(5)
        except Exception as e:
            print(f"予期せぬエラー: {str(e)}")
            time.sleep(5)
        finally:
            try:
                ser.close()
            except:
                pass

def monitor_pins():
    global current_location
    while True:
        try:
            # TX(GPIO14)とRX(GPIO15)の状態を読み取り
            tx_state = GPIO.input(14)
            rx_state = GPIO.input(15)
            
            # シリアルデータの直接読み取り（デバッグ用）
            try:
                raw = subprocess.check_output(['xxd', '-l', '32', '/dev/ttyAMA0'], 
                                           stderr=subprocess.PIPE)
                raw_hex = raw.decode('utf-8')
            except:
                raw_hex = "データなし"

            current_location["pin_status"].update({
                "tx": bool(tx_state),
                "rx": bool(rx_state),
                "raw_data": raw_hex
            })
            
            print(f"TX(GPIO14): {'HIGH' if tx_state else 'LOW'}")
            print(f"RX(GPIO15): {'HIGH' if rx_state else 'LOW'}")
            print(f"Raw data: {raw_hex}")
            
        except Exception as e:
            print(f"ピンモニタリングエラー: {str(e)}")
        time.sleep(0.1)

# GPSデータ読み取りスレッドの開始
gps_thread = threading.Thread(target=read_gps, daemon=True)
gps_thread.start()

# ピンモニタリングスレッドの開始
monitor_thread = threading.Thread(target=monitor_pins, daemon=True)
monitor_thread.start()

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <title>GPS Tracker</title>
        <script src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY"></script>
        <style>
          #map { height: 400px; width: 100%; margin-top: 20px; }
          .data-container { margin: 20px 0; }
          .pin-status { 
            display: inline-block; 
            width: 20px; 
            height: 20px; 
            border-radius: 50%;
            margin-right: 10px;
          }
          .pin-active { background-color: #00ff00; }
          .pin-inactive { background-color: #ff0000; }
          .raw-data { 
            font-family: monospace; 
            background: #f0f0f0; 
            padding: 10px; 
            margin: 10px 0;
          }
        </style>
      </head>
      <body>
        <h1>GPS Tracker</h1>
        
        <!-- ピン状態の表示 -->
        <div class="data-container">
          <h2>GPIO ピン状態:</h2>
          <p>
            TX (GPIO14): 
            <span id="tx-status" class="pin-status pin-inactive"></span>
            <span id="tx-text">LOW</span>
          </p>
          <p>
            RX (GPIO15): 
            <span id="rx-status" class="pin-status pin-inactive"></span>
            <span id="rx-text">LOW</span>
          </p>
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
          let map;
          let marker;
          
          function initMap() {
            map = new google.maps.Map(document.getElementById('map'), {
              zoom: 15,
              center: { lat: 35.6895, lng: 139.6917 }
            });
            marker = new google.maps.Marker({
              position: { lat: 35.6895, lng: 139.6917 },
              map: map
            });
          }

          async function updatePinStatus() {
            const res = await fetch('/location');
            const data = await res.json();
            
            // ピン状態の更新
            const txStatus = document.getElementById('tx-status');
            const rxStatus = document.getElementById('rx-status');
            const txText = document.getElementById('tx-text');
            const rxText = document.getElementById('rx-text');
            const rawData = document.getElementById('raw-data');
            
            txStatus.className = 'pin-status ' + (data.pin_status.tx ? 'pin-active' : 'pin-inactive');
            rxStatus.className = 'pin-status ' + (data.pin_status.rx ? 'pin-active' : 'pin-inactive');
            txText.textContent = data.pin_status.tx ? 'HIGH' : 'LOW';
            rxText.textContent = data.pin_status.rx ? 'HIGH' : 'LOW';
            rawData.textContent = data.pin_status.raw_data;
          }

          async function fetchLocation() {
            const res = await fetch('/location');
            const data = await res.json();
            
            // データ表示の更新
            document.getElementById('location').innerText = `${data.lat}, ${data.lon}`;
            document.getElementById('speed').innerText = data.speed;
            document.getElementById('course').innerText = data.course;
            document.getElementById('timestamp').innerText = data.timestamp;
            document.getElementById('satellites').innerText = data.satellites;
            
            // 地図の更新
            const newPosition = { lat: Number(data.lat), lng: Number(data.lon) };
            marker.setPosition(newPosition);
            map.setCenter(newPosition);

            await updatePinStatus();
          }

          initMap();
          setInterval(fetchLocation, 1000);
          fetchLocation();
        </script>
      </body>
    </html>
    """)

@app.route("/location", methods=["GET"])
def location():
    return jsonify(current_location)

# クリーンアップ処理の追加
def cleanup():
    GPIO.cleanup()
    print("GPIOをクリーンアップしました")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=7777)
    finally:
        cleanup()
