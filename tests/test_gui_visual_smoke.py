"""
Playwright automated smoke test and visual QA capture.
Verifies all 10 views in the Casebook GUI, ensures zero console errors,
confirms zero external runtime requests, tests actions, and captures screenshots.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from gui.server import app

SCREENSHOTS_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.2)  # Give server time to bind
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def test_playwright_smoke_and_screenshots(server_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        pages_to_test = [
            ("today", "/today"),
            ("inbox", "/inbox"),
            ("people", "/people"),
            ("normal", "/normal"),
            ("rehearsal", "/rehearsal"),
            ("ledger", "/ledger"),
            ("safeguards", "/safeguards"),
            ("evidence", "/evidence"),
            ("styleguide", "/styleguide"),
        ]

        viewports = [
            ("mobile", {"width": 390, "height": 844}),
            ("desktop", {"width": 1280, "height": 900}),
            ("wide", {"width": 1920, "height": 1080}),
        ]

        themes = ["light", "dark"]

        # Track external requests and console errors
        external_requests = []
        console_errors = []

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def on_request(request):
            url = request.url
            if not url.startswith("http://127.0.0.1") and not url.startswith("http://localhost"):
                external_requests.append(url)

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        page.on("request", on_request)
        page.on("console", on_console)

        # 1. Fetch first alert ID from API to test Case View
        page.goto(f"{server_url}/api/inbox")
        inbox_data = json.loads(page.text_content("pre") or "{}")
        alerts = inbox_data.get("alerts", [])
        assert len(alerts) > 0, "Expected alerts in inbox"
        first_alert_id = alerts[0]["alert_id"]

        all_pages = pages_to_test + [("case", f"/case/{first_alert_id}")]

        # 2. Test Actions on Case page
        page.goto(f"{server_url}/case/{first_alert_id}")
        page.wait_for_selector("#feedback-form-container", timeout=5000)
        # Select verdict and submit
        page.select_option("#verdict-select", "benign_expected")
        page.fill("#notes-textarea", "Automated QA verification - reviewed and verified.")
        page.click("#btn-submit-verdict")
        page.wait_for_selector("#form-msg", timeout=5000)

        # 3. Test Ledger Action
        page.goto(f"{server_url}/ledger")
        page.wait_for_selector(".ledger-table", timeout=5000)
        page.click("button:has-text('Check the Chain')")
        page.wait_for_selector("#ledger-status-container .context-callout, #ledger-status-container .attention-callout", timeout=5000)

        # 4. Multi-viewport & Multi-theme Screenshot Capture
        for page_name, path in all_pages:
            for theme in themes:
                for vp_name, vp_size in viewports:
                    context.close()
                    context = browser.new_context(
                        viewport=vp_size,
                        color_scheme="dark" if theme == "dark" else "light",
                    )
                    page = context.new_page()
                    page.on("request", on_request)
                    page.on("console", on_console)

                    page.goto(f"{server_url}{path}")
                    page.wait_for_timeout(350)  # Allow SVG render

                    # Force dark attribute if dark theme
                    if theme == "dark":
                        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
                        page.wait_for_timeout(100)

                    screenshot_path = SCREENSHOTS_DIR / f"{page_name}_{theme}_{vp_name}.png"
                    page.screenshot(path=str(screenshot_path), full_page=False)

        browser.close()

        # Strict checks
        assert len(external_requests) == 0, f"Found external requests: {external_requests}"
        assert len(console_errors) == 0, f"Found console errors: {console_errors}"

