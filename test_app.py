import pytest
import app as route_app

POINTS = [(9.1717, 77.8700), (8.7642, 78.1348), (8.7139, 77.7567), (9.4533, 77.7924)]


@pytest.fixture
def client(tmp_path):
    route_app.DB = str(tmp_path / "test.db")
    route_app.app.config["TESTING"] = True
    route_app.init_db()
    with route_app.app.test_client() as c:
        yield c


def login(c):
    return c.post("/", data={"username": "admin", "password": "admin123"}, follow_redirects=True)


def test_haversine_zero_and_known():
    assert route_app.haversine(POINTS[0], POINTS[0]) == 0
    assert 50 < route_app.haversine(POINTS[0], POINTS[1]) < 60


def test_route_visits_all_and_returns_to_depot():
    order, orig, opt, saving = route_app.optimize_route(POINTS)
    assert order[0] == 0 and order[-1] == 0
    assert sorted(order[:-1]) == list(range(len(POINTS)))
    assert opt <= orig and saving >= 0


def test_login_success_and_failure(client):
    assert b"Dashboard" in login(client).data
    bad = client.post("/", data={"username": "x", "password": "y"}, follow_redirects=True)
    assert b"Invalid username or password" in bad.data


def test_protected_page_redirects(client):
    assert client.get("/optimize").status_code == 302


def test_add_location_and_optimize(client):
    login(client)
    names = ["Depot", "Thoothukudi", "Tirunelveli", "Sivakasi"]
    for i, (n, p) in enumerate(zip(names, POINTS)):
        data = {"name": n, "latitude": p[0], "longitude": p[1], "parcels": 3}
        if i == 0:
            data["is_depot"] = "on"
        client.post("/locations", data=data)
    res = client.get("/optimize")
    assert res.status_code == 200 and b"Optimized Distance" in res.data
    assert b"Thoothukudi" in client.get("/report").data
