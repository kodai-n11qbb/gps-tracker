# gps-tracker
## 概要
移動体(ラジコン等)にGPS機器を取付け、訓練用教材とする

raspberrypiと同じwifi内に接続し、http://172.20.10.4:7777 に接続すると現在地が表示

デバック用で https://172.20.10.4:7777/status でデータ取得ができているか確認可能

AE-GPS 単体だと 30.5m = 100フィート 程の誤差がある [2025/2 時点]

## 使用機器・環境
### ハード
AE-GPS\
raspberrypi zero 2 W

### library / OS
OS : raspberrypi OS legacy 32bit lite\
server : flask\
map : openStreatMap

### 環境
エディタでコードを編集 -> githubで共有 -> RPiでgit pull\
の繰り返し\
rasipberrypi zero 2 W は ssh で制御

## 使用方法
`git clone https://github.com/kodai-n11qbb/gps-tracker.git`\
でダウンロード

`cd gps-tracker`\
`source venv/bin/activate`\
`python main.py`\
で実行

## 注意
### AE-GPSモジュールとRaspberry Pi Zero 2 Wの接続方法
接続方法の手順\
AE-GPSモジュールは3.3Vで動作するため、Raspberry PiのUARTピンと直接接続可能\
必要な接続は4本のピン

VDD (電源)\
GND (グラウンド)\
TXD (送信)\
RXD (受信)

### AE-GPSのRX（AE-GPSの出力ピン） → RPiのTX: GPIO14 (入力 mode)
### AE-GPSのTX（AE-GPSの入力ピン） → RPiのRX: GPIO15 (入力 mode)
### 1PPS入力用: GPIO18
Raspberry Piのシリアルポートを使用するように変更(初回のみ)

セットアップ手順(初回のみ)\
Raspberry PiのUARTを有効化:\
`sudo raspi-config`\
sudo raspi-config\
\# Interfacing Options → Serial → \
\# Would you like a login shell to \be accessible over serial? → No\
\# Would you like the serial port hardware to be enabled? → Yes

### 設定ファイルを編集:(初回のみ)
`sudo nano /boot/config.txt`\
`enable_uart=1`\
`dtoverlay=disable-bt`\
再起動:\
`sudo reboot`\
シリアルポートの権限を設定:\
`sudo usermod -a -G dialout $USER`

### AE-GPS データ確認
`sudo minicom -b 9600 -o -D /dev/ttyAMA0`\
でGPSデータ取得できているか確認

ポートを複数からアクセスする仕様ではないので\
GPSデータ確認コマンド使用後にpythonコードを実行する際は`ctrl + A, x`でポートを開放
