"""Tests for HostelMatch API, scoring algorithm, search, booking inquiry, and database logic."""
import os, json, tempfile, pytest
from app import app, init_db, parse, score, ROOMS, AMENITIES

@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config["TESTING"] = True
    os.environ["DB_PATH"] = db_path
    import app as app_module
    app_module.DB = db_path
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
        
    os.close(db_fd)
    os.unlink(db_path)

def test_parse_input():
    p, err = parse({"budget": 10000, "max_distance": 5, "rooms": ["single"], "amenities": ["wifi"], "gender": "boys", "q": "Scholar"})
    assert err is None
    assert p["budget"] == 10000
    assert p["max_distance"] == 5
    assert p["rooms"] == ["single"]
    assert p["amenities"] == ["wifi"]
    assert p["gender"] == "boys"
    assert p["q"] == "scholar"

    p, err = parse({"budget": -50, "max_distance": 5})
    assert err == "budget and max_distance must be greater than 0"
    
    p, err = parse({"budget": "invalid", "max_distance": 5})
    assert err == "budget and max_distance must be numbers"

def test_scoring_algorithm():
    h = {
        "distance_km": 1.0,
        "rating": 4.5,
        "rooms": {"single": 8000, "double": 6000},
        "amenities": ["wifi", "meals", "ac"]
    }
    p = {
        "budget": 10000,
        "max_distance": 5.0,
        "rooms": ["single"],
        "amenities": ["wifi", "meals"]
    }
    total, breakdown = score(h, p)
    assert 0 <= total <= 100
    assert breakdown["budget"] == 25.0
    assert breakdown["amenities"] == 30.0
    assert breakdown["room"] == 10.0
    assert breakdown["rating"] == 9.0

def test_recommend_endpoint(client):
    res = client.post("/api/recommend", json={"budget": 12000, "max_distance": 4, "sort": "match"})
    assert res.status_code == 200
    data = res.get_json()
    assert "results" in data
    assert data["count"] > 0
    for r in data["results"]:
        assert r["price"] <= 12000
        assert r["distance_km"] <= 4

def test_search_and_gender_filter(client):
    # Search by keyword "Scholar"
    res = client.post("/api/recommend", json={"budget": 15000, "max_distance": 5, "q": "Scholar"})
    data = res.get_json()
    assert data["count"] > 0
    assert "Scholar" in data["results"][0]["name"]

    # Filter by gender "girls"
    res = client.post("/api/recommend", json={"budget": 20000, "max_distance": 8, "gender": "girls"})
    data = res.get_json()
    assert data["count"] > 0
    for h in data["results"]:
        assert h["gender"] in ("girls", "coed")

def test_booking_enquiry_endpoint(client):
    payload = {
        "hostel_id": 1,
        "name": "Alex Smith",
        "phone": "9876543210",
        "move_date": "2026-10-15"
    }
    res = client.post("/api/enquiry", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "code" in data
    assert data["code"].startswith("HM-")

def test_shortlist_flow(client):
    cid = "test-client-123"
    assert client.get("/api/shortlist").status_code == 400
    
    res = client.post("/api/shortlist/1", headers={"X-Client-Id": cid})
    assert res.status_code == 200
    
    res = client.get("/api/shortlist", headers={"X-Client-Id": cid})
    data = res.get_json()
    assert len(data["results"]) == 1
    assert data["results"][0]["id"] == 1
    
    client.delete("/api/shortlist/1", headers={"X-Client-Id": cid})
    res = client.get("/api/shortlist", headers={"X-Client-Id": cid})
    assert len(res.get_json()["results"]) == 0

def test_admin_operations(client):
    payload = {
        "name": "New Test Hostel",
        "area": "Center",
        "distance_km": 1.5,
        "rating": 4.8,
        "rooms": {"single": 9000},
        "amenities": ["wifi", "ac"],
        "gender": "coed",
        "verified": True,
        "phone": "9998887770"
    }
    assert client.post("/api/admin/hostels", json=payload).status_code == 401
    
    res = client.post("/api/admin/hostels", json=payload, headers={"X-Admin-Key": "change-me"})
    assert res.status_code == 201
    hid = res.get_json()["id"]
    
    payload["name"] = "Updated Test Hostel"
    res = client.put(f"/api/admin/hostels/{hid}", json=payload, headers={"X-Admin-Key": "change-me"})
    assert res.status_code == 200
    
    res = client.delete(f"/api/admin/hostels/{hid}", headers={"X-Admin-Key": "change-me"})
    assert res.status_code == 200
