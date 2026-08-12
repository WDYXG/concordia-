"""Two-call smoke test for the Concordia DeepSeek adapter."""

from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)


def main() -> None:
    model = DeepSeekLanguageModel()
    text = model.sample_text(
        "Alice is campaigning for mayor of fictional Riverbend. "
        "Write one short campaign sentence.",
        max_tokens=80,
        temperature=0.3,
    )
    print("sample_text:", text)

    index, choice, info = model.sample_choice(
        "A voter who prioritizes environmental protection chooses a candidate.",
        ["Alice", "Bob"],
    )
    print("sample_choice:", {"index": index, "choice": choice, **info})


if __name__ == "__main__":
    main()
