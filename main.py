from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Dummy current location data (to be replaced with real sensor input)
current_location = {"lat": 35.6895, "lon": 139.6917}  # Example coordinates

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
