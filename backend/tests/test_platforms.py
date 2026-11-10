from tests.helpers import automation, platform


def test_authentication_and_role_boundaries(client, operator):
    assert client.get("/platforms").status_code == 401
    assert operator.post("/platforms", json={"name": "Proibida"}).status_code == 403
    assert operator.get("/audit-events").status_code == 403
    assert operator.get("/auth/users").status_code == 403


def test_platform_edit_persists_and_requires_revalidation(admin):
    item = platform(admin)
    definition = automation(admin, item["id"])
    body = {key: value for key, value in item.items() if key not in {"id", "created_at"}}
    body["active"] = False
    for field in body["fields"]:
        field.pop("id")
        field.pop("position")
    assert admin.put(f"/platforms/{item['id']}", json=body).status_code == 200
    assert not admin.get(f"/platforms/{item['id']}").json()["active"]
    assert admin.get(f"/platforms/{item['id']}/automations").json()[0]["status"] == "draft"
    assert admin.post(f"/automations/{definition['id']}/validate").status_code == 409


def test_versioning_and_validation(admin):
    item = platform(admin)
    automation(admin, item["id"])
    automation(admin, item["id"])
    versions = admin.get(f"/platforms/{item['id']}/automations").json()
    assert [version["version"] for version in versions] == [2, 1]
    assert [version["status"] for version in versions] == ["validated", "archived"]
    invalid = automation(
        admin,
        item["id"],
        [{"action": "fill", "locator": "#name", "data_ref": "employee.name"}],
        False,
    )
    assert admin.post(f"/automations/{invalid['id']}/validate").status_code == 422
    invalid_ref = automation(
        admin,
        item["id"],
        [
            {"action": "fill", "locator": "#name", "data_ref": "employee.unknown"},
            {"action": "assert", "locator": "#status", "success_condition": "ok"},
        ],
        False,
    )
    assert admin.post(f"/automations/{invalid_ref['id']}/validate").status_code == 422


def test_secret_fields_and_raw_validation_input_are_not_exposed(admin):
    secret = "very-sensitive-test-value"
    response = admin.post("/platforms", json={"name": "Teste", "config": {"api_token": secret}})
    assert response.status_code == 422
    assert secret not in response.text
    assert (
        admin.post(
            "/platforms", json={"name": "Teste", "fields": [{"key": "password", "label": "Senha"}]}
        ).status_code
        == 422
    )


def test_not_found_duplicate_and_csrf(admin):
    assert admin.get("/platforms/missing").status_code == 404
    platform(admin)
    assert admin.post("/platforms", json={"name": "Portal piloto"}).status_code == 409
    token = admin.headers.pop("X-CSRF-Token")
    assert admin.post("/platforms", json={"name": "Sem CSRF"}).status_code == 403
    admin.headers["X-CSRF-Token"] = token


def test_changes_are_audited_without_passwords(admin, factory):
    item = platform(admin)
    automation(admin, item["id"])
    events = admin.get("/audit-events").json()
    assert {"platform.saved", "automation.version_created", "automation.validated"} <= {
        row["action"] for row in events
    }
    assert "Test-only-passphrase" not in str(events)
    assert "password_hash" not in str(events)


def test_login_lock_and_logout(client):
    for _ in range(5):
        assert (
            client.post(
                "/auth/login", json={"username": "operator", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post("/auth/login", json={"username": "operator", "password": "wrong"}).status_code
        == 429
    )


def test_user_management_revokes_access(admin, operator):
    assert (
        admin.post(
            "/auth/users",
            json={
                "username": "new-operator",
                "password": "test-created-password",
                "role": "operator",
            },
        ).status_code
        == 201
    )
    assert admin.post("/auth/users/operator-id/disable").status_code == 200
    assert operator.get("/platforms").status_code == 401
    assert admin.post("/auth/users/admin-id/disable").status_code == 409
    assert admin.post("/auth/logout").status_code == 204
    assert admin.get("/auth/me").status_code == 401
