"""Screenshot a web page as B-roll: a Google Business Profile, a review page, your website, a dashboard.

Renders in headless Chromium at phone or desktop size, optionally scrolled to a selector, and
saves a PNG you can drop into an EDL as a `pip` or `speaker_inset` B-roll. Also records a short
scroll-through video when asked, so "the screen is the set" beats have real motion.

Usage:
    .venv/bin/python tools/capture.py https://example.com --out raw/broll_site.png
    .venv/bin/python tools/capture.py https://example.com --out raw/broll_site.png --device desktop --full-page
    .venv/bin/python tools/capture.py https://example.com --out raw/broll_scroll.mp4 --scroll 6   # 6 s scroll video
    .venv/bin/python tools/capture.py https://example.com --out raw/reviews.png --selector ".reviews"
Only capture pages you have the right to show (your own, your clients' with permission, public listings).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg  # noqa: E402

DEVICES = {"phone": (390, 844, 3), "desktop": (1440, 900, 2)}


def capture(url: str, out: Path, device: str = "phone", full_page: bool = False, selector: str | None = None,
            scroll_seconds: float = 0.0, fps: int = 30, wait_ms: int = 1500) -> Path:
    from playwright.sync_api import sync_playwright

    import plates  # noqa: WPS433

    w, h, scale = DEVICES[device]
    with sync_playwright() as pw:
        kwargs = {"args": ["--no-sandbox"]}
        if plates.chromium_path():
            kwargs["executable_path"] = plates.chromium_path()
        browser = pw.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale,
                                user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1") if device == "phone" else None)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(wait_ms)
        if selector:
            page.locator(selector).first.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
        out.parent.mkdir(parents=True, exist_ok=True)
        if scroll_seconds > 0:
            total = page.evaluate("document.documentElement.scrollHeight - window.innerHeight")
            n = int(scroll_seconds * fps)
            with tempfile.TemporaryDirectory() as td:
                for i in range(n):
                    y = int(total * (1 - (1 - i / max(1, n - 1)) ** 3))   # ease-out scroll
                    page.evaluate(f"window.scrollTo(0, {y})")
                    page.screenshot(path=f"{td}/{i:05d}.png")
                subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-framerate", str(fps), "-i", f"{td}/%05d.png",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
                                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(out)], check=True)
        else:
            page.screenshot(path=str(out), full_page=full_page)
        browser.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help=".png for a still, .mp4 with --scroll for a scroll-through video")
    ap.add_argument("--device", default="phone", choices=list(DEVICES))
    ap.add_argument("--full-page", action="store_true")
    ap.add_argument("--selector", help="CSS selector to scroll into view first")
    ap.add_argument("--scroll", type=float, default=0.0, help="seconds of scroll-through video to record")
    args = ap.parse_args()
    out = capture(args.url, Path(args.out), args.device, args.full_page, args.selector, args.scroll)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
