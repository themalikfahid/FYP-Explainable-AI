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
    if not exe and Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome").exists():
        exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def test_full_user_journey(server):
    expect.set_options(timeout=15000)  # CPU-bound SHAP can be slow on loaded machines
    SHOTS.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    base = server["base"]
    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = _launch(p)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # landing
        page.goto(base + "/")
        expect(page.get_by_role("heading", name=re.compile("reasons behind"))).to_be_visible()
        expect(page.locator(".importance li").first).to_be_visible()
        page.screenshot(path=SHOTS / "01_landing_desktop.png", full_page=True)

        # protected route redirects to login
        page.goto(base + "/history")
        expect(page).to_have_url(re.compile("/login$"))

        # 1. register (with a validation error first)
        page.goto(base + "/register")
        page.get_by_label("Full name").fill("E2E Synthetic User")
        page.get_by_label("Email").fill("e2e.user@example.com")
        page.get_by_label(re.compile("^Password")).fill("weakpass")
        page.get_by_label("Confirm password").fill("weakpass")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_text("Include at least one letter and one number.")).to_be_visible()
        page.get_by_label(re.compile("^Password")).fill("Synthetic123")
        page.get_by_label("Confirm password").fill("Synthetic123")
        page.get_by_role("button", name="Create account").click()

        # 2. log in
        expect(page.get_by_text("Account created. Log in to continue.")).to_be_visible()
        page.get_by_label("Email").fill("e2e.user@example.com")
        page.get_by_label("Password").fill("Synthetic123")
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("heading", name="Hello, E2E")).to_be_visible()
        page.screenshot(path=SHOTS / "02_dashboard_empty.png", full_page=True)

        # 3. diabetes assessment: submit empty first -> validation
        page.get_by_role("link", name="Diabetes screen").first.click()
        page.get_by_role("button", name="Get my result").click()
        expect(page.get_by_role("alert").first).to_contain_text("Please fix")
        page.locator("#f-age").fill("45")
        page.locator("#f-gender_male").select_option("0")
        page.get_by_role("button", name='Set all symptoms to "No"').click()
        for name in ("polyuria", "polydipsia", "sudden_weight_loss", "weakness", "visual_blurring"):
            page.locator(f"input[name='{name}'][value='1']").check(force=True)
        for fid, v in [("height_cm", "165"), ("weight_kg", "72"), ("sleep_hours", "6"),
                       ("activity_minutes_week", "60"), ("fruit_veg_servings_day", "2"), ("alcohol_units_week", "0")]:
            page.locator(f"#f-{fid}").fill(v)
        page.locator("#f-smoking").select_option("0")
        # errors from the first empty submit disappear as fields are completed
        expect(page.get_by_text("This field is required.")).to_have_count(0)
        page.screenshot(path=SHOTS / "03_diabetes_form.png", full_page=True)
        page.get_by_role("button", name="Get my result").click()

        # 5-7. real result, SHAP, recommendations
        expect(page).to_have_url(re.compile(r"/history/\d+$"), timeout=30000)
        expect(page.get_by_role("heading", name="Why the model said this")).to_be_visible()
        expect(page.locator(".ledger-row").first).to_be_visible()
        expect(page.get_by_role("heading", name="What you can do next")).to_be_visible()
        expect(page.locator(".scorecard").first).to_contain_text("BMI")
        risk_text = page.locator(".result-head .risk").inner_text()
        assert risk_text in ("Low risk", "Moderate risk", "High risk")
        page.screenshot(path=SHOTS / "04_diabetes_result.png", full_page=True)
        diabetes_url = page.url

        # 8. PDF download
        with page.expect_download() as dl:
            page.get_by_role("button", name="Download PDF report").click()
        path = DOWNLOADS / dl.value.suggested_filename
        dl.value.save_as(path)
        assert path.read_bytes()[:5] == b"%PDF-"

        # 4. heart assessment (optional fields left blank)
        page.get_by_role("link", name="Heart screen").click()
        page.locator("#f-age").fill("61")
        page.locator("#f-sex").select_option("1")
        page.locator("#f-cp").select_option("4")
        page.get_by_label(re.compile("Resting blood pressure")).fill("145")
        page.locator("#f-fbs").select_option("0") if page.locator("select#f-fbs").count() else \
            page.locator("input[name='fbs'][value='0']").check(force=True)
        page.locator("#f-restecg").select_option("2")
        page.get_by_label(re.compile("Maximum heart rate")).fill("112")
        page.locator("input[name='exang'][value='1']").check(force=True)
        page.get_by_label(re.compile("ST depression")).fill("2.4")
        page.get_by_label(re.compile("Include lifestyle details")).uncheck()
        page.get_by_role("button", name="Get my result").click()
        expect(page).to_have_url(re.compile(r"/history/\d+$"), timeout=30000)
        expect(page.locator(".banner.warn")).to_contain_text("Not provided")
        page.get_by_label("Explain").select_option("0")
        expect(page.locator(".ledger-outcome")).to_contain_text("No significant disease")
        page.get_by_label("Explain").select_option("any")
        page.screenshot(path=SHOTS / "05_heart_result.png", full_page=True)

        # 9. history shows both
        page.get_by_role("link", name="History").click()
        expect(page.locator("table.history tbody tr")).to_have_count(2)
        page.screenshot(path=SHOTS / "06_history.png", full_page=True)

        # tools page and model info
        page.get_by_role("link", name="BMI & lifestyle").click()
        for fid, v in [("height_cm", "170"), ("weight_kg", "70"), ("sleep_hours", "8"),
                       ("activity_minutes_week", "200"), ("fruit_veg_servings_day", "5"), ("alcohol_units_week", "0")]:
            page.locator(f"#f-{fid}").fill(v)
        page.locator("#f-smoking").select_option("0")
        page.get_by_role("button", name="Calculate").click()
        expect(page.locator(".scorecard").nth(1)).to_contain_text("100")
        page.get_by_role("link", name="How the models work").click()
        expect(page.get_by_role("heading", name="Held-out test results")).to_be_visible()
        page.screenshot(path=SHOTS / "07_model_info.png", full_page=True)

        # mobile layout check
        mob = browser.new_context(viewport={"width": 390, "height": 844}, storage_state=ctx.storage_state())
        mpage = mob.new_page()
        mpage.goto(base + "/")
        mpage.screenshot(path=SHOTS / "08_landing_mobile.png", full_page=True)
        assert mpage.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal scroll on mobile"
        mob.close()

        # 10. log out, 11. protected resources rejected
        page.get_by_role("button", name="Log out").click()
        expect(page.get_by_text("You have been logged out.")).to_be_visible()
        page.goto(diabetes_url)
        expect(page).to_have_url(re.compile("/login$"))
        status = page.evaluate("fetch('/api/predictions').then(r => r.status)")
        assert status == 401

        # mobile result page using a fresh login
        mob = browser.new_context(viewport={"width": 390, "height": 844})
        mp = mob.new_page()
        mp.goto(base + "/login")
        mp.get_by_label("Email").fill("e2e.user@example.com")
        mp.get_by_label("Password").fill("Synthetic123")
        mp.get_by_role("button", name="Log in").click()
        expect(mp.get_by_role("heading", name="Hello, E2E")).to_be_visible()
        mp.goto(diabetes_url)
        expect(mp.locator(".ledger-row").first).to_be_visible()
        wide = mp.evaluate("""[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1)
            .slice(0, 8).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))""")
        assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"horizontal scroll on result page: {wide}"
        mp.screenshot(path=SHOTS / "09_result_mobile.png", full_page=True)
        mob.close()
        browser.close()
    assert not [e for e in console_errors if "401" not in e and "Failed to load resource" not in e], console_errors
