import threading
import time
import serial
import RPi.GPIO as GPIO
from flask import Flask, jsonify, render_template_string

# Global variable for storing raw data
raw_data = ""

# Initialize GPIO for AE-GPS connection (pins used per README)
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # AE-GPSのRX → RPiのTX: GPIO14 (入力 mode since UART is controlled by hardware)
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

# Background thread: continuously read raw data and update global variable
def read_raw_data():
    global raw_data
    ser = connect_serial()
    if not ser:
        return
    while True:
        try:
            line = ser.readline()
            if line:
                raw_data = line.decode('utf-8', errors='replace').strip()
                print(f"受信: {raw_data}")
        except Exception as e:
            print(f"読み取りエラー: {e}")
            time.sleep(1)

# Flask application
app = Flask(__name__)

@app.route("/raw", methods=["GET"])
def get_raw():
    return jsonify({"raw": raw_data})

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <title>AE-GPS Raw Data</title>
      </head>
      <body>
        <h1>AE-GPS 生データ</h1>
        <div id="data">{{ raw }}</div>
        <script>
          async function fetchData() {
            const res = await fetch('/raw');
            const data = await res.json();
            document.getElementById('data').innerText = data.raw;
          }
          setInterval(fetchData, 1000);
          fetchData();
        </script>
      </body>
    </html>
    """, raw=raw_data)

def cleanup():
    GPIO.cleanup()
    print("GPIOクリーンアップ完了")

if __name__ == "__main__":
    setup_gpio()
    # Start background thread for raw data reading
    thread = threading.Thread(target=read_raw_data, daemon=True)
    thread.start()
    try:
        app.run(host="0.0.0.0", port=7777)
    finally:
        cleanup()