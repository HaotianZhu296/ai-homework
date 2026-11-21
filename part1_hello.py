"""Part 1: send one prompt to the API and print the response."""

from llm_client import get_model, make_client

PROMPT = "What is the capital of France?"


def main() -> None:
    client = make_client()
    response = client.chat.completions.create(
        model=get_model(),
        messages=[{"role": "user", "content": PROMPT}],
    )
    print(f"Prompt:   {PROMPT}")
    print(f"Response: {response.choices[0].message.content}")


if __name__ == "__main__":
    main()
