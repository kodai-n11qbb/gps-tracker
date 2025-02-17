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

                # "$GPGLL" contains latitude and longitude
                if decoded_line.startswith("$GPGLL"):
                    try:
                        msg = pynmea2.parse(decoded_line)
                        with data_lock:
                            gps_data["lat"] = float(msg.latitude)
                            gps_data["lon"] = float(msg.longitude)
                    except Exception as parse_err:
                        print(f"NMEA解析エラー (GPGLL): {parse_err}")
                # Other sentences ($GPGSA, $GPGSV, $GPVTG, $GPZDA) are received without lat/lon update

                print(f"受信: {raw_data}")
        except Exception as e:
            print(f"読み取りエラー: {e}")
        time.sleep(1)

