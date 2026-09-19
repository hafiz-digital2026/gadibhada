"""
Gadi Bhada (গাড়ি ভাড়া) - Vehicle Rental Matching App
----------------------------------------------------
Ek simple Flask app jisme:
  1. Gadi wale (drivers) apni gadi register karte hain (naam, gadi type,
     number, contact, location).
  2. Sawari (passenger) apni location se search karta hai aur unhe
     sabse nazdeek ke available gadi wale dikhte hain, contact number ke saath.

Run karne ke liye:
    pip install flask --break-system-packages
    python3 app.py
Phir browser me kholein: http://127.0.0.1:5000
"""

from flask import Flask, request, render_template_string, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import math
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gadibhada-secret-key-change-this")

DB_PATH = os.path.join(os.path.dirname(__file__), "gadibhada.db")

# Agar DATABASE_URL diya gaya hai (jaise Supabase/Render Postgres), to us permanent
# database ka use hoga - isse data kabhi reset nahi hoga. Warna local SQLite file use hogi.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    DB_INTEGRITY_ERRORS = (psycopg2.IntegrityError,)
else:
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


class DBConn:
    """SQLite aur PostgreSQL, dono ke liye ek jaisa interface deta hai -
    conn.execute(query, params).fetchall() / fetchone() sab jagah kaam karega,
    chahe SQLite chal rahi ho ya Supabase/Postgres."""

    def __init__(self):
        if USE_POSTGRES:
            self._conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        else:
            self._conn = sqlite3.connect(DB_PATH)
            self._conn.row_factory = sqlite3.Row

    def execute(self, query, params=()):
        if USE_POSTGRES:
            # SQLite "?" placeholders ko Postgres ke "%s" me badal dete hain
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(query.replace("?", "%s"), params)
            return cur
        return self._conn.execute(query, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)
    return wrapper


# Admin login - set these as environment variables on your server for real use,
# warna yahan diye defaults chalenge (production me isse zaroor badal dein!).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# Yahan seedha apna password likh dein (neeche wali line me "GadiBhada@2026" ki jagah).
# Isse koi extra command (env variable set karna) chalane ki zaroorat nahi padegi.
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "GadiBhada@2026"))


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def get_db():
    return DBConn()


def init_db():
    conn = get_db()
    id_col = "id SERIAL PRIMARY KEY" if USE_POSTGRES else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS drivers (
            {id_col},
            name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            vehicle_number TEXT NOT NULL UNIQUE,
            contact_number TEXT NOT NULL,
            city TEXT NOT NULL,
            village TEXT,
            post_office TEXT,
            police_station TEXT,
            district TEXT,
            pincode TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            is_available INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS bookings (
            {id_col},
            driver_id INTEGER NOT NULL,
            driver_name TEXT NOT NULL,
            driver_contact TEXT NOT NULL,
            passenger_name TEXT NOT NULL,
            passenger_contact TEXT NOT NULL,
            pickup_place TEXT,
            pickup_lat REAL,
            pickup_lon REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS complaints (
            {id_col},
            reporter_type TEXT NOT NULL,
            name TEXT NOT NULL,
            contact_number TEXT NOT NULL,
            related_vehicle_number TEXT,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    # Purani database ho to naye columns add kar dein (migration) - agar pehle se hain to error ignore
    for col in ["village TEXT", "post_office TEXT", "police_station TEXT", "district TEXT", "pincode TEXT"]:
        try:
            if USE_POSTGRES:
                conn.execute(f"ALTER TABLE drivers ADD COLUMN IF NOT EXISTS {col}")
            else:
                conn.execute(f"ALTER TABLE drivers ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
        except DB_INTEGRITY_ERRORS:
            conn.rollback()
    conn.commit()
    conn.close()


init_db()  # App shuru hote hi tables ban jayengi (local run aur gunicorn dono me)


# ---------------------------------------------------------------------------
# Distance calculation (Haversine formula) - "nearest" gadi dhundhne ke liye
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def build_full_address(row):
    """Vill-PO-PS-Dist-PIN format me poora address bana ke deta hai (gramin address style)."""
    parts = []
    if row.get("village"):
        parts.append(f"Vill-{row['village']}")
    if row.get("post_office"):
        parts.append(f"PO-{row['post_office']}")
    if row.get("police_station"):
        parts.append(f"PS-{row['police_station']}")
    if row.get("district"):
        parts.append(f"Dist-{row['district']}")
    elif row.get("city"):
        parts.append(row["city"])
    if row.get("pincode"):
        parts.append(f"PIN-{row['pincode']}")
    return ", ".join(parts) if parts else (row.get("city") or "-")


# ---------------------------------------------------------------------------
# Templates (ek hi file me simplicity ke liye)
# ---------------------------------------------------------------------------
BASE_STYLE = """
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1b5e20">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="apple-touch-icon" href="/icon.png">
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/service-worker.js').catch(function() {});
  });
}
</script>
<style>
  body { font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 0; }
  .nav { background: #1b5e20; padding: 10px 14px; display: flex; flex-wrap: wrap;
         gap: 4px 14px; align-items: center; }
  .nav a { color: #fff; text-decoration: none; font-weight: 600; font-size: 14px;
           padding: 6px 2px; white-space: nowrap; }
  .nav a.admin-link { margin-left: auto; opacity: 0.85; }
  .container { max-width: 560px; margin: 30px auto; background: #fff; padding: 24px 28px;
               border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  h1 { color: #1b5e20; font-size: 22px; }
  label { display: block; margin-top: 14px; font-weight: 600; font-size: 14px; color: #333; }
  input, select { width: 100%; padding: 10px; margin-top: 4px; border: 1px solid #ccc;
                  border-radius: 6px; box-sizing: border-box; font-size: 14px; }
  button { margin-top: 20px; background: #1b5e20; color: #fff; border: none; padding: 12px 20px;
           border-radius: 6px; font-size: 15px; cursor: pointer; width: 100%; }
  button:hover { background: #164018; }
  .flash { background: #e8f5e9; border: 1px solid #66bb6a; padding: 10px 14px; border-radius: 6px;
           margin-bottom: 14px; color: #1b5e20; }
  .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 14px; margin-top: 12px; }
  .card h3 { margin: 0 0 6px 0; color: #1b5e20; }
  .dist { color: #e65100; font-weight: 700; }
  .contact { display: inline-block; margin-top: 8px; background: #2e7d32; color: #fff;
             padding: 8px 14px; border-radius: 6px; text-decoration: none; font-weight: 600; }
  small { color: #777; }
</style>
"""

HOME_HTML = """
<!doctype html><html><head>
<meta name="google-site-verification" content="vhLYAYVANSJWAJ0JE59MCRXufgDeQp-hwPQcIAEMl84" />
<title>Gadi Bhada - Bhada Gadi | Gari Bhara Online Booking</title>
<meta name="description" content="Gadi Bhada - Bhada Gadi, Gari Bhara, Bhara Gari online book karein. Apne area ke sabse nazdeek Auto, Car, Bike, Van, Truck dhundhein aur seedha driver ka contact number payein.">
<meta name="keywords" content="gadi bhada, bhada gadi, gadibhada, bhadagadi, gari bhara, bhara gari, garibhara, bharagari, car rental near me, auto booking, malda gadi bhada">
{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>🚗 Gadi Bhada (Bhada Gadi / Gari Bhara) me Swagat Hai</h1>
  <p>Agar aap gadi wale hain to <a href="{{ url_for('register') }}">yahan register karein</a>.</p>
  <p>Agar aapko gadi chahiye to <a href="{{ url_for('search') }}">yahan search karein</a> aur
     sabse nazdeek ki gadi ka number paayein.</p>
  <p><small>Bhada Gadi, Gadi Bhada, Gari Bhara, Bhara Gari — Auto, Car, Bike, Van, Truck sab
     yahan online book kar sakte hain.</small></p>
</div>
</body></html>
"""

REGISTER_HTML = """
<!doctype html><html><head><title>Gadi Register Karein</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>🚖 Apni Gadi Register Karein</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}
  <form method="POST">
    <label>Aapka Naam</label>
    <input type="text" name="name" required>

    <label>Gadi ka Type</label>
    <select name="vehicle_type" required>
      <option value="Auto">Auto</option>
      <option value="Car">Car</option>
      <option value="Bike">Bike</option>
      <option value="Van">Van / Tempo</option>
      <option value="Truck">Truck</option>
    </select>

    <label>Gadi Number</label>
    <input type="text" name="vehicle_number" placeholder="e.g. WB-06-AB-1234" required>

    <label>Contact Number</label>
    <input type="tel" name="contact_number" placeholder="10 digit mobile number" required>

    <label>Sheher / City (bada shehar/kasba, agar hai)</label>
    <input type="text" name="city" placeholder="e.g. Malda, ya apne nazdeek ka town">

    <label>Vill (Gaon ka Naam)</label>
    <input type="text" name="village" id="village" placeholder="e.g. Ramnagar">

    <label>PO (Post Office)</label>
    <input type="text" name="post_office" id="post_office" placeholder="e.g. Harishchandrapur">

    <label>PS (Police Station)</label>
    <input type="text" name="police_station" id="police_station" placeholder="e.g. Harishchandrapur">

    <label>Dist (District)</label>
    <input type="text" name="district" id="district" placeholder="e.g. Malda" required>

    <label>PIN Code</label>
    <input type="text" name="pincode" id="pincode" placeholder="e.g. 732125" required>

    <button type="button" onclick="geocodeAddress(['village','post_office','district','pincode'],'lat','lon','geostatus')">
      🔍 Is Address se Location Nikaalein</button>
    <small id="geostatus"></small>

    <label>Latitude</label>
    <input type="text" name="latitude" id="lat" placeholder="e.g. 22.5726" required>

    <label>Longitude</label>
    <input type="text" name="longitude" id="lon" placeholder="e.g. 88.3639" required>

    <button type="button" onclick="useMyLocation('lat','lon')">📍 Meri Current Location Bharein</button>
    <button type="submit">Register Karein</button>
  </form>
</div>
<script>
{{ geo_script|safe }}
</script>
</body></html>
"""

SEARCH_HTML = """
<!doctype html><html><head><title>Gadi Dhundhein</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>🔍 Nazdeek ki Gadi Dhundhein</h1>
  <form method="POST">
    <label>Gadi ka Type (optional)</label>
    <select name="vehicle_type">
      <option value="">-- Koi Bhi --</option>
      <option value="Auto">Auto</option>
      <option value="Car">Car</option>
      <option value="Bike">Bike</option>
      <option value="Van">Van / Tempo</option>
      <option value="Truck">Truck</option>
    </select>

    <label>Vill (Gaon ka Naam)</label>
    <input type="text" name="s_village" id="s_village" placeholder="e.g. Ramnagar">

    <label>PO (Post Office)</label>
    <input type="text" name="s_post_office" id="s_post_office" placeholder="e.g. Harishchandrapur">

    <label>PS (Police Station)</label>
    <input type="text" name="s_police_station" id="s_police_station" placeholder="e.g. Harishchandrapur">

    <label>Dist (District)</label>
    <input type="text" name="s_district" id="s_district" placeholder="e.g. Malda">

    <label>PIN Code</label>
    <input type="text" name="s_pincode" id="s_pincode" placeholder="e.g. 732125">

    <button type="button" onclick="geocodeAddress(['s_village','s_post_office','s_district','s_pincode'],'lat','lon','geostatus')">
      🔍 Is Address se Location Nikaalein</button>
    <small id="geostatus"></small>

    <label>Aapki Latitude</label>
    <input type="text" name="latitude" id="lat" required>

    <label>Aapki Longitude</label>
    <input type="text" name="longitude" id="lon" required>

    <button type="button" onclick="useMyLocation('lat','lon')">📍 Meri Current Location Bharein</button>
    <button type="submit">Search Karein</button>
  </form>

  {% if results is not none %}
    <h2 style="margin-top:26px;">Results ({{ results|length }})</h2>
    {% if results|length == 0 %}
      <p>Koi gadi nazdeek me nahi mili. Baad me phir try karein.</p>
    {% endif %}
    {% for r in results %}
      <div class="card">
        <h3>{{ r.vehicle_type }} — {{ r.name }}</h3>
        <p>Gadi Number: {{ r.vehicle_number }}<br>
           Address: {{ r.full_address }}<br>
           Doori: <span class="dist">{{ "%.2f"|format(r.distance) }} km</span></p>
        <a class="contact" href="tel:{{ r.contact_number }}">📞 Call: {{ r.contact_number }}</a>
        <a class="contact" style="background:#e65100;"
           href="{{ url_for('book', driver_id=r.id) }}?place={{ place_query|urlencode }}&lat={{ search_lat }}&lon={{ search_lon }}">
           🚕 Book Karein</a>
      </div>
    {% endfor %}
  {% endif %}
</div>
<script>
{{ geo_script|safe }}
</script>
</body></html>
"""

# Common JS: current-location (GPS) button + place-name/pincode -> lat/lon geocoding
# Uses OpenStreetMap's free Nominatim service (no API key needed).
GEO_SCRIPT = """
function useMyLocation(latId, lonId) {
  if (!navigator.geolocation) { alert("Location supported nahi hai is browser me."); return; }
  navigator.geolocation.getCurrentPosition(function(pos) {
    document.getElementById(latId).value = pos.coords.latitude.toFixed(6);
    document.getElementById(lonId).value = pos.coords.longitude.toFixed(6);
  }, function() { alert("Location nahi mil paayi, please manually bharein."); });
}

async function geocodePlace(placeId, latId, lonId, statusId) {
  var query = document.getElementById(placeId).value.trim();
  var status = document.getElementById(statusId);
  if (!query) { status.textContent = "Pehle jagah ka naam ya pincode likhein."; return; }
  status.textContent = "Dhundh rahe hain...";
  try {
    var url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(query);
    var res = await fetch(url, { headers: { "Accept": "application/json" } });
    var data = await res.json();
    if (data && data.length > 0) {
      document.getElementById(latId).value = parseFloat(data[0].lat).toFixed(6);
      document.getElementById(lonId).value = parseFloat(data[0].lon).toFixed(6);
      status.textContent = "Mil gaya: " + data[0].display_name;
    } else {
      status.textContent = "Ye jagah nahi mili, thoda alag likh ke try karein (jaise sheher/pincode add karein).";
    }
  } catch (e) {
    status.textContent = "Internet/location service me dikkat aa rahi hai, thodi der baad try karein.";
  }
}

// Vill/PO/PS/Dist/PIN jaise rural address fields ko jod ke geocode karta hai.
// fieldIds: un input ids ki list jinko jod ke ek query banani hai (order matters,
// zyada specific pehle - jaise village pehle, phir district, phir pincode).
async function geocodeAddress(fieldIds, latId, lonId, statusId) {
  var parts = [];
  fieldIds.forEach(function(id) {
    var el = document.getElementById(id);
    if (el && el.value.trim()) parts.push(el.value.trim());
  });
  parts.push("India");
  var query = parts.join(", ");
  var status = document.getElementById(statusId);
  if (parts.length <= 1) { status.textContent = "Pehle District aur PIN Code jaise fields bharein."; return; }
  status.textContent = "Dhundh rahe hain: " + query + " ...";
  try {
    var url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(query);
    var res = await fetch(url, { headers: { "Accept": "application/json" } });
    var data = await res.json();
    if (data && data.length > 0) {
      document.getElementById(latId).value = parseFloat(data[0].lat).toFixed(6);
      document.getElementById(lonId).value = parseFloat(data[0].lon).toFixed(6);
      status.textContent = "Mil gaya (kareeb-kareeb): " + data[0].display_name +
        " — agar sahi jagah nahi hai to Latitude/Longitude manually theek kar lein ya "
        + "'Meri Current Location' button use karein.";
    } else {
      status.textContent = "Is address se location nahi mili. PIN Code sahi se likhein, "
        + "ya 'Meri Current Location Bharein' button use karein.";
    }
  } catch (e) {
    status.textContent = "Internet/location service me dikkat aa rahi hai, thodi der baad try karein.";
  }
}
"""

BOOK_HTML = """
<!doctype html><html><head><title>Gadi Book Karein</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  {% if driver %}
    <h1>🚕 Book Karein: {{ driver.vehicle_type }} — {{ driver.name }}</h1>
    <p>Gadi Number: {{ driver.vehicle_number }}<br>Address: {{ driver.full_address }}</p>
    <form method="POST">
      <label>Aapka Naam</label>
      <input type="text" name="passenger_name" required>

      <label>Aapka Contact Number</label>
      <input type="tel" name="passenger_contact" placeholder="10 digit mobile number" required>

      <label>Pickup Jagah</label>
      <input type="text" name="pickup_place" value="{{ place_query }}" placeholder="e.g. Sevoke Road, Siliguri">

      <input type="hidden" name="pickup_lat" value="{{ search_lat }}">
      <input type="hidden" name="pickup_lon" value="{{ search_lon }}">

      <button type="submit">Booking Bhejein</button>
    </form>
  {% else %}
    <h1>⚠️ Gadi nahi mili</h1>
    <p>Ye gadi ab available nahi hai. <a href="{{ url_for('search') }}">Wapas search karein</a>.</p>
  {% endif %}
</div>
</body></html>
"""

BOOKING_CONFIRM_HTML = """
<!doctype html><html><head><title>Booking Bhej Di</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>✅ Booking Request Bhej Di Gayi</h1>
  <p>{{ driver_name }} ({{ driver_contact }}) ko aapki booking request mil gayi hai.
     Wo jaldi hi aapko call karenge. Agar zaroori ho to aap khud bhi
     <a href="tel:{{ driver_contact }}">{{ driver_contact }}</a> pe call kar sakte hain.</p>
  <a href="{{ url_for('search') }}"><button type="button">Wapas Search Pe Jaayein</button></a>
</div>
</body></html>
"""

MY_BOOKINGS_HTML = """
<!doctype html><html><head><title>Meri Bookings</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>📋 Meri Bookings (Driver)</h1>
  <p><small>Apna registered contact number daalein aur dekhein kisne aapki gadi book ki hai.</small></p>
  <form method="POST">
    <label>Aapka Contact Number</label>
    <input type="tel" name="contact_number" value="{{ contact_number or '' }}" placeholder="10 digit mobile number" required>
    <button type="submit">Dekhein</button>
  </form>

  {% if bookings is not none %}
    <h2 style="margin-top:26px;">Bookings ({{ bookings|length }})</h2>
    {% if bookings|length == 0 %}
      <p>Abhi tak koi booking nahi aayi hai.</p>
    {% endif %}
    {% for b in bookings %}
      <div class="card">
        <h3>{{ b.passenger_name }} — <span style="color:#e65100;">{{ b.status|upper }}</span></h3>
        <p>Contact: <a href="tel:{{ b.passenger_contact }}">{{ b.passenger_contact }}</a><br>
           Pickup: {{ b.pickup_place or "Bataya nahi gaya" }}<br>
           Kab: {{ b.created_at }}</p>
        {% if b.status == 'pending' %}
          <form method="POST" action="{{ url_for('update_booking', booking_id=b.id) }}" style="display:inline;">
            <input type="hidden" name="contact_number" value="{{ contact_number }}">
            <input type="hidden" name="action" value="accept">
            <button type="submit" style="width:auto; display:inline-block; margin-right:8px;">✅ Accept</button>
          </form>
          <form method="POST" action="{{ url_for('update_booking', booking_id=b.id) }}" style="display:inline;">
            <input type="hidden" name="contact_number" value="{{ contact_number }}">
            <input type="hidden" name="action" value="reject">
            <button type="submit" style="width:auto; display:inline-block; background:#b71c1c;">❌ Reject</button>
          </form>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}
</div>
</body></html>
"""

HELP_HTML = """
<!doctype html><html><head><title>Help / Shikayat</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('register') }}">Gadi Register Karein</a>
  <a href="{{ url_for('search') }}">Gadi Dhundhein</a>
  <a href="{{ url_for('my_bookings') }}">Meri Bookings</a>
  <a href="{{ url_for('help_page') }}">Help / Shikayat</a>
  <a href="{{ url_for('admin_login') }}" class="admin-link">Admin</a>
</div>
<div class="container">
  <h1>🆘 Help / Shikayat Darj Karein</h1>
  <p><small>Kisi gadi wale se ya passenger se koi dikkat hui ho, ya app me koi problem
     aa rahi ho — yahan bata dein, admin dekh kar aapse sampark karenge.</small></p>
  {% with messages = get_flashed_messages() %}
    {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}
  <form method="POST">
    <label>Aap Kaun Hain?</label>
    <select name="reporter_type" required>
      <option value="Passenger">Passenger (Sawari)</option>
      <option value="Driver">Driver (Gadi Wala)</option>
      <option value="Other">Koi Aur</option>
    </select>

    <label>Aapka Naam</label>
    <input type="text" name="name" required>

    <label>Aapka Mobile Number</label>
    <input type="tel" name="contact_number" placeholder="10 digit mobile number" required>

    <label>Gadi Number (agar kisi gadi se related dikkat hai, optional)</label>
    <input type="text" name="related_vehicle_number" placeholder="e.g. WB66J5583">

    <label>Aapki Dikkat / Shikayat Bataiye</label>
    <textarea name="message" placeholder="Yahan apni poori baat likhein" required
              style="width:100%; height:90px; padding:10px; margin-top:4px; border:1px solid #ccc;
                     border-radius:6px; box-sizing:border-box; font-size:14px; font-family:inherit;"></textarea>

    <button type="submit">Shikayat Bhejein</button>
  </form>
</div>
</body></html>
"""

ADMIN_LOGIN_HTML = """
<!doctype html><html><head><title>Admin Login</title>{{ style|safe }}</head><body>
<div class="nav"><a href="{{ url_for('home') }}">Gadi Bhada</a></div>
<div class="container">
  <h1>🔐 Admin Login</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}{% for m in messages %}<div class="flash" style="background:#fdecea;border-color:#e57373;color:#b71c1c;">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}
  <form method="POST">
    <label>Admin ID</label>
    <input type="text" name="username" autocapitalize="off" autocorrect="off" spellcheck="false" required>
    <label>Password</label>
    <input type="password" name="password" autocapitalize="off" autocorrect="off" spellcheck="false" required>
    <button type="submit">Login</button>
  </form>
</div>
</body></html>
"""

ADMIN_DASHBOARD_HTML = """
<!doctype html><html><head><title>Admin Dashboard</title>{{ style|safe }}
<style>
  table { width:100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #eee; }
  .on { color: #1b5e20; font-weight: 700; }
  .off { color: #b71c1c; font-weight: 700; }
  .togglebtn, .editbtn, .delbtn { width: auto; margin: 0 4px 4px 0; padding: 6px 10px; font-size: 12px; display: inline-block; }
  .editbtn { background: #1565c0; }
  .delbtn { background: #b71c1c; }
</style>
</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('admin_dashboard') }}">Admin Dashboard</a>
  <a href="{{ url_for('admin_logout') }}" class="admin-link">Logout</a>
</div>
<div class="container" style="max-width: 900px;">
  <h1>🛠️ Admin Dashboard</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}

  <h2>Registered Drivers ({{ drivers|length }})</h2>
  <table>
    <tr><th>Naam</th><th>Gadi</th><th>Number</th><th>Contact</th><th>Address</th><th>Status</th><th>Actions</th></tr>
    {% for d in drivers %}
    <tr>
      <td>{{ d.name }}</td>
      <td>{{ d.vehicle_type }}</td>
      <td>{{ d.vehicle_number }}</td>
      <td>{{ d.contact_number }}</td>
      <td>{{ d.full_address }}</td>
      <td>{% if d.is_available %}<span class="on">ON</span>{% else %}<span class="off">OFF</span>{% endif %}</td>
      <td>
        <form method="POST" action="{{ url_for('admin_toggle_driver', driver_id=d.id) }}" style="display:inline;">
          <button type="submit" class="togglebtn">{{ 'Off' if d.is_available else 'On' }}</button>
        </form>
        <a href="{{ url_for('admin_edit_driver', driver_id=d.id) }}" class="editbtn"
           style="color:#fff; text-decoration:none; border-radius:6px; background:#1565c0; padding:6px 10px; font-size:12px;">Edit</a>
        <form method="POST" action="{{ url_for('admin_delete_driver', driver_id=d.id) }}" style="display:inline;"
              onsubmit="return confirm('Pakka is driver ko delete karna hai? Ye wapas nahi hoga.');">
          <button type="submit" class="delbtn">Delete</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>

  <h2 style="margin-top: 26px;">Bookings ({{ bookings|length }})</h2>
  <table>
    <tr><th>Passenger</th><th>Contact</th><th>Driver</th><th>Pickup</th><th>Status</th><th>Kab</th></tr>
    {% for b in bookings %}
    <tr>
      <td>{{ b.passenger_name }}</td>
      <td>{{ b.passenger_contact }}</td>
      <td>{{ b.driver_name }} ({{ b.driver_contact }})</td>
      <td>{{ b.pickup_place or '-' }}</td>
      <td>{{ b.status }}</td>
      <td>{{ b.created_at }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2 style="margin-top: 26px;">🆘 Shikayatein / Complaints ({{ complaints|length }})</h2>
  <table>
    <tr><th>Kaun</th><th>Naam</th><th>Contact</th><th>Gadi Number</th><th>Message</th><th>Status</th><th>Kab</th><th>Action</th></tr>
    {% for cm in complaints %}
    <tr>
      <td>{{ cm.reporter_type }}</td>
      <td>{{ cm.name }}</td>
      <td><a href="tel:{{ cm.contact_number }}">{{ cm.contact_number }}</a></td>
      <td>{{ cm.related_vehicle_number or '-' }}</td>
      <td>{{ cm.message }}</td>
      <td>{% if cm.status == 'open' %}<span class="off">OPEN</span>{% else %}<span class="on">RESOLVED</span>{% endif %}</td>
      <td>{{ cm.created_at }}</td>
      <td>
        {% if cm.status == 'open' %}
        <form method="POST" action="{{ url_for('admin_resolve_complaint', complaint_id=cm.id) }}">
          <button type="submit" class="togglebtn">Resolve Karein</button>
        </form>
        {% else %}
        <small>✅ Ho gaya</small>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</div>
</body></html>
"""

ADMIN_EDIT_DRIVER_HTML = """
<!doctype html><html><head><title>Driver Edit Karein</title>{{ style|safe }}</head><body>
<div class="nav">
  <a href="{{ url_for('home') }}">Gadi Bhada</a>
  <a href="{{ url_for('admin_dashboard') }}">Admin Dashboard</a>
  <a href="{{ url_for('admin_logout') }}" class="admin-link">Logout</a>
</div>
<div class="container">
  <h1>✏️ Driver Details Edit Karein</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}{% for m in messages %}<div class="flash" style="background:#fdecea;border-color:#e57373;color:#b71c1c;">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}
  <form method="POST">
    <label>Naam</label>
    <input type="text" name="name" value="{{ d.name }}" required>

    <label>Gadi ka Type</label>
    <select name="vehicle_type" required>
      {% for vt in ['Auto','Car','Bike','Van','Truck'] %}
        <option value="{{ vt }}" {% if d.vehicle_type == vt %}selected{% endif %}>{{ vt }}</option>
      {% endfor %}
    </select>

    <label>Gadi Number</label>
    <input type="text" name="vehicle_number" value="{{ d.vehicle_number }}" required>

    <label>Contact Number</label>
    <input type="tel" name="contact_number" value="{{ d.contact_number }}" required>

    <label>Sheher / City</label>
    <input type="text" name="city" value="{{ d.city or '' }}">

    <label>Vill (Gaon ka Naam)</label>
    <input type="text" name="village" value="{{ d.village or '' }}">

    <label>PO (Post Office)</label>
    <input type="text" name="post_office" value="{{ d.post_office or '' }}">

    <label>PS (Police Station)</label>
    <input type="text" name="police_station" value="{{ d.police_station or '' }}">

    <label>Dist (District)</label>
    <input type="text" name="district" value="{{ d.district or '' }}" required>

    <label>PIN Code</label>
    <input type="text" name="pincode" value="{{ d.pincode or '' }}" required>

    <label>Latitude</label>
    <input type="text" name="latitude" value="{{ d.latitude }}" required>

    <label>Longitude</label>
    <input type="text" name="longitude" value="{{ d.longitude }}" required>

    <button type="submit">Save Karein</button>
  </form>
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template_string(HOME_HTML, style=BASE_STYLE)


@app.route("/robots.txt")
def robots_txt():
    txt = "User-agent: *\nAllow: /\nSitemap: " + request.url_root.rstrip("/") + "/sitemap.xml\n"
    return app.response_class(txt, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    base = request.url_root.rstrip("/")
    pages = ["/", "/register", "/search", "/help"]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in pages:
        xml += f"  <url><loc>{base}{p}</loc></url>\n"
    xml += "</urlset>"
    return app.response_class(xml, mimetype="application/xml")


@app.route("/manifest.json")
def manifest():
    return {
        "name": "Gadi Bhada",
        "short_name": "GadiBhada",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f4f6f8",
        "theme_color": "#1b5e20",
        "icons": [
            {"src": "/icon.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon.png", "sizes": "512x512", "type": "image/png"},
        ],
    }


@app.route("/service-worker.js")
def service_worker():
    js = """
self.addEventListener('install', function(e) { self.skipWaiting(); });
self.addEventListener('activate', function(e) { self.clients.claim(); });
self.addEventListener('fetch', function(e) {
  // Simple network-first strategy - koi offline caching nahi, hamesha fresh data
  e.respondWith(fetch(e.request).catch(function() {
    return new Response('Aap offline hain. Internet check karein.', { status: 503 });
  }));
});
"""
    return app.response_class(js, mimetype="application/javascript")


@app.route("/icon.png")
def icon():
    # 1x1 halke hare rang ka placeholder PNG - isse apne real logo se badal dein
    import base64
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    return app.response_class(png_bytes, mimetype="image/png")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        vehicle_number = request.form["vehicle_number"].strip().upper().replace(" ", "")
        contact_number = request.form["contact_number"].strip()

        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM drivers WHERE UPPER(REPLACE(vehicle_number,' ','')) = ? OR contact_number = ?",
            (vehicle_number, contact_number),
        ).fetchone()
        if existing:
            conn.close()
            flash("⚠️ Ye gadi number ya contact number pehle se register hai. Dobara register nahi ho sakta.")
            return redirect(url_for("register"))

        district = request.form.get("district", "").strip()
        pincode = request.form.get("pincode", "").strip()
        if not district or not pincode:
            flash("⚠️ District aur PIN Code bharna zaroori hai.")
            return redirect(url_for("register"))

        data = (
            request.form["name"],
            request.form["vehicle_type"],
            request.form["vehicle_number"].strip(),
            contact_number,
            request.form.get("city", "").strip(),
            request.form.get("village", "").strip(),
            request.form.get("post_office", "").strip(),
            request.form.get("police_station", "").strip(),
            district,
            pincode,
            float(request.form["latitude"]),
            float(request.form["longitude"]),
        )
        try:
            conn.execute(
                """INSERT INTO drivers
                   (name, vehicle_type, vehicle_number, contact_number, city,
                    village, post_office, police_station, district, pincode,
                    latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                data,
            )
            conn.commit()
        except DB_INTEGRITY_ERRORS:
            conn.rollback()
            flash("⚠️ Ye gadi number pehle se register hai. Dobara register nahi ho sakta.")
            conn.close()
            return redirect(url_for("register"))
        conn.close()
        flash("Aapki gadi successfully register ho gayi hai! ✅")
        return redirect(url_for("register"))
    return render_template_string(REGISTER_HTML, style=BASE_STYLE, geo_script=GEO_SCRIPT)


@app.route("/search", methods=["GET", "POST"])
def search():
    results = None
    place_query = ""
    search_lat = ""
    search_lon = ""
    if request.method == "POST":
        user_lat = float(request.form["latitude"])
        user_lon = float(request.form["longitude"])
        vehicle_type = request.form.get("vehicle_type", "").strip()
        place_query = ", ".join(
            filter(None, [
                request.form.get("s_village", "").strip(),
                request.form.get("s_post_office", "").strip(),
                request.form.get("s_police_station", "").strip(),
                request.form.get("s_district", "").strip(),
                request.form.get("s_pincode", "").strip(),
            ])
        )
        search_lat = user_lat
        search_lon = user_lon

        conn = get_db()
        if vehicle_type:
            rows = conn.execute(
                "SELECT * FROM drivers WHERE is_available = 1 AND vehicle_type = ?",
                (vehicle_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM drivers WHERE is_available = 1"
            ).fetchall()
        conn.close()

        results = []
        for row in rows:
            d = dict(row)
            d["distance"] = haversine_km(user_lat, user_lon, d["latitude"], d["longitude"])
            d["full_address"] = build_full_address(d)
            results.append(d)

        # Nazdeek se door ka order (nearest first)
        results.sort(key=lambda x: x["distance"])
        results = results[:15]  # top 15 nearest

    return render_template_string(
        SEARCH_HTML,
        style=BASE_STYLE,
        results=results,
        geo_script=GEO_SCRIPT,
        place_query=place_query,
        search_lat=search_lat,
        search_lon=search_lon,
    )


@app.route("/book/<int:driver_id>", methods=["GET", "POST"])
def book(driver_id):
    conn = get_db()
    driver = conn.execute(
        "SELECT * FROM drivers WHERE id = ? AND is_available = 1", (driver_id,)
    ).fetchone()

    if request.method == "POST" and driver:
        conn.execute(
            """INSERT INTO bookings
               (driver_id, driver_name, driver_contact, passenger_name,
                passenger_contact, pickup_place, pickup_lat, pickup_lon)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                driver["id"],
                driver["name"],
                driver["contact_number"],
                request.form["passenger_name"],
                request.form["passenger_contact"],
                request.form.get("pickup_place", ""),
                request.form.get("pickup_lat") or None,
                request.form.get("pickup_lon") or None,
            ),
        )
        conn.commit()
        driver_name = driver["name"]
        driver_contact = driver["contact_number"]
        conn.close()
        return render_template_string(
            BOOKING_CONFIRM_HTML,
            style=BASE_STYLE,
            driver_name=driver_name,
            driver_contact=driver_contact,
        )

    conn.close()
    place_query = request.args.get("place", "")
    search_lat = request.args.get("lat", "")
    search_lon = request.args.get("lon", "")
    driver_dict = None
    if driver:
        driver_dict = dict(driver)
        driver_dict["full_address"] = build_full_address(driver_dict)
    return render_template_string(
        BOOK_HTML,
        style=BASE_STYLE,
        driver=driver_dict,
        place_query=place_query,
        search_lat=search_lat,
        search_lon=search_lon,
    )


@app.route("/my-bookings", methods=["GET", "POST"])
def my_bookings():
    bookings = None
    contact_number = None
    if request.method == "POST":
        contact_number = request.form["contact_number"].strip()
    elif request.args.get("contact_number"):
        contact_number = request.args.get("contact_number").strip()

    if contact_number:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM bookings WHERE driver_contact = ? ORDER BY created_at DESC",
            (contact_number,),
        ).fetchall()
        conn.close()
        bookings = [dict(r) for r in rows]

    return render_template_string(
        MY_BOOKINGS_HTML, style=BASE_STYLE, bookings=bookings, contact_number=contact_number
    )


@app.route("/update-booking/<int:booking_id>", methods=["POST"])
def update_booking(booking_id):
    action = request.form.get("action")
    contact_number = request.form.get("contact_number", "").strip()
    new_status = "accepted" if action == "accept" else "rejected"

    conn = get_db()
    # Sirf woh driver hi status badal sakta hai jiske contact number se booking judi hai
    conn.execute(
        "UPDATE bookings SET status = ? WHERE id = ? AND driver_contact = ?",
        (new_status, booking_id, contact_number),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("my_bookings", contact_number=contact_number))


@app.route("/help", methods=["GET", "POST"])
def help_page():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            """INSERT INTO complaints (reporter_type, name, contact_number, related_vehicle_number, message)
               VALUES (?, ?, ?, ?, ?)""",
            (
                request.form.get("reporter_type", "Other"),
                request.form["name"].strip(),
                request.form["contact_number"].strip(),
                request.form.get("related_vehicle_number", "").strip(),
                request.form["message"].strip(),
            ),
        )
        conn.commit()
        conn.close()
        flash("Aapki shikayat darj ho gayi hai. Admin jald hi aapse sampark karenge. ✅")
        return redirect(url_for("help_page"))
    return render_template_string(HELP_HTML, style=BASE_STYLE)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username.lower() == ADMIN_USERNAME.lower() and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Galat Admin ID ya Password.")
        return redirect(url_for("admin_login"))
    return render_template_string(ADMIN_LOGIN_HTML, style=BASE_STYLE)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    drivers = [dict(r) for r in conn.execute("SELECT * FROM drivers ORDER BY created_at DESC").fetchall()]
    for d in drivers:
        d["full_address"] = build_full_address(d)
    bookings = [dict(r) for r in conn.execute("SELECT * FROM bookings ORDER BY created_at DESC LIMIT 50").fetchall()]
    complaints = [dict(r) for r in conn.execute("SELECT * FROM complaints ORDER BY created_at DESC").fetchall()]
    conn.close()
    return render_template_string(
        ADMIN_DASHBOARD_HTML, style=BASE_STYLE, drivers=drivers, bookings=bookings, complaints=complaints
    )


@app.route("/admin/resolve-complaint/<int:complaint_id>", methods=["POST"])
@admin_required
def admin_resolve_complaint(complaint_id):
    conn = get_db()
    conn.execute("UPDATE complaints SET status = 'resolved' WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/toggle/<int:driver_id>", methods=["POST"])
@admin_required
def admin_toggle_driver(driver_id):
    conn = get_db()
    conn.execute(
        "UPDATE drivers SET is_available = 1 - is_available WHERE id = ?", (driver_id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit/<int:driver_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_driver(driver_id):
    conn = get_db()
    driver = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,)).fetchone()
    if not driver:
        conn.close()
        flash("Ye driver nahi mila.")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        vehicle_number = request.form["vehicle_number"].strip().upper().replace(" ", "")
        contact_number = request.form["contact_number"].strip()

        # Doosre driver ke saath duplicate to nahi ho raha (apne aap ko chhod ke)
        clash = conn.execute(
            """SELECT id FROM drivers
               WHERE (UPPER(REPLACE(vehicle_number,' ','')) = ? OR contact_number = ?)
               AND id != ?""",
            (vehicle_number, contact_number, driver_id),
        ).fetchone()
        if clash:
            conn.close()
            flash("⚠️ Ye gadi number ya contact number kisi doosre driver ke paas pehle se hai.")
            return redirect(url_for("admin_edit_driver", driver_id=driver_id))

        try:
            conn.execute(
                """UPDATE drivers SET
                     name=?, vehicle_type=?, vehicle_number=?, contact_number=?, city=?,
                     village=?, post_office=?, police_station=?, district=?, pincode=?,
                     latitude=?, longitude=?
                   WHERE id=?""",
                (
                    request.form["name"],
                    request.form["vehicle_type"],
                    request.form["vehicle_number"].strip(),
                    contact_number,
                    request.form.get("city", "").strip(),
                    request.form.get("village", "").strip(),
                    request.form.get("post_office", "").strip(),
                    request.form.get("police_station", "").strip(),
                    request.form.get("district", "").strip(),
                    request.form.get("pincode", "").strip(),
                    float(request.form["latitude"]),
                    float(request.form["longitude"]),
                    driver_id,
                ),
            )
            conn.commit()
        except DB_INTEGRITY_ERRORS:
            conn.rollback()
            flash("⚠️ Ye gadi number kisi doosre driver ke paas pehle se hai.")
            conn.close()
            return redirect(url_for("admin_edit_driver", driver_id=driver_id))
        conn.close()
        flash("Driver ki details update ho gayi. ✅")
        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template_string(ADMIN_EDIT_DRIVER_HTML, style=BASE_STYLE, d=driver)


@app.route("/admin/delete/<int:driver_id>", methods=["POST"])
@admin_required
def admin_delete_driver(driver_id):
    conn = get_db()
    conn.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
    conn.commit()
    conn.close()
    flash("Driver delete ho gaya. ✅")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
