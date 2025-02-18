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
    global gps_data, running  # raw_data not used anymore for stable data
    ser = connect_serial()
    if not ser:
        return
    try:
        while running:
            try:
                line = ser.readline()
                if line:
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    # Parse $GPGGA for time, latitude, longitude
                    if decoded_line.startswith("$GPGGA"):
                        try:
                            msg = pynmea2.parse(decoded_line)
                            with data_lock:
                                gps_data["time"] = str(msg.timestamp)
                                gps_data["lat"] = float(msg.latitude) if msg.latitude else None
                                gps_data["lon"] = float(msg.longitude) if msg.longitude else None
                        except Exception as parse_err:
                            print(f"NMEA解析エラー (GPGGA): {parse_err}")
                    print(f"受信: {decoded_line}")
            except Exception as e:
                print(f"読み取りエラー: {e}")
            time.sleep(1)
    finally:
        ser.close()
        print("シリアルポートをクローズしました")

# Flaskアプリケーション
app = Flask(__name__)

@app.route("/status", methods=["GET"])
def get_status():
    with data_lock:
        return jsonify(gps_data)

@app.route("/")
def index():
    with data_lock:
        gps = gps_data.copy()
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>GPS Data</title>
</head>
<body>
  <h1>GPS Data</h1>
  <p>Time: {{ gps.time or '---' }}</p>
  <p>Latitude: {{ ('%.6f' % gps.lat) if gps.lat is not none else '---' }}</p>
  <p>Longitude: {{ ('%.6f' % gps.lon) if gps.lon is not none else '---' }}</p>
  <script>
    setInterval(() => {
      fetch('/status')
      .then(response => response.json())
      .then(data => {
        document.querySelector('p:nth-of-type(1)').innerText = 'Time: ' + (data.time || '---');
        document.querySelector('p:nth-of-type(2)').innerText = 'Latitude: ' + (data.lat ? parseFloat(data.lat).toFixed(6) : '---');
        document.querySelector('p:nth-of-type(3)').innerText = 'Longitude: ' + (data.lon ? parseFloat(data.lon).toFixed(6) : '---');
      });
    }, 500);
  </script>
</body>
</html>
""", gps=gps)

if __name__ == "__main__":
    setup_gpio()
    # Start the thread for reading raw data
    raw_data_thread = threading.Thread(target=read_raw_data)
    # Start the thread for GPIO pin monitoring (if needed)
    pin_monitor_thread = threading.Thread(target=lambda: None)  # ...existing get pin status code...
    raw_data_thread.daemon = True
    pin_monitor_thread.daemon = True
    raw_data_thread.start()
    pin_monitor_thread.start()
    try:
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)  # 修正: use_reloader=False を追加
    except KeyboardInterrupt:
        print("KeyboardInterrupt を検知しました。終了処理を実行します。")
    finally:
        running = False
        print("アプリケーションを終了します。")

