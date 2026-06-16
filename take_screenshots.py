"""
Capture screenshots of every app page for the README.
Run from project root with the server already on http://127.0.0.1:8000
"""
import os
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT  = "docs/screenshots"
os.makedirs(OUT, exist_ok=True)

VIEWPORT = {"width": 1280, "height": 800}

USER = "demouser"
PASS = "demo1234"
EMAIL = "demo@example.com"


def shot(page, name: str):
    path = f"{OUT}/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  saved {path}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport=VIEWPORT)
    page = ctx.new_page()

    # ── 1. Login page ─────────────────────────────────────────────────────────
    print("Login page...")
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    shot(page, "login")

    # ── 2. Register page ──────────────────────────────────────────────────────
    print("Register page...")
    page.goto(f"{BASE}/register")
    page.wait_for_load_state("networkidle")
    shot(page, "register")

    # ── 3. Login (try first; if it fails, register then login) ───────────────
    print("Logging in as demo user...")
    page.goto(f"{BASE}/login")
    page.fill("#username", USER)
    page.fill("#password", PASS)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")

    if "/login" in page.url:
        # Login failed — user doesn't exist yet; register first
        print("  Not found, registering...")
        page.goto(f"{BASE}/register")
        page.fill("#username", USER)
        page.fill("#email", EMAIL)
        page.fill("#password", PASS)
        page.fill("#confirm_password", PASS)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
    print(f"  Landed on: {page.url}")

    # ── 4. Dashboard ──────────────────────────────────────────────────────────
    print("Dashboard...")
    page.wait_for_load_state("networkidle")
    shot(page, "dashboard")

    # ── 5. Upload page (empty) ────────────────────────────────────────────────
    print("Upload page...")
    page.goto(f"{BASE}/upload")
    page.wait_for_load_state("networkidle")
    shot(page, "upload")

    # ── 6. Upload the sample PDF ──────────────────────────────────────────────
    print("Uploading sample PDF...")
    page.goto(f"{BASE}/upload")
    page.wait_for_load_state("networkidle")
    page.fill("#title", "RAG Forensics Demo Doc")
    page.fill("#category", "demo")
    page.fill("#namespace", "demo-docs")
    pdf_path = os.path.abspath("app/my.pdf")
    page.set_input_files("#file", pdf_path)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle", timeout=60000)
    shot(page, "upload_success")

    # ── 7. Ask page (empty form) ───────────────────────────────────────────────
    print("Ask page (empty)...")
    page.goto(f"{BASE}/ask")
    page.wait_for_load_state("networkidle")
    shot(page, "ask")

    # ── 8. Ask page with answer ────────────────────────────────────────────────
    print("Asking a question (waits for OpenAI)...")
    page.goto(f"{BASE}/ask")
    page.wait_for_load_state("networkidle")
    page.fill("#question", "What is this document about?")
    # select the namespace we just uploaded to
    page.select_option("#namespace", "demo-docs")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle", timeout=30000)
    shot(page, "ask_answer")

    # ── 9. Eval page ───────────────────────────────────────────────────────────
    print("Eval page...")
    page.goto(f"{BASE}/eval")
    page.wait_for_load_state("networkidle")
    shot(page, "eval")

    browser.close()

print("\nAll screenshots saved to docs/screenshots/")
