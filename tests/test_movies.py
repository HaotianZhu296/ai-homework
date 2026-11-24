import json

from langchain_core.language_models import FakeListChatModel

from part1_generate_prompts import MOVIES, build_prompts, movie_prompt, save_prompts
from part2_run_llm import load_prompts, parse_response, run_batch, save_results


def test_template_takes_only_the_title():
    assert movie_prompt.input_variables == ["title"]


def test_one_prompt_per_movie_asking_for_genre_and_plot():
    prompts = build_prompts()
    assert len(prompts) == 4
    for title, prompt in zip(MOVIES, prompts):
        assert f'"{title}"' in prompt and "genre" in prompt and "plot" in prompt


def test_prompts_survive_the_round_trip_through_the_file(tmp_path):
    path = tmp_path / "prompts.txt"
    save_prompts(build_prompts(), path)
    assert load_prompts(path) == build_prompts()


def test_batch_turns_each_reply_into_a_record():
    replies = [
        '{"title": "Inception", "genre": "Sci-fi", "plot": "Dream heists."}',
        '```json\n{"title": "Titanic", "genre": ["Romance", "Drama"], "plot": "A ship sinks."}\n```',
    ]
    prompts = build_prompts(["Inception", "Titanic"])
    results = run_batch(FakeListChatModel(responses=replies), prompts)
    assert results[0] == {"prompt": prompts[0], "title": "Inception", "genre": "Sci-fi", "plot": "Dream heists."}
    assert results[1]["genre"] == ["Romance", "Drama"]


def test_non_json_reply_is_kept_instead_of_crashing():
    item = parse_response("Sorry, I don't know that movie.")
    assert item["error"] and item["response"] == "Sorry, I don't know that movie."


def test_results_file_is_valid_json(tmp_path):
    path = tmp_path / "results.json"
    save_results([{"prompt": "p", "title": "Amélie", "genre": "Comedy", "plot": "Paris."}], path)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["title"] == "Amélie"
