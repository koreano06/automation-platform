"""Local browser acceptance check with an isolated database and disposable credentials.

Requires frontend dependencies, backend [dev,runner], and Chromium.
Run from repository root: python scripts/browser_smoke.py
"""

import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def wait_for(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("O servidor de teste encerrou antes de responder.")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("O servidor de teste não iniciou.")


def main():
    with tempfile.TemporaryDirectory(prefix="automation-qa-") as directory:
        os.environ["DATABASE_URL"] = (
            "sqlite:///" + (Path(directory) / "qa.db").as_posix()
        )
        os.environ["ALLOWED_ORIGINS"] = '["http://127.0.0.1:5178"]'
        os.environ["VITE_API_BASE_URL"] = "http://127.0.0.1:8765"
        os.environ["ASSETS_DIR"] = str(Path(directory) / "assets")
        os.environ["ARTIFACTS_DIR"] = str(Path(directory) / "artifacts")
        from alembic import command
        from app.cli import seed_demo
        from app.database.migrations import migration_config
        from app.database.session import SessionLocal, engine
        from app.security import create_user

        command.upgrade(migration_config(), "head")
        password = secrets.token_urlsafe(24)
        with SessionLocal() as db:
            admin = create_user(db, "qa-admin", password, "admin")
            db.commit()
            seed_demo(db, admin)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        processes = []
        artifacts = ROOT / "docs" / "verification"
        artifacts.mkdir(parents=True, exist_ok=True)
        try:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8765",
                    ],
                    cwd=ROOT / "backend",
                    env=os.environ.copy(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            )
            processes.append(
                subprocess.Popen(
                    [
                        "node",
                        str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "5178",
                    ],
                    cwd=ROOT / "frontend",
                    env=os.environ.copy(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            )
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "app.worker"],
                    cwd=ROOT / "backend",
                    env=os.environ.copy(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            )
            wait_for("http://127.0.0.1:8765/health", processes[0])
            wait_for("http://127.0.0.1:5178", processes[1])
            from playwright.sync_api import expect, sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                failures = []
                page.on(
                    "pageerror", lambda error: failures.append(str(error).replace(password, "[hidden]")[:300])
                )
                page.goto("http://127.0.0.1:5178")
                page.wait_for_timeout(1500)
                if not page.get_by_label("Usuário", exact=True).count():
                    print("QA startup page errors:", failures)
                    print("QA startup page text:", page.locator("body").inner_text()[:1200])
                page.get_by_label("Usuário", exact=True).fill("qa-admin")
                page.get_by_label("Senha", exact=True).fill(password)
                page.get_by_role("button", name="Entrar no workspace").click()
                expect(
                    page.get_by_role("heading", name="Construtor visual", exact=True)
                ).to_be_visible()
                assert page.locator(".studio-hero").count() == 0
                page.get_by_label("Plataforma de destino").select_option(
                    label="Portal de Treinamento · simulation"
                )
                pilot_id = page.get_by_label("Plataforma de destino").input_value()
                page.get_by_role("button", name="Duplicar etapa 2", exact=True).click()
                page.get_by_role("button", name="Testar etapa 1", exact=True).click()
                page.locator(".step-test-panel").get_by_role(
                    "button", name="Reconhecer alvo", exact=True
                ).click()
                expect(page.locator(".step-test-panel .status")).to_have_text(
                    "Concluída", timeout=20000
                )
                expect(page.locator(".step-test-panel")).to_contain_text(
                    "Resultado simulado"
                )
                page.get_by_role("button", name="Fechar teste", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Captura visual", exact=True)
                ).to_be_visible()
                page.screenshot(
                    path=str(artifacts / "studio-desktop.png"), full_page=True
                )
                # Choose an image region and persist only the button reference.
                from PIL import Image, ImageDraw

                screenshot = Path(directory) / "pilot-screen.png"
                image = Image.new("RGB", (800, 450), "#eef0f7")
                draw = ImageDraw.Draw(image)
                draw.rectangle((100, 100, 240, 150), fill="#7655df")
                draw.text((120, 120), "CONFIRM", fill="white")
                image.save(screenshot)
                page.get_by_label("Captura da plataforma", exact=True).set_input_files(
                    screenshot
                )
                canvas = page.locator("canvas")
                expect(canvas).to_be_visible()
                page.wait_for_function("document.querySelector('canvas').width === 800")
                canvas.scroll_into_view_if_needed()
                bounds = canvas.bounding_box()
                page.mouse.move(
                    bounds["x"] + bounds["width"] * 0.12,
                    bounds["y"] + bounds["height"] * 0.21,
                )
                page.mouse.down()
                page.mouse.move(
                    bounds["x"] + bounds["width"] * 0.31,
                    bounds["y"] + bounds["height"] * 0.35,
                )
                page.mouse.up()
                page.get_by_role(
                    "button", name="Adicionar ação ao fluxo", exact=True
                ).click()
                expect(
                    page.get_by_text("Reconhecimento do botão adicionado.", exact=False)
                ).to_be_visible()
                page.get_by_role(
                    "button", name="Salvar nova versão", exact=True
                ).click()
                expect(
                    page.get_by_text("Nova versão salva como rascunho.", exact=False)
                ).to_be_visible()
                # The newest version is validated before it can be used.
                page.locator(".version-row").first.get_by_role(
                    "button", name="Validar", exact=True
                ).click()
                expect(
                    page.get_by_text("Versão validada e disponível", exact=False)
                ).to_be_visible()
                page.get_by_role("button", name="Nova solicitação", exact=True).click()
                page.get_by_label("Nome completo", exact=True).fill("Pessoa QA")
                page.get_by_label("E-mail corporativo", exact=True).fill(
                    "qa@example.invalid"
                )
                page.get_by_label("Departamento", exact=True).fill("Testes")
                page.get_by_label("Matrícula", exact=True).fill("QA-1")
                page.get_by_role("checkbox", name="Portal de Treinamento").check()
                page.get_by_role("checkbox", name="Diretório de Teste").check()
                for select in page.locator(".target-fields select").all():
                    select.select_option("Colaborador")
                page.get_by_role(
                    "button", name="Revisar solicitação", exact=False
                ).click()
                expect(
                    page.get_by_role("heading", name="Revise a solicitação")
                ).to_be_visible()
                page.get_by_role(
                    "button", name="Confirmar solicitação", exact=True
                ).click()
                expect(
                    page.get_by_role("heading", name="Detalhes da execução")
                ).to_be_visible()
                expect(page.locator(".detail-summary .status")).to_have_text(
                    "Parcial", timeout=20000
                )
                page.get_by_role("button", name="Repetir falha", exact=True).click()
                expect(page.locator(".detail-summary .status")).to_have_text(
                    "Concluída", timeout=15000
                )
                page.screenshot(
                    path=str(artifacts / "execution-desktop.png"), full_page=True
                )
                page.get_by_role("button", name="Plataformas", exact=True).click()
                # Reproduce the observed stale API response without touching user data.
                stale_route = "**/platforms/" + pilot_id
                page.route(
                    stale_route,
                    lambda route: (
                        route.fulfill(
                            status=405,
                            content_type="application/json",
                            body='{"detail":"Method Not Allowed"}',
                        )
                        if route.request.method == "DELETE"
                        else route.continue_()
                    ),
                )
                page.once("dialog", lambda dialog: dialog.accept())
                page.get_by_role(
                    "button",
                    name="Excluir plataforma Portal de Treinamento",
                    exact=True,
                ).click()
                expect(page.get_by_role("alert")).to_contain_text(
                    "API em execução está desatualizada"
                )
                expect(
                    page.get_by_role(
                        "heading", name="Portal de Treinamento", exact=True
                    )
                ).to_be_visible()
                page.unroute(stale_route)
                page.once("dialog", lambda dialog: dialog.accept())
                page.get_by_role(
                    "button",
                    name="Excluir plataforma Portal de Treinamento",
                    exact=True,
                ).click()
                expect(
                    page.get_by_role(
                        "heading", name="Portal de Treinamento", exact=True
                    )
                ).to_have_count(0)
                page.get_by_role("button", name="Execuções", exact=True).click()
                page.locator(".table-link").first.click()
                expect(page.locator(".detail-summary .status")).to_have_text(
                    "Concluída"
                )
                expect(
                    page.get_by_role(
                        "heading", name="Portal de Treinamento", exact=True
                    )
                ).to_be_visible()
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(
                    path=str(artifacts / "execution-mobile.png"), full_page=True
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                ), "Layout overflow on mobile"
                assert not failures, failures
                page.get_by_role("button", name="Diagnóstico", exact=True).click()
                expect(
                    page.get_by_role(
                        "heading", name="Diagnóstico dos serviços", exact=True
                    )
                ).to_be_visible()
                expect(
                    page.get_by_text("Executor conectado", exact=True)
                ).to_be_visible()
                page.get_by_role("button", name="Sair", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Acesse sua conta", exact=True)
                ).to_be_visible()
                browser.close()
            print(
                "Browser acceptance passed: login, studio, image crop, version/validation, multi-platform request, partial failure/retry, stale DELETE 405 feedback, successful deletion with history, mobile."
            )
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            engine.dispose()


if __name__ == "__main__":
    main()
