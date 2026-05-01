#!/usr/bin/env python3
"""Pre-publish audit for the SwiftTerm hosted website."""

from __future__ import annotations

import argparse
import html.parser
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_HOSTED_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DOMAIN = "swiftterm.app"
EXPECTED_BASE_URL = f"https://{EXPECTED_DOMAIN}"

PAGES = {
    "index.html": f"{EXPECTED_BASE_URL}/",
    "faq.html": f"{EXPECTED_BASE_URL}/faq.html",
    "whats-new.html": f"{EXPECTED_BASE_URL}/whats-new.html",
    "press.html": f"{EXPECTED_BASE_URL}/press.html",
    "support.html": f"{EXPECTED_BASE_URL}/support.html",
    "privacy.html": f"{EXPECTED_BASE_URL}/privacy.html",
}

REQUIRED_FILES = [
    ".nojekyll",
    "404.html",
    "CNAME",
    "README.md",
    "robots.txt",
    "sitemap.xml",
    "site.css",
    "site.webmanifest",
    "assets/swiftterm-social-preview.png",
    "assets/swiftterm-hero-console.png",
    "assets/swiftterm-wordmark.svg",
    "media-kit/swiftterm-media-kit.zip",
    "screenshots/swiftterm-app-icon.png",
    "screenshots/swiftterm-ipad-workspace.png",
    "screenshots/swiftterm-iphone-terminal.png",
    "screenshots/swiftterm-iphone-files.png",
]

REQUIRED_MEDIA_KIT_MEMBERS = {
    "README.md",
    "swiftterm-app-icon-1024.png",
    "swiftterm-wordmark.svg",
    "swiftterm-social-preview.png",
    "swiftterm-hero-console.png",
    "swiftterm-ipad-workspace.png",
    "swiftterm-iphone-terminal.png",
    "swiftterm-iphone-files.png",
    "swiftterm-one-sheet.md",
    "swiftterm-press-release.md",
    "swiftterm-press-release.txt",
}

FORBIDDEN_PATTERNS = {
    "placeholder copy": r"TODO|PLACEHOLDER|YOUR_|example\.com",
    "automatic remote action claim": r"automatically\s+(opens?|unlocks?|fixes?|deploys?)|one\s+tap\s+(opens?|unlocks?|fixes?|deploys?)",
    "Apple endorsement implication": r"endorsed\s+by\s+Apple|official\s+Apple\s+partner",
    "unconfigured press mailbox": r"press@swiftterm\.app",
}

REQUIRED_COPY_TERMS = [
    "iPhone",
    "iPad",
    "Keychain",
    "Ed25519",
    "SFTP",
    "opt-in",
    "support@swiftterm.app",
    "privacy@swiftterm.app",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


class ReferenceParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.images: list[dict[str, str]] = []
        self.meta: dict[tuple[str, str], str] = {}
        self.visible_text: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        values = {key: value or "" for key, value in attrs}
        if values.get("href"):
            self.refs.append(values["href"])
        if values.get("src"):
            self.refs.append(values["src"])
        if tag == "img":
            self.images.append(values)
        if tag == "meta":
            if values.get("property"):
                self.meta[("property", values["property"])] = values.get("content", "")
            if values.get("name"):
                self.meta[("name", values["name"])] = values.get("content", "")
        if tag == "link" and values.get("rel") == "canonical":
            self.meta[("link", "canonical")] = values.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text and not self._ignored_depth:
            self.visible_text.append(text)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def add(checks: list[Check], name: str, ok: bool, detail: str = "") -> None:
    checks.append(Check(name, ok, detail if not ok else ""))


def parse_html(path: Path) -> ReferenceParser:
    parser = ReferenceParser()
    parser.feed(read(path))
    return parser


def is_external(ref: str) -> bool:
    return ref.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:", "javascript:", "//"))


def check_required_files(hosted_root: Path, checks: list[Check]) -> None:
    missing = [rel for rel in [*PAGES.keys(), *REQUIRED_FILES] if not (hosted_root / rel).exists()]
    add(checks, "required launch files exist", not missing, ", ".join(missing))

    cname = read(hosted_root / "CNAME").strip() if (hosted_root / "CNAME").exists() else ""
    add(checks, "CNAME points to swiftterm.app", cname == EXPECTED_DOMAIN, cname)

    robots = read(hosted_root / "robots.txt") if (hosted_root / "robots.txt").exists() else ""
    add(checks, "robots.txt references production sitemap", f"{EXPECTED_BASE_URL}/sitemap.xml" in robots)

    sitemap = read(hosted_root / "sitemap.xml") if (hosted_root / "sitemap.xml").exists() else ""
    missing_urls = [url for url in PAGES.values() if url not in sitemap]
    add(checks, "sitemap.xml includes launch pages", not missing_urls, ", ".join(missing_urls))


def check_local_references(hosted_root: Path, checks: list[Check]) -> None:
    missing: list[str] = []
    for html_path in sorted(hosted_root.rglob("*.html")):
        parser = parse_html(html_path)
        for ref in parser.refs:
            if is_external(ref):
                continue
            path = urllib.parse.unquote(urllib.parse.urlparse(ref).path)
            if not path:
                continue
            target = (html_path.parent / path).resolve() if not path.startswith("/") else (hosted_root / path.lstrip("/")).resolve()
            if ref.endswith("/") or target.is_dir():
                target = target / "index.html"
            if not target.exists():
                missing.append(f"{html_path.relative_to(hosted_root)} -> {ref}")
    add(checks, "local HTML links and assets resolve", not missing, "; ".join(missing[:10]))


def check_metadata(hosted_root: Path, checks: list[Check]) -> None:
    failures: list[str] = []
    for page_name, expected_url in PAGES.items():
        parser = parse_html(hosted_root / page_name)
        canonical = parser.meta.get(("link", "canonical"), "")
        og_url = parser.meta.get(("property", "og:url"), "")
        og_image = parser.meta.get(("property", "og:image"), "")
        if canonical != expected_url:
            failures.append(f"{page_name} canonical={canonical!r}")
        if og_url != expected_url:
            failures.append(f"{page_name} og:url={og_url!r}")
        if og_image != f"{EXPECTED_BASE_URL}/assets/swiftterm-social-preview.png":
            failures.append(f"{page_name} og:image={og_image!r}")
    add(checks, "canonical, og:url, and og:image match production", not failures, "; ".join(failures))


def check_stylesheet_cache_bust(hosted_root: Path, checks: list[Check]) -> None:
    failures: list[str] = []
    for page_name in [*PAGES.keys(), "404.html"]:
        path = hosted_root / page_name
        if not path.exists():
            continue
        parser = parse_html(path)
        stylesheet_refs = [ref for ref in parser.refs if ref.startswith("site.css")]
        if "site.css?v=20260501-rizz2" not in stylesheet_refs:
            failures.append(page_name)
    add(checks, "HTML pages use cache-busted stylesheet URL", not failures, ", ".join(failures))


def check_media_kit(hosted_root: Path, checks: list[Check]) -> None:
    zip_path = hosted_root / "media-kit" / "swiftterm-media-kit.zip"
    if not zip_path.exists():
        add(checks, "media kit ZIP is readable", False, "missing")
        return
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        missing = sorted(REQUIRED_MEDIA_KIT_MEMBERS - names)
        add(checks, "media kit ZIP contains required assets", not missing, ", ".join(missing))
    except zipfile.BadZipFile as error:
        add(checks, "media kit ZIP is readable", False, str(error))


def check_copy(hosted_root: Path, checks: list[Check]) -> None:
    html_text = "\n".join(read(path) for path in sorted(hosted_root.rglob("*.html")))
    missing_terms = [term for term in REQUIRED_COPY_TERMS if term not in html_text]
    add(checks, "expected SwiftTerm trust and product terms are present", not missing_terms, ", ".join(missing_terms))

    faq = read(hosted_root / "faq.html") if (hosted_root / "faq.html").exists() else ""
    boundary_terms = ["Mosh", "CloudKit", "collaboration", "production AI", "live RSA"]
    missing_boundaries = [term for term in boundary_terms if term not in faq]
    add(checks, "FAQ names roadmap boundaries", not missing_boundaries, ", ".join(missing_boundaries))


def check_forbidden_patterns(hosted_root: Path, checks: list[Check]) -> None:
    text_paths = [*hosted_root.rglob("*.html"), *hosted_root.rglob("*.css"), *hosted_root.rglob("*.md"), hosted_root / "site.webmanifest"]
    for label, pattern in FORBIDDEN_PATTERNS.items():
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [str(path.relative_to(hosted_root)) for path in text_paths if path.exists() and regex.search(read(path))]
        add(checks, f"no {label}", not matches, ", ".join(matches))


def check_live(checks: list[Check]) -> None:
    urls = [*PAGES.values(), f"{EXPECTED_BASE_URL}/media-kit/swiftterm-media-kit.zip", f"{EXPECTED_BASE_URL}/assets/swiftterm-social-preview.png"]
    for url in urls:
        try:
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SwiftTermHostedSiteAudit/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                ok = 200 <= response.status < 400
                detail = f"HTTP {response.status}"
        except urllib.error.HTTPError as error:
            ok = 200 <= error.code < 400
            detail = f"HTTP {error.code}"
        except Exception as error:  # noqa: BLE001
            ok = False
            detail = str(error)
        add(checks, f"live URL responds: {url}", ok, detail)


def run_audit(hosted_root: Path, include_live: bool) -> list[Check]:
    checks: list[Check] = []
    add(checks, "hosted root exists", hosted_root.exists(), str(hosted_root))
    if not hosted_root.exists():
        return checks
    check_required_files(hosted_root, checks)
    check_local_references(hosted_root, checks)
    check_metadata(hosted_root, checks)
    check_stylesheet_cache_bust(hosted_root, checks)
    check_media_kit(hosted_root, checks)
    check_copy(hosted_root, checks)
    check_forbidden_patterns(hosted_root, checks)
    if include_live:
        check_live(checks)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SwiftTerm hosted-site launch readiness.")
    parser.add_argument("--hosted-root", type=Path, default=DEFAULT_HOSTED_ROOT)
    parser.add_argument("--live", action="store_true", help="Also check live production URLs.")
    args = parser.parse_args()

    checks = run_audit(args.hosted_root.resolve(), args.live)
    failed = [check for check in checks if not check.ok]

    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        detail = f" - {check.detail}" if check.detail else ""
        print(f"{status}: {check.name}{detail}")

    print()
    if failed:
        print(f"SwiftTerm hosted-site audit failed: {len(failed)} issue(s).")
        return 1
    print(f"SwiftTerm hosted-site audit passed: {len(checks)} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
