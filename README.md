# gps-tracker
## 概要
移動体(ラジコン等)にGPS機器を取付け、訓練用教材とする

raspberrypiと同じwifi内に接続し、localhost:7777 に接続すると現在地が表示される

だけ

## 使用機器・環境
AE-GPS\
raspberrypi zero 2 W\
raspberrypi OS legacy 32bit

## 使用方法
`git clone https://github.com/kodai-n11qbb/gps-tracker.git`\
でダウンロード


## AIによる注意
AE-GPSモジュールとRaspberry Pi Zero 2 Wの接続方法を説明します。

接続方法の手順\
AE-GPSモジュールは3.3Vで動作するため、Raspberry PiのUARTピンと直接接続できます。\
必要な接続は4本のピンです：\
VDD (電源)\
GND (グラウンド)\
TXD (送信)\
RXD (受信)\
main.py\
Raspberry Piのシリアルポートを使用するように変更します。

main.py+1-1\
物理的な接続図\
AE-GPS → Raspberry Pi Zero 2 W の接続：

セットアップ手順\
Raspberry PiのUARTを有効化:\
`sudo raspi-config`\
sudo raspi-config\
\# Interfacing Options → Serial → \
\# Would you like a login shell to \be accessible over serial? → No\
\# Would you like the serial port hardware to be enabled? → Yes

設定ファイルを編集:\
`sudo nano /boot/config.txt
enable_uart=1
dtoverlay=disable-bt`\
再起動:\
`sudo reboot`\
シリアルポートの権限を設定:\
`sudo usermod -a -G dialout $USER`\
これで、AE-GPSモジュールからのデータを受信できるようになります。シリアルポートのパスが/dev/ttyS0になっていることを確認してください。