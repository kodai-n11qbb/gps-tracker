from flask import Flask, render_template_string, jsonify
import serial
import threading
import time
import pynmea2

app = Flask(__name__)

# グローバル変数として現在位置を保持
current_location = {"lat": 35.6895, "lon": 139.6917}  # デフォルト値

def read_gps():
    global current_location
    ser = serial.Serial(
        port='/dev/ttyS0',  # Raspberry PiのUARTポート
        baudrate=9600,
        timeout=1
    )
    
    while True:
        try:
            line = ser.readline().decode('utf-8')
            if line.startswith('$GPRMC'):
                msg = pynmea2.parse(line)
                if msg.latitude and msg.longitude:
                    current_location = {
                        "lat": msg.latitude,
                        "lon": msg.longitude
                    }
        except:
            pass
        time.sleep(0.1)

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
      </head>
      <body>
        <h1>GPS Tracker</h1>
        <p>現在地: <span id="location"></span></p>
        <script>
          async function fetchLocation() {
            const res = await fetch('/location');
            const data = await res.json();
            document.getElementById('location').innerText = data.lat + ', ' + data.lon;
          }
          setInterval(fetchLocation, 1000);
          fetchLocation();
        </script>
      </body>
    </html>
    """)

@app.route("/location", methods=["GET"])
def location():
    return jsonify(current_location)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7777)
