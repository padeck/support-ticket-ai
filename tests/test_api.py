def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_create_ticket_success(client):
    resp = client.post(
        "/api/tickets",
        json={"request": "Mein Benutzerkonto ist gesperrt und ich kann mich nicht anmelden."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticketId"].startswith("T-")
    assert data["category"] == "account_access"
    assert data["priority"] in ("low", "medium", "high", "critical")
    assert data["assignedTeam"] == "identity-operations"
    assert isinstance(data["summary"], str) and data["summary"]
    assert data["status"] in ("open", "manual_review_required")
    assert data["aiProvider"] == "simulated"


def test_create_ticket_empty_request(client):
    resp = client.post("/api/tickets", json={"request": ""})
    assert resp.status_code == 422


def test_create_ticket_too_long(client):
    resp = client.post("/api/tickets", json={"request": "x" * 5001})
    assert resp.status_code == 422


def test_create_incident_critical_manual_review(client):
    resp = client.post(
        "/api/tickets",
        json={"request": "Seit heute Morgen ist das Produktivsystem nicht erreichbar, alle Nutzer sind betroffen."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "incident"
    assert data["priority"] == "critical"
    assert data["status"] == "manual_review_required"
    assert data["assignedTeam"] == "platform-operations"


def test_get_ticket_success(client):
    create_resp = client.post("/api/tickets", json={"request": "Mein Konto ist gesperrt."})
    ticket_id = create_resp.json()["ticketId"]

    resp = client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json()["ticketId"] == ticket_id


def test_get_ticket_not_found(client):
    resp = client.get("/api/tickets/T-unknown")
    assert resp.status_code == 404


def test_list_tickets_no_filter(client):
    client.post("/api/tickets", json={"request": "Mein Konto ist gesperrt."})
    client.post("/api/tickets", json={"request": "Wie ändere ich meine Rechnungsadresse?"})

    resp = client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["tickets"]) == 2


def test_list_tickets_with_status_filter(client):
    client.post(
        "/api/tickets",
        json={"request": "Seit heute ist das Produktivsystem komplett nicht erreichbar."},
    )
    client.post("/api/tickets", json={"request": "Wie ändere ich meine Rechnungsadresse?"})

    resp = client.get("/api/tickets?status=manual_review_required")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["tickets"][0]["status"] == "manual_review_required"


def test_list_tickets_with_category_filter(client):
    client.post("/api/tickets", json={"request": "Mein Konto ist gesperrt."})
    client.post("/api/tickets", json={"request": "Wie ändere ich meine Rechnungsadresse?"})

    resp = client.get("/api/tickets?category=billing")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["tickets"][0]["category"] == "billing"


def test_patch_ticket_status(client):
    create_resp = client.post("/api/tickets", json={"request": "Mein Konto ist gesperrt."})
    ticket_id = create_resp.json()["ticketId"]

    resp = client.patch(f"/api/tickets/{ticket_id}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_invalid_status(client):
    create_resp = client.post("/api/tickets", json={"request": "Mein Konto ist gesperrt."})
    ticket_id = create_resp.json()["ticketId"]

    resp = client.patch(f"/api/tickets/{ticket_id}", json={"status": "bogus"})
    assert resp.status_code == 422


def test_patch_ticket_not_found(client):
    resp = client.patch("/api/tickets/T-unknown", json={"status": "resolved"})
    assert resp.status_code == 404
