"""
INTEGRATION TESTS for main.py

These spin up your ACTUAL FastAPI app (via TestClient) and send real
HTTP requests through it — routes, dependencies, and the database
(an isolated test one, see conftest.py) all run for real. This checks
that all the pieces work correctly TOGETHER, not just in isolation.
"""


# ===== HELPERS =====
# Small helpers to avoid repeating "register + login" in every test.
def _get_token(client, username, role="staff", password="testpass123"):
    client.post("/register", json={
        "username": username,
        "password": password,
        "role": role,
    })
    response = client.post("/login", data={
        "username": username,
        "password": password,
    })
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ===== AUTH ENDPOINT TESTS =====

def test_register_new_user_succeeds(client):
    response = client.post("/register", json={
        "username": "newuser",
        "password": "pass123",
        "role": "staff",
    })
    assert response.status_code == 200
    assert response.json()["username"] == "newuser"


def test_register_duplicate_username_fails(client):
    client.post("/register", json={"username": "dupuser", "password": "pass123", "role": "staff"})
    response = client.post("/register", json={"username": "dupuser", "password": "pass456", "role": "staff"})
    assert response.status_code == 400


def test_login_correct_credentials_returns_token(client):
    client.post("/register", json={"username": "loginuser", "password": "correctpass", "role": "staff"})
    response = client.post("/login", data={"username": "loginuser", "password": "correctpass"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_returns_401(client):
    client.post("/register", json={"username": "loginuser2", "password": "correctpass", "role": "staff"})
    response = client.post("/login", data={"username": "loginuser2", "password": "wrongpass"})
    assert response.status_code == 401


# ===== PRODUCT ENDPOINT TESTS =====

def test_create_product_without_token_returns_401(client):
    response = client.post("/products", json={
        "name": "Test Item", "sku": "TEST-001", "category": "Test",
        "price": 10.0, "quantity": 5,
    })
    assert response.status_code == 401


def test_create_product_with_valid_token_succeeds(client):
    token = _get_token(client, "admin1", role="admin")
    response = client.post(
        "/products",
        json={"name": "Test Item", "sku": "TEST-001", "category": "Test", "price": 10.0, "quantity": 5},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["sku"] == "TEST-001"


def test_get_products_returns_created_product(client):
    token = _get_token(client, "admin2", role="admin")
    client.post(
        "/products",
        json={"name": "Item A", "sku": "SKU-A", "category": "Cat", "price": 5.0, "quantity": 10},
        headers=_auth_headers(token),
    )
    response = client.get("/products", headers=_auth_headers(token))
    assert response.status_code == 200
    skus = [p["sku"] for p in response.json()]
    assert "SKU-A" in skus


# ===== SCAN ENDPOINT TESTS =====

def test_scan_out_reduces_quantity_correctly(client):
    token = _get_token(client, "admin3", role="admin")
    client.post(
        "/products",
        json={"name": "Scan Item", "sku": "SCAN-001", "category": "Cat",
              "price": 5.0, "quantity": 20, "min_buffer": 5},
        headers=_auth_headers(token),
    )
    response = client.put(
        "/products/scan/SCAN-001?quantity=5&direction=out",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 15


def test_scan_out_more_than_available_fails(client):
    """This is the negative-stock guard we discussed earlier —
    should be blocked with a 400, not allowed to go negative."""
    token = _get_token(client, "admin4", role="admin")
    client.post(
        "/products",
        json={"name": "Low Item", "sku": "LOW-001", "category": "Cat", "price": 5.0, "quantity": 3},
        headers=_auth_headers(token),
    )
    response = client.put(
        "/products/scan/LOW-001?quantity=10&direction=out",
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_scan_unknown_sku_returns_404(client):
    token = _get_token(client, "admin5", role="admin")
    response = client.put(
        "/products/scan/DOES-NOT-EXIST?quantity=1&direction=in",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


# ===== DELETE ENDPOINT TESTS (role-based access control) =====

def test_delete_product_as_admin_succeeds(client):
    token = _get_token(client, "admin6", role="admin")
    client.post(
        "/products",
        json={"name": "Delete Me", "sku": "DEL-001", "category": "Cat", "price": 5.0, "quantity": 5},
        headers=_auth_headers(token),
    )
    response = client.delete("/products/DEL-001", headers=_auth_headers(token))
    assert response.status_code == 200


def test_delete_product_as_staff_returns_403(client):
    """This is the role-based access control check — staff should NOT
    be able to delete products, only admins."""
    admin_token = _get_token(client, "admin7", role="admin")
    client.post(
        "/products",
        json={"name": "Protected", "sku": "PROT-001", "category": "Cat", "price": 5.0, "quantity": 5},
        headers=_auth_headers(admin_token),
    )

    staff_token = _get_token(client, "staffuser1", role="staff")
    response = client.delete("/products/PROT-001", headers=_auth_headers(staff_token))
    assert response.status_code == 403


# ===== FORECAST ENDPOINT TESTS =====

def test_forecast_with_insufficient_data_returns_400(client):
    """A brand-new product with no transaction history shouldn't be
    forecastable yet — needs at least 5 'out' transactions."""
    token = _get_token(client, "admin8", role="admin")
    client.post(
        "/products",
        json={"name": "New Item", "sku": "NEW-001", "category": "Cat", "price": 5.0, "quantity": 50},
        headers=_auth_headers(token),
    )
    response = client.get("/forecast/NEW-001")
    assert response.status_code == 400


def test_forecast_unknown_sku_returns_404(client):
    response = client.get("/forecast/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_forecast_with_enough_data_returns_prediction(client):
    """Scans a product 'out' 5 times (the minimum required), then checks
    that a real forecast with predictions comes back."""
    token = _get_token(client, "admin9", role="admin")
    client.post(
        "/products",
        json={"name": "Forecast Item", "sku": "FC-001", "category": "Cat",
              "price": 5.0, "quantity": 100, "min_buffer": 10},
        headers=_auth_headers(token),
    )

    for _ in range(5):
        client.put(
            "/products/scan/FC-001?quantity=2&direction=out",
            headers=_auth_headers(token),
        )

    response = client.get("/forecast/FC-001")
    assert response.status_code == 200
    body = response.json()
    assert "forecast_next_7_days" in body
    assert len(body["forecast_next_7_days"]) == 7
    assert "recommendation" in body
