from flask import Flask, render_template_string, jsonify
import serial
import threading
import time
import pynmea2
import RPi.GPIO as GPIO  # 追加

app = Flask(__name__)

# グローバル変数を拡張
current_location = {
    "lat": 35.6895, 
    "lon": 139.6917,
    "speed": 0,
    "course": 0,
    "timestamp": "",
    "satellites": 0
}

# GPIOとUARTの初期化
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # UARTピンの設定
    GPIO.setup(14, GPIO.OUT)  # TX
    GPIO.setup(15, GPIO.IN)   # RX
    print("GPIOの初期化が完了しました")

def read_gps():
    global current_location
    try:
        setup_gpio()  # GPIO初期化
    except Exception as e:
        print(f"GPIOの初期化に失敗: {str(e)}")
        return

    while True:
        try:
            ser = serial.Serial(
                port='/dev/ttyS0',  # Raspberry Pi Zero 2 WのUARTポート
                baudrate=9600,
                timeout=1,
                # UART設定の追加
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print("GPSモジュールに接続しました")
            
            while True:
                try:
                    line = ser.readline().decode('utf-8')
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
                    print("データの読み取りエラー")
                except pynmea2.ParseError:
                    print("NMEAデータの解析エラー")
                except Exception as e:
                    print(f"エラー発生: {str(e)}")
                time.sleep(0.1)
                
        except serial.SerialException:
            print("GPSモジュールに接続できません。5秒後に再試行します...")
            time.sleep(5)
        except Exception as e:
            print(f"予期せぬエラー: {str(e)}")
            time.sleep(5)

# GPSデータ読み取りスレッドの開始
gps_thread = threading.Thread(target=read_gps, daemon=True)
gps_thread.start()

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
        </style>
      </head>
      <body>
        <h1>GPS Tracker</h1>
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
