"""Build a self-contained Riverbend webpage that needs no local server."""

from __future__ import annotations

import argparse
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Build a standalone Riverbend World HTML file."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "web" / "riverbend_world.html",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    web_root = project_root / "web"
    html = (web_root / "index.html").read_text(encoding="utf-8")
    css = (web_root / "styles.css").read_text(encoding="utf-8")
    javascript = (web_root / "dist" / "app.js").read_text(
        encoding="utf-8"
    )
    data = (web_root / "data" / "demo_bundle.json").read_text(
        encoding="utf-8"
    )
    safe_data = data.replace("<", "\\u003c").replace(">", "\\u003e")

    html = html.replace(
        '<link rel="stylesheet" href="/styles.css" />',
        f"<style>\n{css}\n</style>",
    )
    html = html.replace(
        '<script type="module" src="/dist/app.js"></script>',
        (
            '<script id="demo-data" type="application/json">\n'
            f"{safe_data}\n"
            "</script>\n"
            f"<script>\n{javascript}\n</script>"
        ),
    )
    args.output.write_text(html, encoding="utf-8")
    print(f"Built standalone world: {args.output.resolve()}")


if __name__ == "__main__":
    main()
