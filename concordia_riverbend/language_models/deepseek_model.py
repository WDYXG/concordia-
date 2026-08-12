"""DeepSeek adapter for Concordia's LanguageModel interface."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
import json
import os
from pathlib import Path
from typing import Any

from concordia.language_model import language_model
from openai import OpenAI


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_CHOICE_ATTEMPTS = 4


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _truncate_at_terminator(text: str, terminators: Collection[str]) -> str:
    positions = [
        text.find(terminator)
        for terminator in terminators
        if terminator and terminator in text
    ]
    return text[: min(positions)] if positions else text


class DeepSeekLanguageModel(language_model.LanguageModel):
    """Calls DeepSeek through its OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        env_file: str | Path | None = None,
        client: Any | None = None,
        max_choice_attempts: int = DEFAULT_CHOICE_ATTEMPTS,
    ) -> None:
        if env_file is None:
            env_file = Path.cwd() / ".env"
        _load_env_file(Path(env_file))

        self._model_name = (
            model_name
            or os.getenv("DEEPSEEK_MODEL")
            or DEFAULT_DEEPSEEK_MODEL
        )
        self._api_base = (
            api_base
            or os.getenv("DEEPSEEK_BASE_URL")
            or DEFAULT_DEEPSEEK_BASE_URL
        )
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if client is None and not self._api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not found. Add it to the local .env file."
            )
        if max_choice_attempts < 1:
            raise ValueError("max_choice_attempts must be at least 1.")

        self._client = client or OpenAI(
            api_key=self._api_key,
            base_url=self._api_base,
        )
        self._max_choice_attempts = max_choice_attempts
        self._usage_records: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def api_base(self) -> str:
        return self._api_base

    def _create_completion(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
        timeout: float,
        terminators: Collection[str] = (),
        json_mode: bool = False,
    ) -> str:
        request: dict[str, Any] = {
            "model": self._model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the language engine inside a Concordia social "
                        "simulation. Follow the user's requested output format "
                        "exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if terminators:
            request["stop"] = list(terminators)
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**request)
        usage = getattr(response, "usage", None)
        self._usage_records.append(
            {
                "model": self._model_name,
                "prompt_tokens": int(
                    getattr(usage, "prompt_tokens", 0) or 0
                ),
                "completion_tokens": int(
                    getattr(usage, "completion_tokens", 0) or 0
                ),
                "total_tokens": int(
                    getattr(usage, "total_tokens", 0) or 0
                ),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "json_mode": json_mode,
            }
        )
        content = response.choices[0].message.content
        if not content:
            raise language_model.InvalidResponseError(
                "DeepSeek returned an empty response."
            )
        return str(content).strip()

    def usage_summary(self) -> dict[str, Any]:
        """Return provider-reported token totals without estimating prices."""
        return {
            "model": self._model_name,
            "request_count": len(self._usage_records),
            "prompt_tokens": sum(
                record["prompt_tokens"]
                for record in self._usage_records
            ),
            "completion_tokens": sum(
                record["completion_tokens"]
                for record in self._usage_records
            ),
            "total_tokens": sum(
                record["total_tokens"]
                for record in self._usage_records
            ),
            "records": [dict(record) for record in self._usage_records],
            "cost_estimate": None,
            "cost_note": (
                "No price was assumed. Apply the provider's price for the "
                "model and run date to the recorded token totals."
            ),
        }

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
        terminators: Collection[str] = language_model.DEFAULT_TERMINATORS,
        temperature: float = language_model.DEFAULT_TEMPERATURE,
        top_p: float = language_model.DEFAULT_TOP_P,
        top_k: int = language_model.DEFAULT_TOP_K,
        timeout: float = language_model.DEFAULT_TIMEOUT_SECONDS,
        seed: int | None = None,
    ) -> str:
        del top_k, seed  # DeepSeek's compatible endpoint does not use them here.
        text = self._create_completion(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            terminators=terminators,
        )
        return _truncate_at_terminator(text, terminators)

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, Mapping[str, Any]]:
        del seed
        if not responses:
            raise ValueError("responses must contain at least one choice.")
        if len(set(responses)) != len(responses):
            raise ValueError("responses must not contain duplicates.")

        options = "\n".join(f"- {response}" for response in responses)
        choice_prompt = (
            f"{prompt}\n\nChoose exactly one option:\n{options}\n\n"
            'Return JSON only in this form: {"choice": "<exact option>"}'
        )
        last_answer = ""
        for attempt in range(1, self._max_choice_attempts + 1):
            last_answer = self._create_completion(
                choice_prompt,
                max_tokens=80,
                temperature=0.0,
                top_p=1.0,
                timeout=language_model.DEFAULT_TIMEOUT_SECONDS,
                json_mode=True,
            )
            try:
                parsed = json.loads(last_answer)
                selected = str(parsed["choice"]).strip()
                index = responses.index(selected)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            return index, responses[index], {"attempts": attempt}

        raise language_model.InvalidResponseError(
            "DeepSeek did not return one of the permitted choices after "
            f"{self._max_choice_attempts} attempts. Last response: "
            f"{last_answer!r}"
        )
