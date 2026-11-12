#!/usr/bin/env python3
"""Capture the documentation screenshots of SD-Scripts GUI with Playwright.

Run it against a *demo* instance, never against your real data. It adds one job to
the queue (the queue stays paused, nothing is started) and removes it again right
after the run summary shot.

1. Start a server on its own data root, with a workspace that holds the SD 1.5 model,
   one image folder with captions and one finished training run:

       cd backend
       SD_SCRIPTS_GUI_DATA_ROOT=<demo-data> SD_SCRIPTS_GUI_ALLOWED_HOSTS=127.0.0.1,localhost \\
           .venv/Scripts/python.exe -m uvicorn app.main:app --port 8020 --workers 1

2. Install the browser once, then capture:

       uv run --with playwright python -m playwright install chromium
       uv run --with playwright python scripts/capture_screenshots.py \\
           --base-url http://127.0.0.1:8020 --out docs/images

Output: <out>/<locale>/<name>.png for locale en and th. Viewport 1440x900 at scale 1,
light theme, plus one dark hero shot and one 390x844 mobile shot per locale. Labels are
read from frontend/src/i18n/<locale>.ts, so the script clicks what the UI really calls
things. Absolute paths of the machine are replaced by --mask-root before each shot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ("en", "th")
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

JOB_NAME = "My first SD1.5 LoRA"
DEMO_DATASET = "demo-pattern"
DEMO_FOLDER = "smoke"
SEARCH_TERM = "optimizer"


# --------------------------------------------------------------------------- labels
def load_i18n(locale: str) -> dict[str, str]:
    """Reads the flat key/value pairs of frontend/src/i18n/<locale>.ts."""
    text = (ROOT / "frontend" / "src" / "i18n" / f"{locale}.ts").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"""^\s*'([\w.\-]+)':\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")""", re.M | re.S
    )
    table: dict[str, str] = {}
    for key, raw in pattern.findall(text):
        body = raw[1:-1]
        table[key] = re.sub(
            r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), body
        )
    return table


# --------------------------------------------------------------------------- page helpers
def settle(page: Page, extra_ms: int = 350) -> None:
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(extra_ms)


def new_context(
    browser: Browser, locale: str, theme: str, viewport: dict[str, int]
) -> BrowserContext:
    context = browser.new_context(
        viewport=viewport,
        device_scale_factor=1,
        locale="th-TH" if locale == "th" else "en-US",
        color_scheme="dark" if theme == "dark" else "light",
        reduced_motion="reduce",
    )
    # Both stores are zustand `persist` entries: {"state": {...}, "version": 1}.
    context.add_init_script(
        "try {"
        f"localStorage.setItem('sdgui:locale', JSON.stringify({{state: {{locale: '{locale}'}}, version: 1}}));"
        f"localStorage.setItem('sdgui:theme', JSON.stringify({{state: {{mode: '{theme}'}}, version: 1}}));"
        "} catch (e) {}"
    )
    return context


MASK_JS = """
([needles, replacement]) => {
  const fix = (s) => needles.reduce((acc, n) => acc.split(n).join(replacement), s);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const next = fix(node.nodeValue);
    if (next !== node.nodeValue) node.nodeValue = next;
  }
  document.querySelectorAll('input, textarea').forEach((el) => {
    const next = fix(el.value || '');
    if (next !== el.value) el.value = next;
  });
}
"""


class Shooter:
    def __init__(self, out: Path, locale: str, mask_needles: list[str], mask_to: str):
        self.dir = out / locale
        self.dir.mkdir(parents=True, exist_ok=True)
        self.needles = mask_needles
        self.mask_to = mask_to
        self.saved: list[str] = []

    def _mask(self, page: Page) -> None:
        # Park the pointer in a corner so no hover state ends up in a shot.
        page.mouse.move(DESKTOP["width"] - 4, 4)
        if self.needles:
            page.evaluate(MASK_JS, [self.needles, self.mask_to])

    def page(self, page: Page, name: str) -> None:
        self._mask(page)
        target = self.dir / f"{name}.png"
        page.screenshot(path=str(target))
        self.saved.append(str(target))
        print(f"  saved {target.relative_to(self.dir.parent.parent)}")

    def element(self, page: Page, locator, name: str) -> None:
        locator.scroll_into_view_if_needed()
        self._mask(page)
        target = self.dir / f"{name}.png"
        locator.screenshot(path=str(target))
        self.saved.append(str(target))
        print(f"  saved {target.relative_to(self.dir.parent.parent)}")


def open_app(
    page: Page, base: str, labels: dict[str, str], mobile: bool = False
) -> None:
    page.goto(base + "/")
    settle(page, 900)
    if mobile:
        # The sidebar lives in a sheet on narrow screens; the preset tabs prove the data loaded.
        page.get_by_role("tablist", name=labels["training.presets"]).wait_for()
    else:
        page.get_by_role("navigation", name=labels["nav.main"]).get_by_role(
            "button", name=labels["family.sd15"], exact=True
        ).wait_for()


def go_page(page: Page, labels: dict[str, str], key: str) -> None:
    """Clicks a sidebar item. The app has no URL routing."""
    nav = page.get_by_role("navigation", name=labels["nav.main"])
    nav.get_by_role("button", name=labels[key], exact=True).click()
    settle(page)
    page.evaluate("window.scrollTo(0, 0)")


def go_family(page: Page, labels: dict[str, str], family: str) -> None:
    nav = page.get_by_role("navigation", name=labels["nav.main"])
    nav.get_by_role("button", name=labels[f"family.{family}"], exact=True).click()
    settle(page)
    page.evaluate("window.scrollTo(0, 0)")


def fill_training_form(page: Page, labels: dict[str, str]) -> None:
    """Job name, dataset config and the suggested base model, like the quick start."""
    page.get_by_label(labels["project.name"], exact=False).first.fill(JOB_NAME)
    page.get_by_role(
        "combobox", name=re.compile(re.escape(labels["project.dataset"]))
    ).click()
    page.get_by_role("option", name=DEMO_DATASET).click()
    page.get_by_role("button", name=labels["model.useSuggested"]).first.click()
    # The command preview is debounced by 400 ms, then it asks the backend.
    page.get_by_text("train_network.py").first.wait_for()
    settle(page, 700)


def group(page: Page, title: str):
    return page.get_by_role("group", name=title, exact=True)


def capture_training(
    page: Page, shooter: Shooter, labels: dict[str, str], base: str
) -> None:
    go_family(page, labels, "sd15")
    fill_training_form(page, labels)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    shooter.page(page, "training-top")

    shooter.element(
        page, group(page, labels["section.modelFiles"]), "training-model-files"
    )

    # "All parameters" with a search: every group that has a match opens by itself.
    all_params = group(page, labels["section.all"])
    all_params.get_by_role("searchbox", name=labels["all.search"]).fill(SEARCH_TERM)
    page.wait_for_timeout(700)
    all_params.scroll_into_view_if_needed()
    shooter.page(page, "training-all-parameters")
    all_params.get_by_role("button", name=labels["common.clear"]).click()
    page.evaluate("window.scrollTo(0, 0)")

    # The workspace browser: the Browse button of the base model field.
    models = group(page, labels["section.modelFiles"])
    models.get_by_role("button", name=labels["field.browse"]).first.click()
    dialog = page.get_by_role("dialog", name=labels["browser.title"])
    dialog.wait_for()
    settle(page, 500)
    dialog.get_by_role("button", name=re.compile(r"^\s*models\b")).first.click()
    settle(page, 500)
    dialog.get_by_role("button", name=re.compile(r"^\s*checkpoints\b")).first.click()
    settle(page, 700)
    shooter.page(page, "workspace-browser")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # Add to queue (the queue stays paused), then show the run summary with the result.
    page.get_by_role("button", name=labels["aside.add"], exact=True).click()
    page.get_by_text(labels["aside.added"].replace("{name}", JOB_NAME)).wait_for()
    settle(page, 700)
    aside = page.get_by_role("complementary", name=labels["aside.title"])
    aside.evaluate(
        "el => { el.style.maxHeight = 'none'; el.style.overflow = 'visible'; el.style.position = 'static'; }"
    )
    shooter.element(page, aside, "training-aside")
    aside.evaluate(
        "el => { el.style.maxHeight = ''; el.style.overflow = ''; el.style.position = ''; }"
    )
    # The job was only needed for this shot; the next pages show the finished demo run.
    cleanup_queue(base, page)


def capture_datasets(page: Page, shooter: Shooter, labels: dict[str, str]) -> None:
    go_page(page, labels, "nav.datasets")
    page.get_by_role("tab", name=labels["datasets.tab.configs"]).click()
    page.get_by_text(DEMO_DATASET, exact=True).first.wait_for()
    settle(page, 500)
    shooter.page(page, "dataset-configs")

    page.get_by_role("button", name=labels["common.edit"], exact=True).first.click()
    editor = page.get_by_role("dialog", name=labels["dataset.edit"])
    editor.wait_for()
    settle(page, 700)
    shooter.page(page, "dataset-editor")
    editor.get_by_text(
        labels["dataset.subsetN"].replace("{n}", "1"), exact=True
    ).first.evaluate("el => el.scrollIntoView({ block: 'start' })")
    editor.evaluate("el => { el.scrollTop = el.scrollTop - 90; }")
    page.wait_for_timeout(300)
    shooter.page(page, "dataset-editor-subsets")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    page.get_by_role(
        "button", name=labels["dataset.validate"], exact=True
    ).first.click()
    report = page.get_by_role(
        "dialog", name=labels["dataset.validate.title"].replace("{name}", DEMO_DATASET)
    )
    report.wait_for()
    settle(page, 500)
    shooter.page(page, "dataset-validate")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    page.get_by_role("tab", name=labels["datasets.tab.folders"]).click()
    page.get_by_text(DEMO_FOLDER, exact=True).first.wait_for()
    settle(page, 500)
    shooter.page(page, "image-folders")

    page.get_by_role("button", name=re.compile(rf"^{DEMO_FOLDER}\b")).first.click()
    page.locator("img[alt$='.png']").first.wait_for()
    page.wait_for_function(
        "() => [...document.images].filter(i => i.alt.endsWith('.png')).every(i => i.complete && i.naturalWidth > 0)"
    )
    settle(page, 500)
    shooter.page(page, "image-folder")
    page.get_by_label(
        labels["folders.caption"], exact=True
    ).first.scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, 260)")
    page.wait_for_timeout(300)
    shooter.page(page, "image-folder-captions")


def capture_downloads(page: Page, shooter: Shooter, labels: dict[str, str]) -> None:
    go_page(page, labels, "nav.downloads")
    page.get_by_text("Stable Diffusion 1.5", exact=True).first.wait_for()
    settle(page, 500)
    shooter.page(page, "downloads")


def capture_jobs(page: Page, shooter: Shooter, labels: dict[str, str]) -> None:
    go_page(page, labels, "nav.jobs")
    completed = re.compile(
        re.escape(JOB_NAME) + ".*" + re.escape(labels["status.completed"]), re.I
    )
    page.get_by_role("button", name=completed).first.click()
    # The log is streamed into xterm; wait for the end of the run to appear.
    page.locator(".xterm-rows").get_by_text("model saved", exact=False).first.wait_for(
        timeout=15000
    )
    settle(page, 900)
    shooter.page(page, "jobs")
    outputs = (
        page.locator("[data-slot=card]")
        .filter(has=page.get_by_role("heading", name=labels["jobs.artifacts"]))
        .first
    )
    # The outputs heading may live in the same card as the job header; fall back to it.
    if outputs.count() == 0:
        outputs = (
            page.locator("[data-slot=card]")
            .filter(has_text=labels["jobs.downloadAll"])
            .first
        )
    shooter.element(page, outputs, "jobs-outputs")
    log_card = (
        page.locator("[data-slot=card]")
        .filter(has=page.get_by_role("heading", name=labels["jobs.logs"], exact=True))
        .first
    )
    shooter.element(page, log_card, "jobs-log")


def capture_settings_about(
    page: Page, shooter: Shooter, labels: dict[str, str]
) -> None:
    go_page(page, labels, "nav.settings")
    page.get_by_text(labels["settings.env.title"], exact=True).first.wait_for()
    settle(page, 600)
    shooter.page(page, "settings")
    env_card = (
        page.locator("[data-slot=card]")
        .filter(has=page.get_by_role("heading", name=labels["settings.env.title"]))
        .first
    )
    shooter.element(page, env_card, "settings-environment")

    go_page(page, labels, "nav.about")
    settle(page, 600)
    shooter.page(page, "about")


def cleanup_queue(base: str, page: Page) -> None:
    """Removes the job this script queued: cancel, then delete."""
    jobs = page.request.get(base + "/api/training/jobs").json()
    for job in jobs:
        if job["name"] == JOB_NAME and job["status"] == "queued":
            page.request.post(f"{base}/api/training/jobs/{job['id']}/cancel")
            page.request.delete(f"{base}/api/training/jobs/{job['id']}")
            print(f"  removed the queued job {job['id']}")


def mask_needles(base: str, browser: Browser) -> list[str]:
    """Absolute checkout folder of the server, in the forms the UI may print."""
    request = browser.new_context().request
    status = request.get(base + "/api/system/status").json()
    workspace = status["workspace_root"].replace("\\", "/").rstrip("/")
    root = workspace.rsplit("/", 1)[0]
    return [root, root.replace("/", "\\")]


def run(base: str, out: Path, mask_to: str, only: list[str]) -> list[str]:
    saved: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        needles = mask_needles(base, browser)
        for locale in only:
            labels = load_i18n(locale)
            print(f"[{locale}] light desktop")
            context = new_context(browser, locale, "light", DESKTOP)
            page = context.new_page()
            shooter = Shooter(out, locale, needles, mask_to)
            open_app(page, base, labels)
            capture_training(page, shooter, labels, base)
            capture_datasets(page, shooter, labels)
            capture_downloads(page, shooter, labels)
            capture_jobs(page, shooter, labels)
            capture_settings_about(page, shooter, labels)
            context.close()

            print(f"[{locale}] dark hero")
            context = new_context(browser, locale, "dark", DESKTOP)
            page = context.new_page()
            hero = Shooter(out, locale, needles, mask_to)
            open_app(page, base, labels)
            go_family(page, labels, "sd15")
            fill_training_form(page, labels)
            page.evaluate("window.scrollTo(0, 0)")
            hero.page(page, "hero-dark")
            context.close()

            print(f"[{locale}] mobile")
            context = new_context(browser, locale, "light", MOBILE)
            page = context.new_page()
            mobile = Shooter(out, locale, needles, mask_to)
            open_app(page, base, labels, mobile=True)
            settle(page, 700)
            mobile.page(page, "training-mobile")
            context.close()

            saved += shooter.saved + hero.saved + mobile.saved
        browser.close()
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8020")
    parser.add_argument(
        "--out", default="docs/images", help="folder that receives <locale>/<name>.png"
    )
    parser.add_argument(
        "--mask-root",
        default="C:/sd-gui",
        help="text that replaces the server's checkout folder in the shots",
    )
    parser.add_argument(
        "--locale", choices=LOCALES, action="append", help="limit to one locale"
    )
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = Path.cwd() / out
    saved = run(
        args.base_url.rstrip("/"), out, args.mask_root, args.locale or list(LOCALES)
    )
    print(json.dumps({"saved": len(saved)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
