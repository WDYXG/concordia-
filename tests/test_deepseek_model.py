from __future__ import annotations

from collections import deque
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from concordia.language_model import language_model

from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content))
        ],
        usage=SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=3,
            total_tokens=14,
        ),
    )


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = deque(contents)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        return _response(self._contents.popleft())


class _FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _FakeCompletions(contents)
        self.chat = SimpleNamespace(completions=self.completions)


class DeepSeekLanguageModelTest(unittest.TestCase):
    def test_loads_key_from_env_file_without_printing_it(self) -> None:
        fake = _FakeClient(["hello"])
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "DEEPSEEK_API_KEY=test-only-key\n", encoding="utf-8"
            )
            model = DeepSeekLanguageModel(
                env_file=env_file,
                client=fake,
            )
            self.assertEqual(model.sample_text("Hi"), "hello")

    def test_sample_text_uses_deepseek_parameters(self) -> None:
        fake = _FakeClient(["Alice speaks. STOP ignored"])
        model = DeepSeekLanguageModel(api_key="test", client=fake)

        result = model.sample_text(
            "Continue",
            max_tokens=40,
            terminators=("STOP",),
            temperature=0.4,
        )

        self.assertEqual(result, "Alice speaks. ")
        request = fake.completions.requests[0]
        self.assertEqual(request["model"], "deepseek-v4-flash")
        self.assertEqual(request["max_tokens"], 40)
        self.assertEqual(
            request["extra_body"], {"thinking": {"type": "disabled"}}
        )
        self.assertEqual(request["stop"], ["STOP"])

    def test_sample_choice_returns_concordia_tuple(self) -> None:
        fake = _FakeClient(['{"choice": "Bob"}'])
        model = DeepSeekLanguageModel(api_key="test", client=fake)

        result = model.sample_choice("Who receives the vote?", ["Alice", "Bob"])

        self.assertEqual(result, (1, "Bob", {"attempts": 1}))
        self.assertEqual(
            fake.completions.requests[0]["response_format"],
            {"type": "json_object"},
        )

    def test_sample_choice_retries_invalid_json(self) -> None:
        fake = _FakeClient(["not json", '{"choice": "Alice"}'])
        model = DeepSeekLanguageModel(api_key="test", client=fake)

        result = model.sample_choice("Choose", ["Alice", "Bob"])

        self.assertEqual(result, (0, "Alice", {"attempts": 2}))

    def test_sample_choice_raises_after_limit(self) -> None:
        fake = _FakeClient(['{"choice": "Charlie"}', '{"choice": "Nobody"}'])
        model = DeepSeekLanguageModel(
            api_key="test",
            client=fake,
            max_choice_attempts=2,
        )

        with self.assertRaises(language_model.InvalidResponseError):
            model.sample_choice("Choose", ["Alice", "Bob"])

    def test_records_provider_reported_token_usage(self) -> None:
        fake = _FakeClient(["hello", "again"])
        model = DeepSeekLanguageModel(api_key="test", client=fake)

        model.sample_text("First")
        model.sample_text("Second")
        usage = model.usage_summary()

        self.assertEqual(usage["request_count"], 2)
        self.assertEqual(usage["prompt_tokens"], 22)
        self.assertEqual(usage["completion_tokens"], 6)
        self.assertEqual(usage["total_tokens"], 28)
        self.assertIsNone(usage["cost_estimate"])


if __name__ == "__main__":
    unittest.main()
