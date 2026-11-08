"""The pages load what they need: every local file a page links to exists, and a page whose scripts use the shared
components (AGroupRecords in records.js, AGroupUI in ui.js) also loads them first."""
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
PAGES = sorted(FRONTEND.glob("*.html"))
EXTERNAL = re.compile(r"^(https?:|mailto:|tel:|data:|javascript:|#)")
SHARED = {"AGroupRecords": "js/records.js", "AGroupUI": "js/ui.js"}


def references(page):
    text = page.read_text(encoding="utf-8")
    for ref in re.findall(r'(?:src|href)="([^"]+)"', text):
        if EXTERNAL.match(ref) or "${" in ref:
            continue
        path = ref.split("#")[0].split("?")[0]
        if path:
            yield ref, path


def scripts(page):
    return re.findall(r'<script[^>]+src="([^"]+)"', page.read_text(encoding="utf-8"))


def test_there_are_pages_to_check():
    assert {"index.html", "portal.html", "inbox.html", "ui-kit.html"} <= {p.name for p in PAGES}


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_local_file_a_page_links_to_exists(page):
    missing = [ref for ref, path in references(page) if not (FRONTEND / path).exists()]
    assert missing == []


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_pages_load_the_shared_components_they_use(page):
    loaded = scripts(page)
    for position, src in enumerate(loaded):
        script = FRONTEND / src
        if not script.exists() or src in SHARED.values():
            continue
        code = script.read_text(encoding="utf-8")
        for name, library in SHARED.items():
            if f"window.{name}" in code or re.search(rf"\b{name}\.", code):
                assert library in loaded[:position], f"{src} uses {name} but {page.name} does not load {library} before it"


def test_the_ui_kit_shows_every_shared_component():
    code = (FRONTEND / "js" / "ui.js").read_text(encoding="utf-8")
    exported = re.search(r"window\.AGroupUI = \{([^}]+)\}", code).group(1)
    kit = (FRONTEND / "js" / "ui-kit.js").read_text(encoding="utf-8")
    components = ["listPage", "uploadWidget", "periodSelector", "trendChart", "projectCard", "imageGallery",
                  "categoryPicker", "ratingForm", "ratingDisplay", "formView", "recordPage"]
    for name in components:
        assert name in exported, f"ui.js does not export {name}"
        assert f"UI.{name}" in kit, f"ui-kit.html does not show {name}"
