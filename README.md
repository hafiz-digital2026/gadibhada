# Gadi Bhada 🚗

## Naye Features (is update me)
1. **Duplicate registration block** — same gadi number ya contact number dobara register nahi ho sakta.
2. **Admin panel** — `/admin/login` pe login karke, admin hi drivers ko ON/OFF kar sakta hai.
   - Default Admin ID: `admin`
   - Default Password: `GadiBhada@2026`
   - **Deploy karne se pehle ye zaroor badlein** (neeche "Environment Variables" section dekhein).
3. **Booking system** — passenger kisi gadi ko "Book Karein" bata sakta hai, driver apna
   contact number daal ke `/my-bookings` pe request Accept/Reject kar sakta hai.
4. **Admin ke paas teen full control** — har driver ke saamne:
   - **On/Off** — availability turant badal sakte hain
   - **Edit** — driver ki galat details (naam, gadi number, contact, address) theek kar sakte hain
   - **Delete** — kisi bhi galat/fake registration ko poori tarah hata sakte hain
5. **Mobile-app jaisa experience (PWA)** — koi bhi phone pe site kholke
   "Add to Home Screen" / "Install App" kar sakta hai, phir wo ek app icon jaisa
   khulega (Chrome/Safari dono me kaam karta hai, koi Play Store chahiye nahi).
6. **Help / Shikayat section** (`/help`) — passenger ya driver, kisi ko bhi dikkat ho
   (naam + mobile number + apni baat), seedha admin ke paas complaint chali jaati hai.
   Admin Dashboard me sab shikayatein dikhti hain, "Resolve Karein" bata ke close kar sakte hain.

---

## Local pe Chalane ke liye (Windows)
PowerShell/Terminal me app ke folder ke andar jaake:
```
python app.py
```
Browser me kholein: http://127.0.0.1:5000

---

## 🌐 Live / Online Karna — Poora Tarika (Step-by-Step)

Ye site **Render.com** pe free me live ho sakti hai. Neeche har step detail me hai — ek-ek
karke follow karein.

### Step 1: GitHub Account Banayein (agar nahi hai)
- https://github.com pe jaake free account banayein.

### Step 2: Apna Code GitHub pe Daalein
1. GitHub pe login karke **"New repository"** button dabayein.
2. Naam dein jaise `gadibhada` → **Create repository**.
3. Us repository page pe **"uploading an existing file"** link milega — usi se
   apne computer se `app.py`, `requirements.txt`, aur `Procfile` — teeno files
   seedha upload kar dein (drag-and-drop bhi ho sakta hai).
4. Neeche **"Commit changes"** button dabayein.

Ab aapka code GitHub pe online hai.

### Step 3: Render.com pe Account Banayein
- https://render.com pe jaake **"Get Started"** dabayein, GitHub account se hi
  sign up kar lein (sabse aasaan tarika) — ye free hai.

### Step 4: Naya Web Service Banayein
1. Render dashboard me **"New +"** button → **"Web Service"** chunein.
2. Apna GitHub repo (`gadibhada`) list me dikhega — usse **"Connect"** karein.
3. Ye settings bharni hongi:
   - **Name**: kuch bhi, jaise `gadibhada` (isi se URL banega: `gadibhada.onrender.com`)
   - **Region**: Singapore (India ke sabse paas)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: **Free** chunein

### Step 5: Admin Password Set Karein (Zaroori!)
Same page pe niche **"Environment Variables"** section milega — **"Add Environment Variable"**
dabake ye teen add karein:

| Key | Value |
|---|---|
| `ADMIN_USERNAME` | apna pasand ka admin ID, jaise `admin` |
| `ADMIN_PASSWORD` | apna strong password, jaise `GadiBhada@2026` |
| `SECRET_KEY` | koi bhi random lamba text, jaise `xyz123secretkeybadaldena` |

**Ye bahut zaroori hai** — agar ye nahi bharenge to site code me likha default password
hi use hoga, jo koi bhi dekh sakta hai.

### Step 6: Deploy Karein
- Sabse niche **"Create Web Service"** dabayein.
- Render 2-5 minute me code build karke site live kar dega.
- Upar ek link milega jaisa: `https://gadibhada.onrender.com` — yahi aapki live site hai,
  ise kisi ko bhi bhej sakte hain, wo apne phone/computer se khol sakta hai.

### Aage se Update Karna Ho To
Jab bhi app.py me koi badlav karayenge (mujhse), naya file GitHub pe upload kar dena —
Render khud-ba-khud usko detect karke site update kar dega (2-3 minute me).

---

## ⚠️ Zaroori Baat — Database ke baare me
Render ke **free plan** pe file storage permanent nahi hota — jab bhi Render app ko
restart karega (naya deploy, ya lambe idle time ke baad), tab `gadibhada.db` file
(jisme saare drivers/bookings hain) **reset ho sakti hai**.

Testing/demo ke liye ye theek hai. **Ab app ko permanent database (jaise Supabase Postgres)
use karne ka support mil gaya hai** — neeche section dekhein.

---

## ✅ Permanent Database Lagana (Data Reset Hona Band Karne ke liye)

App ab **Supabase** (ya kisi bhi PostgreSQL database) ke saath kaam kar sakta hai, taaki
data kabhi reset na ho — chahe Render free plan restart kare.

1. https://supabase.com pe free account banayein, naya project banayein
   (ek strong database password rakhein aur yaad rakh lein).
2. Project ke **Settings → Database** me jaake **Connection String** copy karein —
   ye kuch aisa dikhega:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
3. `[YOUR-PASSWORD]` ki jagah apna real Supabase password likhein.
4. Render dashboard me apni service kholke → **"Environment"** tab → naya variable add karein:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | upar wali poori connection string (password bhare hue) |

5. **Save, rebuild aur deploy** dabayein.

Bas — ab app automatically is permanent database ka use karega, aur data kabhi reset
nahi hoga. Agar `DATABASE_URL` nahi diya jaayega, to app pehle jaisi local SQLite file
hi use karega (jo Render free plan pe reset ho sakti hai).

---

## Doosre Free Hosting Options
Render ke alawa **Railway.app**, **PythonAnywhere**, ya **Fly.io** pe bhi isi
`requirements.txt` aur `Procfile` se deploy ho sakta hai — steps milte-julte hain.

---

## Mobile App Jaisa Use Karna
Site khol ke:
- **Android (Chrome)**: 3-dot menu → "Add to Home screen" / "Install app"
- **iPhone (Safari)**: Share icon → "Add to Home Screen"

Isse ek app icon phone ki home screen pe ban jayega, aur khulne pe browser bar nahi dikhega —
bilkul app jaisa lagega. Agar aage chal ke Play Store / App Store pe real native app
chahiye (push notifications, offline mode wagera ke saath), uske liye Flutter/React Native
me alag se banana padega — bata dein to us par bhi plan bana dunga.

---

## Admin Panel Kaise Use Karein
1. `/admin/login` pe jaayein
2. ID/Password daalein
3. Dashboard me har driver ke saamne teen buttons hain:
   - **On/Off** — availability turant badal jaati hai, OFF driver passengers ko search me nahi dikhega
   - **Edit** — driver ki koi bhi detail (naam, gadi number, contact, Vill/PO/PS/Dist/PIN) sudhar sakte hain
   - **Delete** — driver ko hamesha ke liye hata sakte hain (ye wapas nahi ho sakta, isliye confirm popup aayega)
4. Neeche saari bookings ka record bhi dikhta hai.
