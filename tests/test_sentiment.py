from collections import Counter

from metrics import majority, parse_label, score


def test_parse_label_accepts_valid_reply():
    label, rationale, error = parse_label('{"rationale": "mock praise", "label": "sarcastic"}')
    assert (label, rationale, error) == ("sarcastic", "mock praise", None)


def test_parse_label_rejects_unknown_label_and_bad_json():
    assert parse_label('{"rationale": "x", "label": "mixed"}')[0] is None
    assert parse_label("sarcastic")[0] is None


def test_majority_breaks_ties_with_fallback_then_label_order():
    votes = Counter({"positive": 1, "sarcastic": 1, "neutral": 1})
    assert majority(votes, Counter({"sarcastic": 10, "positive": 3})) == "sarcastic"
    assert majority(votes) == "positive"


def test_score_counts_sentences_records_and_votes():
    records = [
        {"id": "1", "text": "A", "annotations": ["positive", "positive", "positive"]},
        {"id": "2", "text": "A", "annotations": ["positive", "sarcastic", "positive"]},
        {"id": "3", "text": "B", "annotations": ["negative", "negative", "neutral"]},
    ]
    m = score(records, {"A": "positive", "B": "neutral"})
    assert m["sentence_accuracy"] == 0.5
    assert round(m["record_accuracy"], 4) == round(2 / 3, 4)
    # Votes matching the prediction: 3 + 2 + 1 out of 9.
    assert round(m["vote_agreement"], 4) == round(6 / 9, 4)
    assert m["confusion"]["negative"]["neutral"] == 1
