"""Part 1: fill a PromptTemplate for each movie and save the prompts to prompts.txt."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import PromptTemplate

HERE = Path(__file__).resolve().parent
PROMPTS_FILE = HERE / "prompts.txt"

MOVIES = ["Inception", "Titanic", "The Matrix", "The Godfather"]

# Asking for JSON with fixed keys lets Part 2 turn each answer into a record
# instead of storing free text.
movie_prompt = PromptTemplate.from_template(
    'Tell me the genre and the plot of the movie "{title}". '
    'Answer with a JSON object only, using the keys "title", "genre" and "plot", '
    'where "genre" is a list of 1 to 3 standard genre names (for example ["Drama", "Romance"]) '
    'and "plot" is a short summary of 2 to 3 sentences without major spoilers.'
)


def build_prompts(titles: list[str] = MOVIES) -> list[str]:
    return [movie_prompt.format(title=title) for title in titles]


def save_prompts(prompts: list[str], path: Path | str = PROMPTS_FILE) -> None:
    """One prompt per line, so Part 2 can read them back line by line."""
    for prompt in prompts:
        if "\n" in prompt:
            raise ValueError(f"prompt spans several lines and would not load back: {prompt!r}")
    Path(path).write_text("\n".join(prompts) + "\n", encoding="utf-8")


def main() -> None:
    prompts = build_prompts()
    save_prompts(prompts)
    for prompt in prompts:
        print(prompt)
    print(f"\nSaved {len(prompts)} prompts to {PROMPTS_FILE.name}")


if __name__ == "__main__":
    main()
