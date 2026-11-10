def platform(client, name="Portal piloto", fail=False, mode="simulation"):
    response = client.post(
        "/platforms",
        json={
            "name": name,
            "mode": mode,
            "config": {"simulate_failure": fail},
            "fields": [
                {
                    "key": "profile",
                    "label": "Perfil",
                    "field_type": "select",
                    "options": ["Colaborador", "Gestor"],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def automation(client, platform_id, steps=None, validate=True):
    response = client.post(
        f"/platforms/{platform_id}/automations",
        json={
            "name": "Cadastro",
            "steps": steps
            or [
                {"action": "open_page", "value": "https://pilot.invalid/new"},
                {"action": "fill", "locator": "#email", "data_ref": "employee.email"},
                {"action": "click_button", "button_text": "Cadastrar"},
                {"action": "assert", "locator": "#status", "success_condition": "Concluído"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    if validate:
        response = client.post(f"/automations/{result['id']}/validate")
        assert response.status_code == 200, response.text
    return result


def payload(platforms, email="colaborador@example.invalid"):
    return {
        "employee": {
            "name": "Pessoa de Teste",
            "email": email,
            "department": "Qualidade",
            "employee_id": "T-001",
        },
        "targets": [
            {"platform_id": item["id"], "fields": {"profile": "Colaborador"}} for item in platforms
        ],
    }


def submit(client, platforms, key="test-request-0001", email="colaborador@example.invalid"):
    response = client.post(
        "/provisioning-requests", json=payload(platforms, email), headers={"Idempotency-Key": key}
    )
    assert response.status_code in {200, 202}, response.text
    return response.json()
