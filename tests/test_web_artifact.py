"""Structural checks for the standalone Riverbend browser artifact."""

from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import unittest


class _ArtifactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.external_scripts: list[str] = []
        self.external_styles: list[str] = []
        self._capture_demo_data = False
        self.demo_data_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "script" and attributes.get("src"):
            self.external_scripts.append(str(attributes["src"]))
        if tag == "link" and attributes.get("href"):
            self.external_styles.append(str(attributes["href"]))
        if tag == "script" and element_id == "demo-data":
            self._capture_demo_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture_demo_data:
            self._capture_demo_data = False

    def handle_data(self, data: str) -> None:
        if self._capture_demo_data:
            self.demo_data_parts.append(data)


class WebArtifactTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.artifact = (
            self.project_root / "web" / "riverbend_world.html"
        )

    def test_standalone_artifact_contains_required_interface(self) -> None:
        parser = _ArtifactParser()
        parser.feed(self.artifact.read_text(encoding="utf-8"))

        required_ids = {
            "world-canvas",
            "import-input",
            "import-button",
            "demo-button",
            "condition-select",
            "play-button",
            "pause-button",
            "step-button",
            "reset-button",
            "timeline",
            "agent-list",
            "event-feed",
            "agent-detail",
            "model-tab",
            "model-detail",
            "vote-tab",
            "vote-tab-count",
            "vote-panel",
            "vote-detail",
            "condition-bars",
        }
        self.assertTrue(required_ids.issubset(parser.ids))
        self.assertEqual(parser.external_scripts, [])
        self.assertEqual(parser.external_styles, [])

    def test_embedded_demo_data_matches_real_run_contract(self) -> None:
        parser = _ArtifactParser()
        parser.feed(self.artifact.read_text(encoding="utf-8"))
        payload = json.loads("".join(parser.demo_data_parts))

        self.assertEqual(payload["mode"], "scripted_no_api_demo")
        self.assertEqual(len(payload["conditions"]), 4)
        for condition in payload["conditions"]:
            run = condition["run"]
            self.assertEqual(len(run["scenario"]["agents"]), 5)
            self.assertEqual(len(run["scenario"]["locations"]), 6)
            self.assertEqual(len(run["turns"]), 15)
            self.assertTrue(
                all("state_after" in turn for turn in run["turns"])
            )
            self.assertTrue(
                condition["metrics"]["manipulation_check_passed"]
            )

    def test_compiled_frontend_is_present(self) -> None:
        javascript = self.project_root / "web" / "dist" / "app.js"
        source = javascript.read_text(encoding="utf-8")

        self.assertGreater(len(source), 10_000)
        self.assertIn("DeepSeek API 实验回放", source)
        self.assertIn("controller_traces", source)
        self.assertIn("file.text()", source)
        self.assertIn("not-voted-bar", source)
        self.assertIn("未投", source)
        self.assertIn("天气事件", source)
        self.assertIn("time_unit", source)
        self.assertIn("最终投票与理由", source)
        self.assertIn("此运行未记录投票理由", source)

    def test_mobile_layout_constrains_primary_panels(self) -> None:
        stylesheet = (
            self.project_root / "web" / "styles.css"
        ).read_text(encoding="utf-8")
        mobile_rules = stylesheet.split(
            "@media (max-width: 760px)", maxsplit=1
        )[1]

        self.assertIn(".workspace,", mobile_rules)
        self.assertIn(".world-column,", mobile_rules)
        self.assertIn(".inspector {", mobile_rules)
        self.assertIn("max-width: 100%;", mobile_rules)
        self.assertIn("overflow-x: hidden;", mobile_rules)
        self.assertIn("overscroll-behavior-x: contain;", mobile_rules)

    def test_event_feed_has_an_independent_scroll_area(self) -> None:
        stylesheet = (
            self.project_root / "web" / "styles.css"
        ).read_text(encoding="utf-8")
        event_rules = stylesheet.split(
            ".event-feed {", maxsplit=1
        )[1].split("}", maxsplit=1)[0]

        self.assertIn("min-height: 0;", event_rules)
        self.assertIn("flex: 1 1 0;", event_rules)
        self.assertIn("overflow-y: scroll;", event_rules)
        self.assertIn("scrollbar-gutter: stable;", event_rules)
