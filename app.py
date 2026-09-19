import os
import math
import sqlite3
import requests
from functools import wraps
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# App & Database Setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gadi_bhada_super_secret_key_123")

# Updated Admin Credentials (Password: Gadibhada@2026)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "Gadibhada@2026")
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    DB_INTEGRITY_ERRORS = (psycopg2.IntegrityError,)
else:
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def get_db():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect("gadi_bhada.db")
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS drivers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                vehicle_type VARCHAR(50) NOT NULL,
                vehicle_number VARCHAR(50) UNIQUE NOT NULL,
                contact_number VARCHAR(15) NOT NULL,
                city VARCHAR(100),
                village VARCHAR(100),
                post_office VARCHAR(100),
                police_station VARCHAR(100),
                district VARCHAR(100),
                pincode VARCHAR(20),
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                is_available INT DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                driver_id INT REFERENCES drivers(id) ON DELETE CASCADE,
                driver_name VARCHAR(100),
                driver_contact VARCHAR(15),
                passenger_name VARCHAR(100) NOT NULL,
                passenger_contact VARCHAR(15) NOT NULL,
                pickup_place TEXT,
                pickup_lat DOUBLE PRECISION,
                pickup_lon DOUBLE PRECISION,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id SERIAL PRIMARY KEY,
                reporter_type VARCHAR(20),
                name VARCHAR(100),
                contact_number VARCHAR(15),
                related_vehicle_number VARCHAR(50),
                message TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        conn.commit()
        cur.close()
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                vehicle_number TEXT UNIQUE NOT NULL,
                contact_number TEXT NOT NULL,
                city TEXT,
                village TEXT,
                post_office TEXT,
                police_station TEXT,
                district TEXT,
                pincode TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                is_available INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_id INTEGER,
                driver_name TEXT,
                driver_contact TEXT,
                passenger_name TEXT NOT NULL,
                passenger_contact TEXT NOT NULL,
                pickup_place TEXT,
                pickup_lat REAL,
                pickup_lon REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (driver_id) REFERENCES drivers (id) ON DELETE CASCADE
            );
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_type TEXT,
                name TEXT,
                contact_number TEXT,
                related_vehicle_number TEXT,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        conn.commit()
    conn.close()


with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Database Initialization Error: {e}")

# ---------------------------------------------------------------------------
# Multi-Language Translation System (English & Bengali)
# ---------------------------------------------------------------------------
TRANSLATIONS = {
    'en': {
        'app_title': 'Gadi Bhada',
        'sub_title': 'Easily find vehicles or list your vehicle for rent in your area',
        'nav_home': 'Home',
        'nav_search': 'Find Vehicle',
        'nav_register': 'Register Vehicle',
        'nav_bookings': 'My Bookings',
        'nav_help': 'Help & Support',
        'nav_admin': 'Admin Login',
        'welcome_msg': 'Welcome to Gadi Bhada App!',
        'welcome_sub': 'Rent vehicles easily or list your vehicle for rental services.',
        'btn_search': 'Find Vehicle (Search)',
        'btn_register': 'Register Vehicle',
        'reg_header': 'Vehicle Registration',
        'driver_name': 'Driver/Owner Name',
        'vehicle_type': 'Vehicle Type',
        'vehicle_number': 'Vehicle Number',
        'mobile_number': 'Mobile Number',
        'city': 'City / Town',
        'village': 'Village',
        'post_office': 'Post Office',
        'police_station': 'Police Station',
        'district': 'District',
        'pincode': 'PIN Code',
        'use_gps': 'Use Current GPS Location',
        'use_address': 'Get Lat/Lon from Address',
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'btn_submit_reg': 'Register Now',
        'search_header': 'Find Vehicle (Search)',
        'all_vehicles': 'All Vehicles',
        'btn_search_now': 'Search Vehicles',
        'found_vehicles': 'Available Vehicles:',
        'no_vehicles': 'No vehicles found in this location.',
        'distance': 'Distance',
        'btn_book': 'Book Now',
        'book_header': 'Confirm Booking',
        'passenger_name': 'Passenger Name',
        'pickup_address': 'Pickup Location Address',
        'btn_confirm_booking': 'Confirm Booking',
        'booking_success': 'Booking Request Sent Successfully!',
        'booking_success_msg': 'Your booking request has been submitted.',
        'driver_contact': 'Driver Contact Number:',
        'call_driver_note': 'You can contact the driver directly via phone.',
        'my_bookings_header': 'Driver Booking Requests',
        'enter_driver_mobile': 'Enter Registered Driver Mobile Number',
        'view_bookings': 'View Bookings',
        'accept': 'Accept',
        'reject': 'Reject',
        'no_requests': 'No pending booking requests.',
        'help_header': 'Help & Complaint Support',
        'who_are_you': 'Are you a Passenger or Driver?',
        'your_complaint': 'Your Complaint / Message',
        'btn_submit_complaint': 'Submit Complaint',
        'admin_panel_login': 'Admin Panel Login',
        'username': 'Username',
        'password': 'Password',
        'btn_login': 'Login',
        'admin_dashboard': 'Admin Dashboard',
        'logout': 'Logout',
        'registered_drivers': 'Registered Drivers',
        'complaints_header': 'Complaints',
        'th_id': 'ID',
        'th_name': 'Name',
        'th_type': 'Type',
        'th_number': 'Number',
        'th_contact': 'Contact',
        'th_address': 'Address',
        'th_status': 'Status',
        'th_actions': 'Actions',
        'active': 'Active',
        'disabled': 'Disabled',
        'toggle': 'Toggle',
        'edit': 'Edit',
        'delete': 'Delete',
        'th_gadi_no': 'Vehicle No',
        'th_message': 'Message',
        'th_action': 'Action',
        'resolve': 'Resolve',
    },
    'bn': {
        'app_title': 'গাড়ি ভাড়া',
        'sub_title': 'আপনার এলাকায় সহজে গাড়ি খুঁজুন এবং গাড়ি রেজিস্ট্রেশন করুন',
        'nav_home': 'হোম',
        'nav_search': 'গাড়ি খুঁজুন',
        'nav_register': 'গাড়ি রেজিস্ট্রেশন',
        'nav_bookings': 'আমার বুকিং',
        'nav_help': 'সাহায্য ও সাপোর্ট',
        'nav_admin': 'এডমিন লগইন',
        'welcome_msg': 'গাড়ি ভাড়া অ্যাপে আপনাকে স্বাগতম!',
        'welcome_sub': 'সহজে গাড়ি ভাড়া নিন অথবা আপনার গাড়ি ভাড়া দেওয়ার জন্য নথিভুক্ত করুন।',
        'btn_search': 'গাড়ি খুঁজুন (সার্চ)',
        'btn_register': 'গাড়ি রেজিস্ট্রেশন করুন',
        'reg_header': 'গাড়ি রেজিস্ট্রেশন ফর্ম',
        'driver_name': 'চালক/মালিকের নাম',
        'vehicle_type': 'গাড়ির ধরণ',
        'vehicle_number': 'গাড়ির নম্বর',
        'mobile_number': 'মোবাইল নম্বর',
        'city': 'শহর / শহর এলাকা',
        'village': 'গ্রাম',
        'post_office': 'পোস্ট অফিস',
        'police_station': 'থানা',
        'district': 'জেলা',
        'pincode': 'পিন কোড',
        'use_gps': 'বর্তমান GPS লোকেশন ব্যবহার করুন',
        'use_address': 'ঠিকানা থেকে লোকেশন বের করুন',
        'latitude': 'অক্ষাংশ (Latitude)',
        'longitude': 'দ্রাঘিমাংশ (Longitude)',
        'btn_submit_reg': 'রেজিস্ট্রেশন সম্পূর্ণ করুন',
        'search_header': 'গাড়ি খুঁজুন',
        'all_vehicles': 'সব ধরনের গাড়ি',
        'btn_search_now': 'গাড়ি খুঁজুন',
        'found_vehicles': 'উপলব্ধ গাড়ি সমূহ:',
        'no_vehicles': 'এই লোকেশনে কোনো গাড়ি পাওয়া যায়নি।',
        'distance': 'দূরত্ব',
        'btn_book': 'বুক করুন',
        'book_header': 'বুকিং নিশ্চিতকরণ',
        'passenger_name': 'যাত্রীর নাম',
        'pickup_address': 'পিকআপ লোকেশনের ঠিকানা',
        'btn_confirm_booking': 'বুকিং কনফার্ম করুন',
        'booking_success': 'বুকিং রিকোয়েস্ট সফল হয়েছে!',
        'booking_success_msg': 'আপনার বুকিং রিকোয়েস্ট চালকের কাছে পাঠানো হয়েছে।',
        'driver_contact': 'চালকের মোবাইল নম্বর:',
        'call_driver_note': 'আপনি সরাসরি চালকের সাথে কথা বলতে পারেন।',
        'my_bookings_header': 'চালক বুকিং রিকোয়েস্ট',
        'enter_driver_mobile': 'রেজিস্টার্ড চালকের মোবাইল নম্বর দিন',
        'view_bookings': 'বুকিং দেখুন',
        'accept': 'গ্রহণ করুন (Accept)',
        'reject': 'বাতিল করুন (Reject)',
        'no_requests': 'কোনো বুকিং রিকোয়েস্ট নেই।',
        'help_header': 'সাহায্য ও অভিযোগ সাপোর্ট',
        'who_are_you': 'আপনি কি যাত্রী নাকি চালক?',
        'your_complaint': 'আপনার অভিযোগ / বার্তা',
        'btn_submit_complaint': 'অভিযোগ জমা দিন',
        'admin_panel_login': 'এডমিন প্যানেল লগইন',
        'username': 'ইউজারনেম',
        'password': 'পাসওয়ার্ড',
        'btn_login': 'লগইন',
        'admin_dashboard': 'এডমিন ড্যাশবোর্ড',
        'logout': 'লগআউট',
        'registered_drivers': 'নিবন্ধিত চালকগণ',
        'complaints_header': 'অভিযোগসমূহ',
        'th_id': 'আইডি',
        'th_name': 'নাম',
        'th_type': 'ধরণ',
        'th_number': 'নম্বর',
        'th_contact': 'যোগাযোগ',
        'th_address': 'ঠিকানা',
        'th_status': 'অবস্থা',
        'th_actions': 'কার্যক্রম',
        'active': 'সক্রিয়',
        'disabled': 'নিষ্ক্রিয়',
        'toggle': 'টগল',
        'edit': 'সম্পাদনা',
        'delete': 'মুছুন',
        'th_gadi_no': 'গাড়ির নম্বর',
        'th_message': 'বার্তা',
        'th_action': 'কার্যক্রম',
        'resolve': 'সমাধান',
    }
}

@app.route('/set_lang/<lang_code>')
def set_lang(lang_code):
    if lang_code in ['en', 'bn']:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('home'))

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'bn')  # Default language is Bengali
    def t(key):
        return TRANSLATIONS.get(lang, TRANSLATIONS['bn']).get(key, key)
    return dict(t=t, current_lang=lang)

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def build_full_address(driver):
    parts = []
    if driver.get("village"):
        parts.append(f"Vill: {driver['village']}")
    if driver.get("post_office"):
        parts.append(f"PO: {driver['post_office']}")
    if driver.get("police_station"):
        parts.append(f"PS: {driver['police_station']}")
    if driver.get("district"):
        parts.append(f"Dist: {driver['district']}")
    if driver.get("pincode"):
        parts.append(f"PIN: {driver['pincode']}")
    if driver.get("city"):
        parts.append(driver["city"])
    return ", ".join(parts) if parts else "Address details not available"


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin Login dorkar.")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated_function


# ---------------------------------------------------------------------------
# UI Styles & Client Scripts
# ---------------------------------------------------------------------------
BASE_STYLE = """
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    body { background-color: #f4f6f9; color: #333; line-height: 1.6; padding-bottom: 60px; }
    header { background: #1e3c72; background: linear-gradient(to right, #2a5298, #1e3c72); color: #fff; padding: 15px 20px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    header h1 { font-size: 24px; margin-bottom: 5px; }
    nav { background: #0f2027; display: flex; justify-content: center; align-items: center; flex-wrap: wrap; padding: 5px 10px; }
    nav a { color: #fff; text-decoration: none; padding: 12px 18px; font-size: 14px; font-weight: 500; transition: background 0.3s; }
    nav a:hover { background: #203a43; }
    .lang-switcher { margin-left: auto; padding: 5px 15px; }
    .lang-btn { color: #fff; text-decoration: none; padding: 5px 10px; border-radius: 4px; font-weight: bold; border: 1px solid #ffffff55; }
    .lang-btn.active { background: #28a745; border-color: #28a745; }
    .container { max-width: 800px; margin: 20px auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .btn { display: inline-block; background: #28a745; color: white; border: none; padding: 10px 18px; border-radius: 5px; cursor: pointer; text-decoration: none; font-size: 15px; font-weight: bold; margin-top: 10px; }
    .btn:hover { background: #218838; }
    .btn-danger { background: #dc3545; }
    .btn-danger:hover { background: #c82333; }
    .btn-primary { background: #007bff; }
    .btn-primary:hover { background: #0069d9; }
    .btn-secondary { background: #6c757d; }
    .btn-secondary:hover { background: #5a6268; }
    .form-group { margin-bottom: 15px; }
    label { display: block; font-weight: bold; margin-bottom: 5px; }
    input[type="text"], input[type="tel"], input[type="password"], select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
    .flash { background: #d4edda; color: #155724; padding: 10px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #c3e6cb; }
    .card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin-bottom: 15px; background: #fafafa; }
    .card-title { font-size: 18px; font-weight: bold; color: #1e3c72; }
    .badge { display: inline-block; padding: 3px 8px; font-size: 12px; border-radius: 3px; color: white; }
    .bg-success { background: #28a745; }
    .bg-warning { background: #ffc107; color: #333; }
    .bg-danger { background: #dc3545; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
    table, th, td { border: 1px solid #ddd; }
    th, td { padding: 10px; text-align: left; }
    th { background: #f1f1f1; }
</style>
"""

GEO_SCRIPT = """
<script>
function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(showPosition, showError);
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}
function showPosition(position) {
    document.getElementById("latitude").value = position.coords.latitude;
    document.getElementById("longitude").value = position.coords.longitude;
    var status = document.getElementById("geo-status");
    if(status) status.innerHTML = "Location retrieved successfully!";
}
function showError(error) {
    alert("Location error: " + error.message);
}
function geocodeAddress() {
    var vill = document.getElementById("village") ? document.getElementById("village").value : "";
    var po = document.getElementById("post_office") ? document.getElementById("post_office").value : "";
    var ps = document.getElementById("police_station") ? document.getElementById("police_station").value : "";
    var dist = document.getElementById("district") ? document.getElementById("district").value : "";
    var pin = document.getElementById("pincode") ? document.getElementById("pincode").value : "";
    
    var query = [vill, po, ps, dist, pin].filter(Boolean).join(", ");
    if(!query) {
        alert("Address details fill karein!");
        return;
    }
    fetch("https://nominatim.openstreetmap.org/search?format=json&q=" + encodeURIComponent(query))
    .then(response => response.json())
    .then(data => {
        if(data && data.length > 0) {
            document.getElementById("latitude").value = data[0].lat;
            document.getElementById("longitude").value = data[0].lon;
            alert("Address geocoded successfully!");
        } else {
            alert("Address location not found.");
        }
    })
    .catch(err => alert("Error finding location coordinates."));
}
</script>
"""

# ---------------------------------------------------------------------------
# Dynamic Translatable HTML Templates
# ---------------------------------------------------------------------------
NAVBAR_HTML = """
<nav>
    <a href="{{ url_for('home') }}">{{ t('nav_home') }}</a>
    <a href="{{ url_for('search') }}">{{ t('nav_search') }}</a>
    <a href="{{ url_for('register') }}">{{ t('nav_register') }}</a>
    <a href="{{ url_for('my_bookings') }}">{{ t('nav_bookings') }}</a>
    <a href="{{ url_for('help_page') }}">{{ t('nav_help') }}</a>
    <a href="{{ url_for('admin_login') }}">{{ t('nav_admin') }}</a>
    <div class="lang-switcher">
        <a href="{{ url_for('set_lang', lang_code='en') }}" class="lang-btn {{ 'active' if current_lang == 'en' else '' }}">English</a>
        <a href="{{ url_for('set_lang', lang_code='bn') }}" class="lang-btn {{ 'active' if current_lang == 'bn' else '' }}">বাংলা</a>
    </div>
</nav>
"""

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('app_title') }} - Home</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('app_title') }}</h1>
    <p>{{ t('sub_title') }}</p>
</header>
""" + NAVBAR_HTML + """
<div class="container" style="text-align: center; padding: 40px 20px;">
    <h2>{{ t('welcome_msg') }}</h2>
    <p style="margin: 20px 0; color: #666;">{{ t('welcome_sub') }}</p>
    <div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;">
        <a href="{{ url_for('search') }}" class="btn btn-primary" style="padding: 15px 25px;">{{ t('btn_search') }}</a>
        <a href="{{ url_for('register') }}" class="btn" style="padding: 15px 25px;">{{ t('btn_register') }}</a>
    </div>
</div>
</body>
</html>
"""

REGISTER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('reg_header') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
    {{ geo_script|safe }}
</head>
<body>
<header>
    <h1>{{ t('reg_header') }}</h1>
</header>
""" + NAVBAR_HTML + """
<div class="container">
    {% with messages = get_flashed_messages() %}
      {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
    {% endwith %}
    <form method="POST">
        <div class="form-group"><label>{{ t('driver_name') }}</label><input type="text" name="name" required></div>
        <div class="form-group">
            <label>{{ t('vehicle_type') }}</label>
            <select name="vehicle_type" required>
                <option value="Auto">Auto</option>
                <option value="Car">Car</option>
                <option value="Bike">Bike</option>
                <option value="Van">Van</option>
                <option value="Truck">Truck</option>
            </select>
        </div>
        <div class="form-group"><label>{{ t('vehicle_number') }}</label><input type="text" name="vehicle_number" placeholder="WB-XX-XXXX" required></div>
        <div class="form-group"><label>{{ t('mobile_number') }}</label><input type="tel" name="contact_number" required></div>
        <div class="form-group"><label>{{ t('city') }}</label><input type="text" name="city"></div>
        <div class="form-group"><label>{{ t('village') }}</label><input type="text" id="village" name="village"></div>
        <div class="form-group"><label>{{ t('post_office') }}</label><input type="text" id="post_office" name="post_office"></div>
        <div class="form-group"><label>{{ t('police_station') }}</label><input type="text" id="police_station" name="police_station"></div>
        <div class="form-group"><label>{{ t('district') }}</label><input type="text" id="district" name="district"></div>
        <div class="form-group"><label>{{ t('pincode') }}</label><input type="text" id="pincode" name="pincode"></div>
        
        <hr style="margin:20px 0;">
        <button type="button" class="btn btn-secondary" onclick="getLocation()">{{ t('use_gps') }}</button>
        <button type="button" class="btn btn-secondary" onclick="geocodeAddress()">{{ t('use_address') }}</button>
        <span id="geo-status" style="color: green; font-weight: bold; margin-left: 10px;"></span>
        
        <div class="form-group" style="margin-top: 10px;"><label>{{ t('latitude') }}</label><input type="text" id="latitude" name="latitude" required></div>
        <div class="form-group"><label>{{ t('longitude') }}</label><input type="text" id="longitude" name="longitude" required></div>
        
        <button type="submit" class="btn">{{ t('btn_submit_reg') }}</button>
    </form>
</div>
</body>
</html>
"""

SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('search_header') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
    {{ geo_script|safe }}
</head>
<body>
<header>
    <h1>{{ t('search_header') }}</h1>
</header>
""" + NAVBAR_HTML + """
<div class="container">
    <form method="POST">
        <div class="form-group">
            <label>{{ t('vehicle_type') }}</label>
            <select name="vehicle_type">
                <option value="">{{ t('all_vehicles') }}</option>
                <option value="Auto">Auto</option>
                <option value="Car">Car</option>
                <option value="Bike">Bike</option>
                <option value="Van">Van</option>
                <option value="Truck">Truck</option>
            </select>
        </div>
        <button type="button" class="btn btn-secondary" onclick="getLocation()">{{ t('use_gps') }}</button>
        <div class="form-group" style="margin-top:10px;"><label>{{ t('latitude') }}</label><input type="text" id="latitude" name="latitude" value="{{ search_lat }}" required></div>
        <div class="form-group"><label>{{ t('longitude') }}</label><input type="text" id="longitude" name="longitude" value="{{ search_lon }}" required></div>
        <button type="submit" class="btn btn-primary">{{ t('btn_search_now') }}</button>
    </form>

    {% if results is not none %}
        <h3 style="margin-top: 25px;">{{ t('found_vehicles') }}</h3>
        {% if results %}
            {% for driver in results %}
                <div class="card" style="margin-top:15px;">
                    <div class="card-title">{{ driver.name }} ({{ driver.vehicle_type }})</div>
                    <p><strong>{{ t('vehicle_number') }}:</strong> {{ driver.vehicle_number }}</p>
                    <p><strong>Address:</strong> {{ driver.full_address }}</p>
                    <p><strong>{{ t('distance') }}:</strong> <span class="badge bg-success">{{ driver.distance }} KM</span></p>
                    <a href="{{ url_for('book', driver_id=driver.id, lat=search_lat, lon=search_lon) }}" class="btn">{{ t('btn_book') }}</a>
                </div>
            {% endfor %}
        {% else %}
            <p style="margin-top:15px; color: red;">{{ t('no_vehicles') }}</p>
        {% endif %}
    {% endif %}
</div>
</body>
</html>
"""

BOOK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('book_header') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('book_header') }}</h1>
</header>
""" + NAVBAR_HTML + """
<div class="container">
    {% if driver %}
        <div class="card">
            <h3>Driver: {{ driver.name }}</h3>
            <p><strong>{{ t('vehicle_type') }}:</strong> {{ driver.vehicle_type }} ({{ driver.vehicle_number }})</p>
            <p><strong>Location:</strong> {{ driver.full_address }}</p>
        </div>
        <form method="POST">
            <div class="form-group"><label>{{ t('passenger_name') }}</label><input type="text" name="passenger_name" required></div>
            <div class="form-group"><label>{{ t('mobile_number') }}</label><input type="tel" name="passenger_contact" required></div>
            <div class="form-group"><label>{{ t('pickup_address') }}</label><input type="text" name="pickup_place" required></div>
            <input type="hidden" name="pickup_lat" value="{{ search_lat }}">
            <input type="hidden" name="pickup_lon" value="{{ search_lon }}">
            <button type="submit" class="btn btn-primary">{{ t('btn_confirm_booking') }}</button>
        </form>
    {% else %}
        <p style="color:red;">Driver not found.</p>
    {% endif %}
</div>
</body>
</html>
"""

BOOKING_CONFIRM_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('booking_success') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('booking_success') }}</h1>
</header>
<div class="container" style="text-align:center;">
    <h2 style="color:green;">{{ t('booking_success_msg') }}</h2>
    <p style="margin:15px 0;">Driver Name: <strong>{{ driver_name }}</strong></p>
    <p>{{ t('driver_contact') }} <strong>{{ driver_contact }}</strong></p>
    <p>{{ t('call_driver_note') }}</p>
    <a href="{{ url_for('home') }}" class="btn">{{ t('nav_home') }}</a>
</div>
</body>
</html>
"""

MY_BOOKINGS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('my_bookings_header') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('my_bookings_header') }}</h1>
</header>
""" + NAVBAR_HTML + """
<div class="container">
    <form method="POST">
        <div class="form-group">
            <label>{{ t('enter_driver_mobile') }}</label>
            <input type="tel" name="contact_number" value="{{ contact_number }}" required>
        </div>
        <button type="submit" class="btn">{{ t('view_bookings') }}</button>
    </form>

    {% if bookings is not none %}
        <h3 style="margin-top:20px;">Booking Requests:</h3>
        {% if bookings %}
            {% for b in bookings %}
                <div class="card">
                    <p><strong>{{ t('passenger_name') }}:</strong> {{ b.passenger_name }}</p>
                    <p><strong>Contact:</strong> {{ b.passenger_contact }}</p>
                    <p><strong>{{ t('pickup_address') }}:</strong> {{ b.pickup_place }}</p>
                    <p><strong>Status:</strong> 
                        <span class="badge {% if b.status=='accepted' %}bg-success{% elif b.status=='rejected' %}bg-danger{% else %}bg-warning{% endif %}">
                            {{ b.status }}
                        </span>
                    </p>
                    {% if b.status == 'pending' %}
                        <form method="POST" action="{{ url_for('update_booking', booking_id=b.id) }}" style="margin-top:10px; display:flex; gap:10px;">
                            <input type="hidden" name="contact_number" value="{{ contact_number }}">
                            <button type="submit" name="action" value="accept" class="btn btn-primary">{{ t('accept') }}</button>
                            <button type="submit" name="action" value="reject" class="btn btn-danger">{{ t('reject') }}</button>
                        </form>
                    {% endif %}
                </div>
            {% endfor %}
        {% else %}
            <p style="margin-top:15px;">{{ t('no_requests') }}</p>
        {% endif %}
    {% endif %}
</div>
</body>
</html>
"""

HELP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('help_header') }} - {{ t('app_title') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('help_header') }}</h1>
</header>
""" + NAVBAR_HTML + """
<div class="container">
    {% with messages = get_flashed_messages() %}
      {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
    {% endwith %}
    <form method="POST">
        <div class="form-group">
            <label>{{ t('who_are_you') }}</label>
            <select name="reporter_type">
                <option value="Passenger">Passenger</option>
                <option value="Driver">Driver</option>
            </select>
        </div>
        <div class="form-group"><label>Name</label><input type="text" name="name" required></div>
        <div class="form-group"><label>{{ t('mobile_number') }}</label><input type="tel" name="contact_number" required></div>
        <div class="form-group"><label>{{ t('vehicle_number') }}</label><input type="text" name="related_vehicle_number"></div>
        <div class="form-group"><label>{{ t('your_complaint') }}</label><textarea name="message" rows="4" required></textarea></div>
        <button type="submit" class="btn btn-primary">{{ t('btn_submit_complaint') }}</button>
    </form>
</div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('admin_panel_login') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
""" + NAVBAR_HTML + """
<div class="container" style="max-width:400px; margin-top:50px;">
    <h2>{{ t('admin_panel_login') }}</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
    {% endwith %}
    <form method="POST">
        <div class="form-group"><label>{{ t('username') }}</label><input type="text" name="username" required></div>
        <div class="form-group"><label>{{ t('password') }}</label><input type="password" name="password" required></div>
        <button type="submit" class="btn btn-primary">{{ t('btn_login') }}</button>
    </form>
</div>
</body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t('admin_dashboard') }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<header>
    <h1>{{ t('admin_dashboard') }}</h1>
    <a href="{{ url_for('admin_logout') }}" style="color:white;">{{ t('logout') }}</a>
</header>
<div class="container" style="max-width:1100px;">
    {% with messages = get_flashed_messages() %}
      {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
    {% endwith %}
    
    <h3>{{ t('registered_drivers') }}</h3>
    <table>
        <tr>
            <th>{{ t('th_id') }}</th><th>{{ t('th_name') }}</th><th>{{ t('th_type') }}</th><th>{{ t('th_number') }}</th><th>{{ t('th_contact') }}</th><th>{{ t('th_address') }}</th><th>{{ t('th_status') }}</th><th>{{ t('th_actions') }}</th>
        </tr>
        {% for d in drivers %}
        <tr>
            <td>{{ d.id }}</td>
            <td>{{ d.name }}</td>
            <td>{{ d.vehicle_type }}</td>
            <td>{{ d.vehicle_number }}</td>
            <td>{{ d.contact_number }}</td>
            <td>{{ d.full_address }}</td>
            <td>{{ t('active') if d.is_available==1 else t('disabled') }}</td>
            <td>
                <form method="POST" action="{{ url_for('admin_toggle_driver', driver_id=d.id) }}" style="display:inline;">
                    <button type="submit" class="btn btn-secondary" style="padding:2px 5px; font-size:12px;">{{ t('toggle') }}</button>
                </form>
                <a href="{{ url_for('admin_edit_driver', driver_id=d.id) }}" class="btn btn-primary" style="padding:2px 5px; font-size:12px;">{{ t('edit') }}</a>
                <form method="POST" action="{{ url_for('admin_delete_driver', driver_id=d.id) }}" style="display:inline;">
                    <button type="submit" class="btn btn-danger" style="padding:2px 5px; font-size:12px;">{{ t('delete') }}</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>

    <h3 style="margin-top:30px;">{{ t('complaints_header') }}</h3>
    <table>
        <tr><th>{{ t('th_id') }}</th><th>{{ t('th_type') }}</th><th>{{ t('th_name') }}</th><th>{{ t('th_contact') }}</th><th>{{ t('th_gadi_no') }}</th><th>{{ t('th_message') }}</th><th>{{ t('th_status') }}</th><th>{{ t('th_action') }}</th></tr>
        {% for c in complaints %}
        <tr>
            <td>{{ c.id }}</td>
            <td>{{ c.reporter_type }}</td>
            <td>{{ c.name }}</td>
            <td>{{ c.contact_number }}</td>
            <td>{{ c.related_vehicle_number }}</td>
            <td>{{ c.message }}</td>
            <td>{{ c.status }}</td>
            <td>
                {% if c.status != 'resolved' %}
                <form method="POST" action="{{ url_for('admin_resolve_complaint', complaint_id=c.id) }}">
                    <button type="submit" class="btn btn-primary" style="padding:2px 5px; font-size:12px;">{{ t('resolve') }}</button>
                </form>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
</body>
</html>
"""

ADMIN_EDIT_DRIVER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Edit Driver - Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {{ style|safe }}
</head>
<body>
<div class="container">
    <h2>Edit Driver Details</h2>
    <form method="POST">
        <div class="form-group"><label>Name</label><input type="text" name="name" value="{{ driver.name }}" required></div>
        <div class="form-group">
            <label>Vehicle Type</label>
            <select name="vehicle_type" required>
                {% for vt in ['Auto', 'Car', 'Bike', 'Van', 'Truck'] %}
                    <option value="{{ vt }}" {% if driver.vehicle_type == vt %}selected{% endif %}>{{ vt }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="form-group"><label>Vehicle Number</label><input type="text" name="vehicle_number" value="{{ driver.vehicle_number }}" required></div>
        <div class="form-group"><label>Contact Number</label><input type="tel" name="contact_number" value="{{ driver.contact_number }}" required></div>
        <div class="form-group"><label>City</label><input type="text" name="city" value="{{ driver.city or '' }}"></div>
        <div class="form-group"><label>Village</label><input type="text" name="village" value="{{ driver.village or '' }}"></div>
        <div class="form-group"><label>Post Office</label><input type="text" name="post_office" value="{{ driver.post_office or '' }}"></div>
        <div class="form-group"><label>Police Station</label><input type="text" name="police_station" value="{{ driver.police_station or '' }}"></div>
        <div class="form-group"><label>District</label><input type="text" name="district" value="{{ driver.district or '' }}"></div>
        <div class="form-group"><label>PIN Code</label><input type="text" name="pincode" value="{{ driver.pincode or '' }}"></div>
        <div class="form-group"><label>Latitude</label><input type="text" name="latitude" value="{{ driver.latitude }}" required></div>
        <div class="form-group"><label>Longitude</label><input type="text" name="longitude" value="{{ driver.longitude }}" required></div>
        <button type="submit" class="btn">Update Driver</button>
    </form>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App Routes Implementation
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template_string(HOME_HTML, style=BASE_STYLE)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        vehicle_number = request.form.get("vehicle_number", "").strip().upper()
        contact_number = request.form.get("contact_number", "").strip()
        city = request.form.get("city", "").strip()
        village = request.form.get("village", "").strip()
        post_office = request.form.get("post_office", "").strip()
        police_station = request.form.get("police_station", "").strip()
        district = request.form.get("district", "").strip()
        pincode = request.form.get("pincode", "").strip()

        try:
            latitude = float(request.form.get("latitude", 0))
            longitude = float(request.form.get("longitude", 0))
        except ValueError:
            flash("Kripya sahi Latitude/Longitude numeric format me bharein.")
            return render_template_string(
                REGISTER_HTML, style=BASE_STYLE, geo_script=GEO_SCRIPT
            )

        conn = get_db()
        try:
            if DATABASE_URL:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO drivers (name, vehicle_type, vehicle_number, contact_number, city, village, post_office, police_station, district, pincode, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        vehicle_type,
                        vehicle_number,
                        contact_number,
                        city,
                        village,
                        post_office,
                        police_station,
                        district,
                        pincode,
                        latitude,
                        longitude,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO drivers (name, vehicle_type, vehicle_number, contact_number, city, village, post_office, police_station, district, pincode, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        vehicle_type,
                        vehicle_number,
                        contact_number,
                        city,
                        village,
                        post_office,
                        police_station,
                        district,
                        pincode,
                        latitude,
                        longitude,
                    ),
                )
            conn.commit()
            flash("Registration Successful!")
            return redirect(url_for("register"))
        except DB_INTEGRITY_ERRORS:
            conn.rollback()
            flash("Vehicle Number pehle se registered hai.")
        finally:
            conn.close()

    return render_template_string(
        REGISTER_HTML, style=BASE_STYLE, geo_script=GEO_SCRIPT
    )


@app.route("/search", methods=["GET", "POST"])
def search():
    results = None
    search_lat = 0
    search_lon = 0

    if request.method == "POST":
        vehicle_type = request.form.get("vehicle_type", "").strip()
        try:
            search_lat = float(request.form.get("latitude", 0))
            search_lon = float(request.form.get("longitude", 0))
        except ValueError:
            return render_template_string(
                SEARCH_HTML,
                style=BASE_STYLE,
                geo_script=GEO_SCRIPT,
                results=[],
                search_lat=search_lat,
                search_lon=search_lon,
            )

        conn = get_db()
        if DATABASE_URL:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            if vehicle_type:
                cur.execute(
                    "SELECT * FROM drivers WHERE is_available = 1 AND vehicle_type = %s",
                    (vehicle_type,),
                )
            else:
                cur.execute("SELECT * FROM drivers WHERE is_available = 1")
            rows = cur.fetchall()
        else:
            if vehicle_type:
                cur = conn.execute(
                    "SELECT * FROM drivers WHERE is_available = 1 AND vehicle_type = ?",
                    (vehicle_type,),
                )
            else:
                cur = conn.execute("SELECT * FROM drivers WHERE is_available = 1")
            rows = cur.fetchall()

        conn.close()

        drivers_list = []
        for r in rows:
            row_dict = dict(r)
            d = haversine_km(
                search_lat, search_lon, row_dict["latitude"], row_dict["longitude"]
            )
            row_dict["distance"] = d
            row_dict["full_address"] = build_full_address(row_dict)
            drivers_list.append(row_dict)

        drivers_list.sort(key=lambda x: x["distance"])
        results = drivers_list

    return render_template_string(
        SEARCH_HTML,
        style=BASE_STYLE,
        geo_script=GEO_SCRIPT,
        results=results,
        search_lat=search_lat,
        search_lon=search_lon,
    )


@app.route("/book/<int:driver_id>", methods=["GET", "POST"])
def book(driver_id):
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM drivers WHERE id = %s", (driver_id,))
        driver_row = cur.fetchone()
    else:
        cur = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,))
        driver_row = cur.fetchone()

    if not driver_row:
        conn.close()
        return render_template_string(BOOK_HTML, style=BASE_STYLE, driver=None)

    driver = dict(driver_row)
    driver["full_address"] = build_full_address(driver)

    if request.method == "POST":
        passenger_name = request.form.get("passenger_name", "").strip()
        passenger_contact = request.form.get("passenger_contact", "").strip()
        pickup_place = request.form.get("pickup_place", "").strip()
        p_lat = request.form.get("pickup_lat")
        p_lon = request.form.get("pickup_lon")

        if DATABASE_URL:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO bookings (driver_id, driver_name, driver_contact, passenger_name, passenger_contact, pickup_place, pickup_lat, pickup_lon)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    driver["id"],
                    driver["name"],
                    driver["contact_number"],
                    passenger_name,
                    passenger_contact,
                    pickup_place,
                    float(p_lat) if p_lat else None,
                    float(p_lon) if p_lon else None,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO bookings (driver_id, driver_name, driver_contact, passenger_name, passenger_contact, pickup_place, pickup_lat, pickup_lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver["id"],
                    driver["name"],
                    driver["contact_number"],
                    passenger_name,
                    passenger_contact,
                    pickup_place,
                    float(p_lat) if p_lat else None,
                    float(p_lon) if p_lon else None,
                ),
            )
        conn.commit()
        conn.close()
        return render_template_string(
            BOOKING_CONFIRM_HTML,
            style=BASE_STYLE,
            driver_name=driver["name"],
            driver_contact=driver["contact_number"],
        )

    conn.close()
    search_lat = request.args.get("lat", "")
    search_lon = request.args.get("lon", "")

    return render_template_string(
        BOOK_HTML,
        style=BASE_STYLE,
        driver=driver,
        search_lat=search_lat,
        search_lon=search_lon,
    )


@app.route("/my_bookings", methods=["GET", "POST"])
def my_bookings():
    bookings = None
    contact_number = ""

    if request.method == "POST":
        contact_number = request.form.get("contact_number", "").strip()
        conn = get_db()
        if DATABASE_URL:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                "SELECT * FROM bookings WHERE driver_contact = %s ORDER BY id DESC",
                (contact_number,),
            )
            bookings = [dict(r) for r in cur.fetchall()]
        else:
            cur = conn.execute(
                "SELECT * FROM bookings WHERE driver_contact = ? ORDER BY id DESC",
                (contact_number,),
            )
            bookings = [dict(r) for r in cur.fetchall()]
        conn.close()

    return render_template_string(
        MY_BOOKINGS_HTML,
        style=BASE_STYLE,
        bookings=bookings,
        contact_number=contact_number,
    )


@app.route("/update_booking/<int:booking_id>", methods=["POST"])
def update_booking(booking_id):
    action = request.form.get("action")
    new_status = "accepted" if action == "accept" else "rejected"

    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE bookings SET status = %s WHERE id = %s", (new_status, booking_id)
        )
    else:
        conn.execute(
            "UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id)
        )
    conn.commit()
    conn.close()

    return redirect(url_for("my_bookings"), code=307)


@app.route("/help", methods=["GET", "POST"])
def help_page():
    if request.method == "POST":
        reporter_type = request.form.get("reporter_type")
        name = request.form.get("name")
        contact_number = request.form.get("contact_number")
        related_vehicle_number = request.form.get("related_vehicle_number")
        message = request.form.get("message")

        conn = get_db()
        if DATABASE_URL:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO complaints (reporter_type, name, contact_number, related_vehicle_number, message)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    reporter_type,
                    name,
                    contact_number,
                    related_vehicle_number,
                    message,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO complaints (reporter_type, name, contact_number, related_vehicle_number, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reporter_type,
                    name,
                    contact_number,
                    related_vehicle_number,
                    message,
                ),
            )
        conn.commit()
        conn.close()
        flash("Complaint Submitted Successfully.")
        return redirect(url_for("help_page"))

    return render_template_string(HELP_HTML, style=BASE_STYLE)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Sahi Username ya Password daalein.")

    return render_template_string(ADMIN_LOGIN_HTML, style=BASE_STYLE)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM drivers ORDER BY id DESC")
        drivers = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM complaints ORDER BY id DESC")
        complaints = [dict(r) for r in cur.fetchall()]
    else:
        drivers = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM drivers ORDER BY id DESC"
            ).fetchall()
        ]
        complaints = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM complaints ORDER BY id DESC"
            ).fetchall()
        ]

    for d in drivers:
        d["full_address"] = build_full_address(d)

    conn.close()
    return render_template_string(
        ADMIN_DASHBOARD_HTML,
        style=BASE_STYLE,
        drivers=drivers,
        complaints=complaints,
    )


@app.route("/admin/toggle_driver/<int:driver_id>", methods=["POST"])
@admin_required
def admin_toggle_driver(driver_id):
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE drivers SET is_available = CASE WHEN is_available = 1 THEN 0 ELSE 1 END WHERE id = %s",
            (driver_id,),
        )
    else:
        conn.execute(
            "UPDATE drivers SET is_available = CASE WHEN is_available = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (driver_id,),
        )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit_driver/<int:driver_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_driver(driver_id):
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name")
        vehicle_type = request.form.get("vehicle_type")
        vehicle_number = request.form.get("vehicle_number").upper()
        contact_number = request.form.get("contact_number")
        city = request.form.get("city")
        village = request.form.get("village")
        post_office = request.form.get("post_office")
        police_station = request.form.get("police_station")
        district = request.form.get("district")
        pincode = request.form.get("pincode")
        latitude = float(request.form.get("latitude"))
        longitude = float(request.form.get("longitude"))

        if DATABASE_URL:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE drivers
                SET name=%s, vehicle_type=%s, vehicle_number=%s, contact_number=%s, city=%s, village=%s, post_office=%s, police_station=%s, district=%s, pincode=%s, latitude=%s, longitude=%s
                WHERE id=%s
                """,
                (
                    name,
                    vehicle_type,
                    vehicle_number,
                    contact_number,
                    city,
                    village,
                    post_office,
                    police_station,
                    district,
                    pincode,
                    latitude,
                    longitude,
                    driver_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE drivers
                SET name=?, vehicle_type=?, vehicle_number=?, contact_number=?, city=?, village=?, post_office=?, police_station=?, district=?, pincode=?, latitude=?, longitude=?
                WHERE id=?
                """,
                (
                    name,
                    vehicle_type,
                    vehicle_number,
                    contact_number,
                    city,
                    village,
                    post_office,
                    police_station,
                    district,
                    pincode,
                    latitude,
                    longitude,
                    driver_id,
                ),
            )
        conn.commit()
        conn.close()
        flash("Driver details updated.")
        return redirect(url_for("admin_dashboard"))

    if DATABASE_URL:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM drivers WHERE id = %s", (driver_id,))
        driver = dict(cur.fetchone())
    else:
        cur = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,))
        driver = dict(cur.fetchone())

    conn.close()
    return render_template_string(
        ADMIN_EDIT_DRIVER_HTML, style=BASE_STYLE, driver=driver
    )


@app.route("/admin/delete_driver/<int:driver_id>", methods=["POST"])
@admin_required
def admin_delete_driver(driver_id):
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute("DELETE FROM drivers WHERE id = %s", (driver_id,))
    else:
        conn.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
    conn.commit()
    conn.close()
    flash("Driver deleted.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/resolve_complaint/<int:complaint_id>", methods=["POST"])
@admin_required
def admin_resolve_complaint(complaint_id):
    conn = get_db()
    if DATABASE_URL:
        cur = conn.cursor()
        cur.execute(
            "UPDATE complaints SET status = 'resolved' WHERE id = %s",
            (complaint_id,),
        )
    else:
        conn.execute(
            "UPDATE complaints SET status = 'resolved' WHERE id = ?",
            (complaint_id,),
        )
    conn.commit()
    conn.close()
    flash("Complaint marked as resolved.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)