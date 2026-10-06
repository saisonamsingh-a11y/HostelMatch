"""HostelMatch backend: Flask + SQLite. Run: python app.py"""
import json, sqlite3, os, math, hmac, uuid, random
from flask import Flask, jsonify, request, render_template, g

BASE = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE, "templates")
app = Flask(__name__, template_folder=templates_dir if os.path.isdir(templates_dir) else BASE)

DB = os.environ.get("DB_PATH", "/tmp/hostelmatch.db" if os.environ.get("VERCEL") else os.path.join(BASE, "hostelmatch.db"))
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")
CLAT, CLNG = float(os.environ.get("CAMPUS_LAT", 19.0760)), float(os.environ.get("CAMPUS_LNG", 72.8777))

def place(i, d):
    """Spread seed hostels geographically around the campus at their stated distance in km."""
    a = math.radians(i * 137.5)
    return (round(CLAT + d / 111 * math.cos(a), 5), round(CLNG + d / (111 * math.cos(math.radians(CLAT))) * math.sin(a), 5))

ROOMS = ["single", "double", "triple", "dorm"]
AMENITIES = ["wifi", "ac", "meals", "laundry", "gym", "study_room", "power_backup", "security"]
GENDERS = ["coed", "boys", "girls"]
SORTS = {
    "match": ("match", True),
    "price": ("price", False),
    "rating": ("rating", True),
    "distance": ("distance_km", False)
}

IMAGES = [
    "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1560185893-a55cbc8c57e8?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=600&q=80"
]

SEED = [
    ("Scholar's Nest", "Near Campus Gate", 0.6, 4.4, {"single": 12000, "double": 8500}, ["wifi", "meals", "study_room", "security", "power_backup"], "Quiet block with a 24h study room and home-style meals.", "coed", True, "9876543210", IMAGES[0], 4.8),
    ("Urban Bunk Co.", "Station Road", 3.2, 4.1, {"dorm": 5500, "double": 7500}, ["wifi", "ac", "laundry", "gym", "security"], "Social, modern hostel close to the metro.", "boys", True, "9876543211", IMAGES[1], 4.2),
    ("Green Quad Residency", "Park Avenue", 1.4, 4.6, {"single": 14500, "double": 10000, "triple": 7800}, ["wifi", "ac", "meals", "laundry", "study_room", "security", "power_backup"], "Premium rooms, all-inclusive, strict visitor policy.", "girls", True, "9876543212", IMAGES[2], 4.9),
    ("Budget Bay PG", "Old Market Lane", 2.1, 3.7, {"triple": 5200, "dorm": 4200}, ["wifi", "meals", "power_backup"], "Lowest-cost option with basic comforts.", "coed", False, "9876543213", IMAGES[3], 3.9),
    ("Campus Edge Hostel", "University Rd", 0.3, 4.2, {"single": 10500, "double": 7200, "triple": 6000}, ["wifi", "laundry", "study_room", "security"], "Five-minute walk to lecture halls.", "coed", True, "9876543214", IMAGES[4], 4.5),
    ("Lakeview Stay", "Lake Road", 4.8, 4.5, {"single": 13000, "double": 9200}, ["wifi", "ac", "meals", "gym", "laundry", "security"], "Calm lakeside spot with a gym and rooftop.", "girls", True, "9876543215", IMAGES[0], 4.7),
    ("Metro Hive", "Metro Junction", 2.7, 3.9, {"double": 6800, "triple": 5600, "dorm": 4800}, ["wifi", "ac", "laundry", "power_backup"], "Great transport links, lively common area.", "boys", False, "9876543216", IMAGES[1], 4.1),
    ("Scholars Court", "Library Street", 1.0, 4.3, {"single": 11500, "double": 8000}, ["wifi", "ac", "study_room", "meals", "security", "power_backup"], "Built for exam season: silent hours and library access.", "coed", True, "9876543217", IMAGES[2], 4.8),
    ("Zen Dorms", "Hill View", 5.5, 4.0, {"dorm": 4000, "triple": 5000}, ["wifi", "meals", "gym", "security"], "Peaceful and affordable, a bit far out.", "boys", False, "9876543218", IMAGES[3], 4.0),
    ("Prime Student Suites", "Tech Park Rd", 3.9, 4.7, {"single": 16000, "double": 11500}, ["wifi", "ac", "meals", "laundry", "gym", "study_room", "security", "power_backup"], "Top-rated suites with every amenity.", "coed", True, "9876543219", IMAGES[4], 4.9)
]

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d:
        d.close()

def init_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS hostels(id INTEGER PRIMARY KEY, name TEXT, area TEXT, distance_km REAL, rating REAL, rooms TEXT, amenities TEXT, about TEXT, lat REAL, lng REAL, gender TEXT, verified INTEGER, phone TEXT, cover_image TEXT, safety_score REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS shortlist(client_id TEXT, hostel_id INTEGER, PRIMARY KEY(client_id, hostel_id))")
    c.execute("CREATE TABLE IF NOT EXISTS enquiries(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, hostel_id INTEGER, name TEXT, phone TEXT, move_date TEXT, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    
    cols = [r[1] for r in c.execute("PRAGMA table_info(hostels)")]
    if "lat" not in cols:
        c.execute("ALTER TABLE hostels ADD COLUMN lat REAL")
        c.execute("ALTER TABLE hostels ADD COLUMN lng REAL")
    if "gender" not in cols:
        c.execute("ALTER TABLE hostels ADD COLUMN gender TEXT DEFAULT 'coed'")
        c.execute("ALTER TABLE hostels ADD COLUMN verified INTEGER DEFAULT 1")
        c.execute("ALTER TABLE hostels ADD COLUMN phone TEXT DEFAULT '9876543210'")
        c.execute("ALTER TABLE hostels ADD COLUMN cover_image TEXT")
        c.execute("ALTER TABLE hostels ADD COLUMN safety_score REAL DEFAULT 4.5")

    for i, d in c.execute("SELECT id, distance_km FROM hostels WHERE lat IS NULL").fetchall():
        c.execute("UPDATE hostels SET lat=?, lng=? WHERE id=?", (*place(i, d), i))
            
    if not c.execute("SELECT 1 FROM hostels").fetchone():
        for i, (n, a, d, r, rooms, am, ab, gen, ver, ph, img, sft) in enumerate(SEED, 1):
            c.execute("INSERT INTO hostels VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (i, n, a, d, r, json.dumps(rooms), json.dumps(am), ab, *place(i, d), gen, 1 if ver else 0, ph, img, sft))
    c.commit()
    c.close()

def row_to_dict(r):
    h = dict(r)
    h["rooms"] = json.loads(h["rooms"])
    h["amenities"] = json.loads(h["amenities"])
    h["price"] = min(h["rooms"].values())
    h["gender"] = h.get("gender") or "coed"
    h["verified"] = bool(h.get("verified", True))
    h["phone"] = h.get("phone") or "9876543210"
    h["cover_image"] = h.get("cover_image") or IMAGES[(h["id"] - 1) % len(IMAGES)]
    h["safety_score"] = h.get("safety_score") or 4.5
    return h

def score(h, p):
    """Returns (total 0-100, breakdown). Weights: budget 25, distance 25, amenities 30, room 10, rating 10."""
    rooms = [h["rooms"][r] for r in p["rooms"] if r in h["rooms"]] or list(h["rooms"].values())
    price = min(rooms)
    h["price"] = price
    ratio = price / p["budget"]
    
    if ratio <= 0.8:
        budget = 25.0
    else:
        budget = 25.0 - (ratio - 0.8) / 0.2 * 10.0
    budget = max(0.0, min(25.0, budget))
        
    dist = 25.0 * (1.0 - 0.6 * h["distance_km"] / p["max_distance"])
    dist = max(0.0, min(25.0, dist))
    
    am = p["amenities"]
    amen = 30.0 * (len([a for a in am if a in h["amenities"]]) / len(am)) if am else 30.0
    
    room = 10.0
    rating = min(10.0, max(0.0, h["rating"] / 5.0 * 10.0))
    
    parts = {
        "budget": round(budget, 1),
        "distance": round(dist, 1),
        "amenities": round(amen, 1),
        "room": room,
        "rating": round(rating, 1)
    }
    total = min(100, max(0, round(sum(parts.values()))))
    return total, parts

def parse(data):
    try:
        budget = float(data.get("budget", 0))
        maxd = float(data.get("max_distance", 0))
    except (TypeError, ValueError):
        return None, "budget and max_distance must be numbers"
    if budget <= 0 or maxd <= 0:
        return None, "budget and max_distance must be greater than 0"
    rooms = [r for r in data.get("rooms", []) if r in ROOMS]
    ams = [a for a in data.get("amenities", []) if a in AMENITIES]
    gender = data.get("gender", "")
    q = str(data.get("q", "")).strip().lower()
    return {"budget": budget, "max_distance": maxd, "rooms": rooms, "amenities": ams, "gender": gender, "q": q}, None

@app.get("/")
def index():
    return render_template("index.html", rooms=ROOMS, amenities=AMENITIES, genders=GENDERS)

@app.post("/api/recommend")
def recommend():
    data = request.get_json(silent=True) or {}
    p, err = parse(data)
    if err:
        return jsonify(error=err), 400
    key, rev = SORTS.get(data.get("sort", "match"), SORTS["match"])
    out = []
    for r in db().execute("SELECT * FROM hostels"):
        h = row_to_dict(r)
        
        # Gender filter check
        if p["gender"] and p["gender"] != "coed" and h["gender"] != "coed" and h["gender"] != p["gender"]:
            continue
            
        # Search query check
        if p["q"]:
            match_str = f"{h['name']} {h['area']} {h['about']}".lower()
            if p["q"] not in match_str:
                continue

        offered = [x for x in p["rooms"] if x in h["rooms"]]
        if p["rooms"] and not offered:
            continue
        h["price"] = min(h["rooms"][x] for x in (offered or h["rooms"]))
        if h["price"] > p["budget"] or h["distance_km"] > p["max_distance"]:
            continue
        h["match"], h["breakdown"] = score(h, p)
        h["missing_amenities"] = [a for a in p["amenities"] if a not in h["amenities"]]
        out.append(h)
    out.sort(key=lambda h: (h[key], h["match"]), reverse=rev)
    return jsonify(count=len(out), results=out)

@app.get("/api/hostels/<int:hid>")
def hostel(hid):
    r = db().execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    return (jsonify(row_to_dict(r)) if r else (jsonify(error="not found"), 404))

def cid():
    return request.headers.get("X-Client-Id", "")[:64] or None

@app.get("/api/shortlist")
def get_short():
    c = cid()
    if not c:
        return jsonify(error="X-Client-Id header required"), 400
    rows = db().execute("SELECT h.* FROM hostels h JOIN shortlist s ON s.hostel_id=h.id WHERE s.client_id=?", (c,))
    return jsonify(results=[row_to_dict(r) for r in rows])

@app.route("/api/shortlist/<int:hid>", methods=["POST", "DELETE"])
def toggle_short(hid):
    c = cid()
    if not c:
        return jsonify(error="X-Client-Id header required"), 400
    d = db()
    if not d.execute("SELECT 1 FROM hostels WHERE id=?", (hid,)).fetchone():
        return jsonify(error="not found"), 404
    if request.method == "POST":
        d.execute("INSERT OR IGNORE INTO shortlist VALUES(?,?)", (c, hid))
    else:
        d.execute("DELETE FROM shortlist WHERE client_id=? AND hostel_id=?", (c, hid))
    d.commit()
    return jsonify(ok=True)

@app.post("/api/enquiry")
def booking_enquiry():
    d = request.get_json(silent=True) or {}
    hid = d.get("hostel_id")
    name = str(d.get("name", "")).strip()
    phone = str(d.get("phone", "")).strip()
    move_date = str(d.get("move_date", "")).strip()
    message = str(d.get("message", "")).strip()
    
    if not hid or not name or not phone:
        return jsonify(error="Hostel ID, Name, and Phone are required"), 400
        
    code = f"HM-{random.randint(10000, 99999)}"
    db().execute("INSERT INTO enquiries(code, hostel_id, name, phone, move_date, message) VALUES(?,?,?,?,?,?)",
                 (code, hid, name, phone, move_date, message))
    db().commit()
    return jsonify(ok=True, code=code, message="Booking inquiry submitted successfully! A manager will contact you shortly.")

@app.get("/api/hostels")
def all_hostels():
    return jsonify(results=[row_to_dict(r) for r in db().execute("SELECT * FROM hostels ORDER BY id")])

# ---------- Admin API ----------
def is_admin():
    return hmac.compare_digest(request.headers.get("X-Admin-Key", ""), ADMIN_KEY)

def clean(d):
    """Validate an admin hostel payload. Returns (values, error)."""
    try:
        name = str(d["name"]).strip()
        area = str(d.get("area", "")).strip()
        dist = float(d["distance_km"])
        rating = float(d["rating"])
        rooms = {k: float(v) for k, v in d["rooms"].items() if k in ROOMS and float(v) > 0}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None, "name, distance_km, rating and rooms {type: price} are required"
    if not name or not rooms or dist < 0 or not 0 <= rating <= 5:
        return None, "need a name, at least one room price, distance >= 0 and rating 0-5"
    ams = [a for a in d.get("amenities", []) if a in AMENITIES]
    try:
        lat = float(d["lat"]) if d.get("lat") not in (None, "") else None
        lng = float(d["lng"]) if d.get("lng") not in (None, "") else None
    except (TypeError, ValueError):
        return None, "lat and lng must be numbers"
    
    gender = str(d.get("gender", "coed")).lower()
    if gender not in GENDERS:
        gender = "coed"
    verified = 1 if d.get("verified", True) else 0
    phone = str(d.get("phone", "9876543210")).strip()
    cover_image = str(d.get("cover_image", IMAGES[0])).strip()
    safety_score = float(d.get("safety_score", 4.5))

    return dict(name=name, area=area, distance_km=dist, rating=rating, rooms=json.dumps(rooms),
                amenities=json.dumps(ams), about=str(d.get("about", ""))[:300], lat=lat, lng=lng,
                gender=gender, verified=verified, phone=phone, cover_image=cover_image, safety_score=safety_score), None

@app.get("/admin")
def admin_page():
    return render_template("admin.html", rooms=ROOMS, amenities=AMENITIES, genders=GENDERS)

@app.route("/api/admin/hostels", methods=["POST"])
@app.route("/api/admin/hostels/<int:hid>", methods=["PUT", "DELETE"])
def admin_write(hid=None):
    if not is_admin():
        return jsonify(error="invalid admin key"), 401
    d = db()
    if request.method == "DELETE":
        d.execute("DELETE FROM hostels WHERE id=?", (hid,))
        d.execute("DELETE FROM shortlist WHERE hostel_id=?", (hid,))
        d.commit()
        return jsonify(ok=True)
    v, err = clean(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    if request.method == "POST":
        cur = d.execute("INSERT INTO hostels(name,area,distance_km,rating,rooms,amenities,about,lat,lng,gender,verified,phone,cover_image,safety_score) VALUES(:name,:area,:distance_km,:rating,:rooms,:amenities,:about,:lat,:lng,:gender,:verified,:phone,:cover_image,:safety_score)", v)
        hid = cur.lastrowid
    else:
        if not d.execute("SELECT 1 FROM hostels WHERE id=?", (hid,)).fetchone():
            return jsonify(error="not found"), 404
        d.execute("UPDATE hostels SET name=:name,area=:area,distance_km=:distance_km,rating=:rating,rooms=:rooms,amenities=:amenities,about=:about,lat=:lat,lng=:lng,gender=:gender,verified=:verified,phone=:phone,cover_image=:cover_image,safety_score=:safety_score WHERE id=:id", {**v, "id": hid})
    if v["lat"] is None:
        d.execute("UPDATE hostels SET lat=?, lng=? WHERE id=?", (*place(hid, v["distance_km"]), hid))
    d.commit()
    return jsonify(ok=True, id=hid), (201 if request.method == "POST" else 200)

init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
