"""The two tool functions and their LangChain tool wrappers."""

from __future__ import annotations

from langchain_core.tools import tool

ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = ["", "thousand", "million", "billion", "trillion"]
LIMIT = 1000 ** len(SCALES)  # 10**15: anything below a quadrillion


def _under_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = [f"{ONES[hundreds]} hundred"] if hundreds else []
    if rest >= 20:
        tens, ones = divmod(rest, 10)
        parts.append(TENS[tens] + (f"-{ONES[ones]}" if ones else ""))
    elif rest:
        parts.append(ONES[rest])
    return " ".join(parts)


def number_to_words(n: int) -> str:
    """2048 -> "two thousand forty-eight". American style: no "and", hyphens for 21-99."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"expected a whole number, got {n!r}")
    if n == 0:
        return "zero"
    if abs(n) >= LIMIT:
        raise ValueError(f"{n} is too large; the limit is {LIMIT - 1:,}")
    chunks, rest = [], abs(n)
    for scale in SCALES:
        rest, chunk = divmod(rest, 1000)
        if chunk:
            chunks.append(_under_thousand(chunk) + (f" {scale}" if scale else ""))
    words = " ".join(reversed(chunks))
    return f"minus {words}" if n < 0 else words


def square(x: float) -> int | float:
    """12 -> 144. Whole-number input gives a whole-number result (no 144.0)."""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return x * x


# LangChain tools. The docstring becomes the tool description the model sees,
# so it says when to pick the tool, not just what it does.
@tool("number_to_words")
def number_to_words_tool(number: int) -> str:
    """Spell out a whole number in English words, e.g. 2048 -> "two thousand forty-eight".
    Use when the user wants a number written, spelled or converted to words."""
    return number_to_words(number)


@tool("square")
def square_tool(number: float) -> int | float:
    """Return the square of a number (the number multiplied by itself), e.g. 12 -> 144.
    Use when the user asks to square a number or for a number squared."""
    return square(number)


TOOLS = {t.name: t for t in (number_to_words_tool, square_tool)}
