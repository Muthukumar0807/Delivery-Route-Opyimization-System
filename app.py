from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import sqlite3
import math

app = Flask(__name__)
app.secret_key = "devops-mini-project-secret"
DB = "delivery.db"
AVG_SPEED_KMPH = 40      # average vehicle speed
FUEL_COST_PER_KM = 7.5   # fuel cost in Rs per km


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        parcels INTEGER NOT NULL DEFAULT 1,
        is_depot INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        stops INTEGER NOT NULL,
        original_km REAL NOT NULL,
        optimized_km REAL NOT NULL,
        saving_pct REAL NOT NULL,
        sequence TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def haversine(a, b):
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def route_distance(route, points):
    return sum(haversine(points[route[i]], points[route[i + 1]])
               for i in range(len(route) - 1))


def nearest_neighbour(points):
    """Greedy tour that starts and ends at the depot (index 0)."""
    unvisited = set(range(1, len(points)))
    route = [0]
    while unvisited:
        last = route[-1]
        nxt = min(unvisited, key=lambda j: haversine(points[last], points[j]))
        route.append(nxt)
        unvisited.remove(nxt)
    return route + [0]


def two_opt(route, points):
    """Improve a tour by reversing segments while the distance keeps dropping."""
    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                new = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                if route_distance(new, points) < route_distance(best, points) - 1e-9:
                    best, improved = new, True
    return best


def optimize_route(points):
    original = list(range(len(points))) + [0]
    optimized = two_opt(nearest_neighbour(points), points)
    orig_km = route_distance(original, points)
    opt_km = route_distance(optimized, points)
    saving = (orig_km - opt_km) / orig_km * 100 if orig_km else 0.0
    return optimized, round(orig_km, 2), round(opt_km, 2), round(saving, 2)


def login_required():
    return session.get("logged_in")


def load_locations(conn):
    return conn.execute(
        "SELECT * FROM locations ORDER BY is_depot DESC, id").fetchall()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid username or password")
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    stops = conn.execute("SELECT COUNT(*) FROM locations WHERE is_depot=0").fetchone()[0]
    parcels = conn.execute("SELECT COALESCE(SUM(parcels),0) FROM locations").fetchone()[0]
    last = conn.execute("SELECT * FROM routes ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return render_template("dashboard.html", stops=stops, parcels=parcels, last=last)


@app.route("/locations", methods=["GET", "POST"])
def locations():
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    if request.method == "POST":
        try:
            is_depot = 1 if request.form.get("is_depot") else 0
            if is_depot:
                conn.execute("UPDATE locations SET is_depot=0")
            conn.execute(
                "INSERT INTO locations (name, latitude, longitude, parcels, is_depot) "
                "VALUES (?, ?, ?, ?, ?)",
                (request.form["name"], float(request.form["latitude"]),
                 float(request.form["longitude"]), int(request.form["parcels"]), is_depot))
            conn.commit()
            flash("Location added successfully")
        except sqlite3.IntegrityError:
            flash("Location already exists")
        except ValueError:
            flash("Enter valid latitude, longitude and parcel count")
    rows = load_locations(conn)
    conn.close()
    return render_template("locations.html", locations=rows)


@app.route("/locations/delete/<int:location_id>")
def delete_location(location_id):
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    conn.execute("DELETE FROM locations WHERE id=?", (location_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("locations"))


@app.route("/optimize")
def optimize():
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    rows = load_locations(conn)
    if len(rows) < 3 or not rows[0]["is_depot"]:
        conn.close()
        flash("Add one depot and at least two delivery locations")
        return redirect(url_for("locations"))
    points = [(r["latitude"], r["longitude"]) for r in rows]
    order, orig_km, opt_km, saving = optimize_route(points)
    legs = []
    for i in range(len(order) - 1):
        a, b = rows[order[i]], rows[order[i + 1]]
        km = haversine(points[order[i]], points[order[i + 1]])
        legs.append({"step": i + 1, "from": a["name"], "to": b["name"], "km": round(km, 2)})
    sequence = " -> ".join(rows[i]["name"] for i in order)
    conn.execute(
        "INSERT INTO routes (created_at, stops, original_km, optimized_km, saving_pct, sequence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), len(rows) - 1,
         orig_km, opt_km, saving, sequence))
    conn.commit()
    conn.close()
    hours = opt_km / AVG_SPEED_KMPH
    return render_template(
        "optimize.html", rows=rows, order=order, legs=legs,
        orig_km=orig_km, opt_km=opt_km, saving=saving,
        time=f"{int(hours)} h {round((hours % 1) * 60)} min",
        fuel=round(opt_km * FUEL_COST_PER_KM, 2),
        fuel_saved=round((orig_km - opt_km) * FUEL_COST_PER_KM, 2))


@app.route("/report")
def report():
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    routes = conn.execute("SELECT * FROM routes ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("report.html", routes=routes, rate=FUEL_COST_PER_KM)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
