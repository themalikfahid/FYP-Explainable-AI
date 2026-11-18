"""Browser end-to-end journey (Playwright + Chromium) against the real backend
serving the built frontend. Synthetic user and inputs only.

Prerequisites: models trained (python -m ml.train) and frontend built (npm run build).
    python -m pytest e2e -q
Screenshots: artifacts/qa/screenshots/
Set CHROMIUM_PATH to use a specific Chromium/Chrome executable.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "artifacts" / "qa" / "screenshots"
DOWNLOADS = ROOT / "artifacts" / "qa" / "downloads"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        pytest.fail("Frontend not built. Run `npm run build` in frontend/.")
    tmp = tmp_path_factory.mktemp("e2e")
    port = _free_port()
    env = {**os.environ, "APP_ENV": "test", "SECRET_KEY": "e2e-secret-key-long-enough-0123456789abcdef",
           "DATABASE_URL": f"sqlite:///{(tmp / 'e2e.db').as_posix()}", "EMAIL_MODE": "file",
           "EMAIL_OUTBOX_DIR": str(tmp / "outbox"), "CORS_ORIGINS": f"http://127.0.0.1:{port}",
           # explicit, so values exported by other test modules (tests/conftest.py) cannot leak in
           "FRONTEND_DIST": str(ROOT / "frontend" / "dist"), "MODELS_DIR": str(ROOT / "artifacts" / "models"),
           "LOGIN_RATE_LIMIT_PER_MINUTE": "10", "PREDICT_RATE_LIMIT_PER_MINUTE": "30"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1",
                             "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield {"base": base, "outbox": tmp / "outbox"}
    proc.terminate()
    proc.wait(10)


def _launch(p):
    exe = os.environ.get("CHROMIUM_PATH")
    args = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    return p.chromium.launch(executable_path=exe, args=args) if exe else p.chromium.launch(args=args)


def _seg(page, group: str, label: str):
    page.get_by_role("group", name=group).get_by_role("button", name=label, exact=True).click()


def _no_hscroll(page, where: str):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"horizontal scroll on {where}"


def test_full_user_journey(server):
    expect.set_options(timeout=20000)  # CPU-bound SHAP can be slow on loaded machines
    SHOTS.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    base = server["base"]
    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = _launch(p)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        # landing: honest metrics load from the API
        page.goto(base + "/")
        expect(page.get_by_role("heading", name=re.compile("Screening you can"))).to_be_visible()
        expect(page.get_by_text("Diabetes screen \u00b7 cross-validated accuracy")).to_be_visible()
        expect(page.locator(".metric-band .v").first).not_to_have_text("\u2026")
        page.wait_for_timeout(1800)
        page.screenshot(path=SHOTS / "01_landing_desktop.png")
        page.screenshot(path=SHOTS / "01b_landing_full.png", full_page=True)

        # protected route redirects to login
        page.goto(base + "/app/history")
        expect(page).to_have_url(re.compile("/login$"))

        # register with validation error first
        page.goto(base + "/register")
        page.get_by_label("Full name").fill("E2E Synthetic User")
        page.get_by_label("Email").fill("e2e.user@example.com")
        page.get_by_label("Password", exact=True).fill("weakpass")
        page.get_by_label("Confirm password").fill("weakpass")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("alert").first).to_be_visible()
        page.screenshot(path=SHOTS / "02_register_error.png")
        page.get_by_label("Password", exact=True).fill("Synthetic123")
        page.get_by_label("Confirm password").fill("Synthetic123")
        page.get_by_role("button", name="Create account").click()

        # login
        expect(page.get_by_text("Account created. Please sign in.")).to_be_visible()
        page.get_by_label("Email").fill("e2e.user@example.com")
        page.get_by_label("Password").fill("Synthetic123")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name=re.compile("Hello, E2E"))).to_be_visible()
        expect(page.get_by_text("Run your first assessment")).to_be_visible()
        page.screenshot(path=SHOTS / "03_dashboard_empty.png")

        # diabetes wizard: validation on step 1, then complete
        page.get_by_role("link", name="New assessment").first.click()
        expect(page.get_by_role("heading", name="New assessment")).to_be_visible()
        page.screenshot(path=SHOTS / "04_assess_chooser.png")
        page.get_by_role("link", name=re.compile("Diabetes symptom screen")).click()
        page.get_by_role("button", name="Continue").click()
        expect(page.get_by_text("Required").first).to_be_visible()
        page.locator("#f-age").fill("45")
        _seg(page, "Sex", "Female") if page.get_by_role("group", name="Sex").count() else _seg(page, "Gender", "Female")
        page.get_by_role("button", name="Continue").click()
        for t in ("Polyuria", "Polydipsia", "Sudden weight loss", "Weakness", "Visual blurring"):
            page.get_by_role("button", name=re.compile("^" + t, re.I)).first.click()
        page.screenshot(path=SHOTS / "05_diabetes_symptoms.png")
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name=re.compile("Add lifestyle details")).click()
        for fid, v in [("h", "165"), ("w", "72"), ("s", "6"), ("a", "60"), ("fv", "2"), ("al", "0")]:
            page.locator(f"#{fid}").fill(v)
        page.get_by_role("button", name="Continue").click()
        expect(page.get_by_role("heading", name="Review and run")).to_be_visible()
        page.get_by_role("button", name="Run assessment").click()

        # result
        expect(page).to_have_url(re.compile(r"/app/result/\d+$"), timeout=40000)
        expect(page.get_by_role("heading", name=re.compile("Why this score"))).to_be_visible()
        expect(page.locator(".shap-row").first).to_be_visible()
        expect(page.get_by_role("heading", name=re.compile("Personalised next steps"))).to_be_visible()
        expect(page.get_by_text(re.compile("model confidence")).first).to_be_visible()
        expect(page.get_by_text(re.compile("Confident result|Inconclusive result")).first).to_be_visible()
        expect(page.get_by_text("Lifestyle score").first).to_be_visible()
        page.wait_for_timeout(1500)
        page.screenshot(path=SHOTS / "06_diabetes_result.png", full_page=True)
        diabetes_url = page.url

        # what-if simulator
        page.get_by_label("Add an input to change").select_option(label="Age")
        page.get_by_label("Age", exact=True).last.fill("70")
        page.get_by_role("button", name="Run scenario").click()
        expect(page.get_by_text("Scenario", exact=True)).to_be_visible()
        page.screenshot(path=SHOTS / "07_whatif.png", full_page=True)

        # PDF
        with page.expect_download() as dl:
            page.get_by_role("button", name="PDF report").click()
        path = DOWNLOADS / dl.value.suggested_filename
        dl.value.save_as(path)
        assert path.read_bytes()[:5] == b"%PDF-"

        # heart wizard (optional fields left blank)
        page.goto(base + "/app/assess/heart")
        page.locator("#f-age").fill("61")
        _seg(page, "Sex", "Male")
        page.locator("#f-cp").select_option(label="No chest pain (asymptomatic)") if page.locator("select#f-cp").count() else _seg(page, "Chest pain type", "No chest pain (asymptomatic)")
        page.get_by_role("button", name="Continue").click()
        page.locator("#f-trestbps").fill("145")
        _seg(page, "Fasting blood sugar > 120 mg/dL", "No")
        page.get_by_role("button", name="Continue").click()
        _seg(page, "Resting ECG result", "Left ventricular hypertrophy")
        page.locator("#f-thalach").fill("112")
        _seg(page, "Exercise-induced angina", "Yes")
        page.locator("#f-oldpeak").fill("2.4")
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Run assessment").click()
        expect(page).to_have_url(re.compile(r"/app/result/\d+$"), timeout=40000)
        expect(page.get_by_text(re.compile("SHAP . any heart disease"))).to_be_visible()
        expect(page.get_by_text("Class probabilities").first).to_be_visible()
        page.wait_for_timeout(1500)
        page.screenshot(path=SHOTS / "08_heart_result.png", full_page=True)

        # coronary artery (Z-Alizadeh) wizard
        page.goto(base + "/app/assess/cad")
        page.locator("#f-age").fill("62")
        _seg(page, "Sex", "Male")
        page.locator("#f-bmi").fill("28.5")
        for label, ans in [("Diabetes (diagnosed)", "No"), ("High blood pressure (diagnosed)", "Yes"), ("Current smoker", "Yes"),
                           ("Family history of heart disease", "No"), ("High cholesterol / lipids (diagnosed)", "Yes")]:
            _seg(page, label, ans)
        page.get_by_role("button", name="Continue").click()
        for label, ans in [("Typical chest pain (angina)", "Yes"), ("Atypical chest pain", "No"), ("Non-anginal chest pain", "No"), ("Shortness of breath", "Yes")]:
            _seg(page, label, ans)
        page.locator("#f-function_class").select_option(label="2 - moderate")
        page.get_by_role("button", name="Continue").click()
        page.locator("#f-bp_systolic").fill("148")
        page.locator("#f-pulse").fill("78")
        for label in ("Q wave on ECG", "ST elevation on ECG", "ST depression on ECG", "T-wave inversion on ECG", "Left ventricular hypertrophy on ECG"):
            _seg(page, label, "Yes" if "depression" in label else "No")
        page.get_by_role("button", name="Continue").click()
        page.locator("#f-ldl").fill("150")
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Run assessment").click()
        expect(page).to_have_url(re.compile(r"/app/result/\d+$"), timeout=40000)
        expect(page.get_by_text("Coronary artery screen").first).to_be_visible()
        expect(page.get_by_text(re.compile("SHAP . positive screen"))).to_be_visible()
        page.wait_for_timeout(1500)
        page.screenshot(path=SHOTS / "08b_cad_result.png", full_page=True)

        # ECG heartbeat classifier
        page.goto(base + "/app/assess/ecg")
        page.get_by_role("button", name="Ventricular", exact=True).click()
        expect(page.get_by_text("Ventricular ectopic beat").first).to_be_visible(timeout=30000)
        expect(page.get_by_text("Beat signal and what the model relied on")).to_be_visible()
        page.wait_for_timeout(1000)
        page.screenshot(path=SHOTS / "08c_ecg_result.png", full_page=True)

        # Type 1 pattern check
        page.goto(base + "/app/assess/t1d")
        page.locator("#t1d-age").fill("9")
        for t in ("Frequent urination", "Extreme thirst", "Unexplained weight loss", "Unusual tiredness", "New bedwetting"):
            page.get_by_role("button", name=re.compile(t)).first.click()
        page.get_by_role("button", name="Check pattern").click()
        expect(page.get_by_text("Pattern score").first).to_be_visible()
        expect(page.get_by_text("Strong match").first).to_be_visible()
        page.screenshot(path=SHOTS / "09_t1d_result.png", full_page=True)

        # dashboard now has data
        page.get_by_role("link", name="Dashboard").first.click()
        expect(page.get_by_text("Risk trend").first).to_be_visible()
        page.wait_for_timeout(1200)
        page.screenshot(path=SHOTS / "10_dashboard.png", full_page=True)

        # history
        page.get_by_role("link", name="History").first.click()
        expect(page.locator("table tbody tr")).to_have_count(3)
        page.screenshot(path=SHOTS / "11_history.png")

        # model transparency
        page.get_by_role("link", name="Model transparency").first.click()
        expect(page.get_by_text("Accuracy vs coverage").first).to_be_visible()
        page.wait_for_timeout(1200)
        page.screenshot(path=SHOTS / "12_models_diabetes.png", full_page=True)
        page.get_by_role("group", name="Model").get_by_role("button", name="Heart").click()
        expect(page.get_by_text("Exact grade (0")).to_be_visible()
        page.wait_for_timeout(1200)
        page.screenshot(path=SHOTS / "13_models_heart.png", full_page=True)

        # tools
        page.get_by_role("link", name="Health tools").first.click()
        page.locator("#tb-h").fill("170")
        page.locator("#tb-w").fill("70")
        page.get_by_role("button", name="Calculate BMI").click()
        expect(page.get_by_text(re.compile("BMI 24"))).to_be_visible()
        page.screenshot(path=SHOTS / "14_tools.png")

        # settings
        page.get_by_role("link", name="Settings").first.click()
        expect(page.get_by_role("heading", name="Settings")).to_be_visible()
        page.screenshot(path=SHOTS / "15_settings.png")

        # not found
        page.goto(base + "/nope")
        expect(page.get_by_text("This page doesn't exist")).to_be_visible()

        # mobile layout
        mob = browser.new_context(viewport={"width": 390, "height": 844})
        mp = mob.new_page()
        mp.goto(base + "/")
        mp.wait_for_timeout(1500)
        _no_hscroll(mp, "landing")
        mp.screenshot(path=SHOTS / "16_landing_mobile.png", full_page=True)
        mp.goto(base + "/login")
        mp.get_by_label("Email").fill("e2e.user@example.com")
        mp.get_by_label("Password").fill("Synthetic123")
        mp.get_by_role("button", name="Sign in").click()
        expect(mp.get_by_role("heading", name=re.compile("Hello, E2E"))).to_be_visible()
        for route, shot in [("/app", "17_dashboard_mobile"), (diabetes_url.replace(base, ""), "18_result_mobile"), ("/app/models", "19_models_mobile"), ("/app/assess/heart", "20_form_mobile")]:
            mp.evaluate("p => { history.pushState({}, '', p); dispatchEvent(new PopStateEvent('popstate')); }", route)
            mp.wait_for_timeout(2000)
            assert "/login" not in mp.url, f"mobile redirected to login for {route}"
            mp.screenshot(path=SHOTS / f"{shot}.png", full_page=True)
            _no_hscroll(mp, route)
        mob.close()

        # sign out, protected resources rejected
        page.goto(base + "/app")
        page.get_by_role("button", name="Sign out").first.click()
        page.goto(base + diabetes_url.replace(base, ""))
        expect(page).to_have_url(re.compile("/login"))
        status = page.evaluate("fetch('/api/predictions').then(r => r.status)")
        assert status == 401
        browser.close()
    real = [e for e in console_errors if "401" not in e and "Failed to load resource" not in e and "WebGL" not in e and "GPU stall" not in e]
    assert not real, real
