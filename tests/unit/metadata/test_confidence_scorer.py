from media_cron.metadata.scorer import ConfidenceScorer


def test_normalize_text():
    scorer = ConfidenceScorer()
    raw = "The Hobbit (Unabridged) [Audiobook] - Part 1 (2008).mp3"
    cleaned = scorer.normalize_title(raw)
    assert "unabridged" not in cleaned
    assert "audiobook" not in cleaned
    assert "part 1" not in cleaned
    assert "hobbit" in cleaned


def test_exact_match():
    scorer = ConfidenceScorer()
    score = scorer.compute_confidence(
        query_title="The Hobbit",
        query_author="J.R.R. Tolkien",
        candidate_title="The Hobbit",
        candidate_author="J.R.R. Tolkien",
    )
    assert score >= 0.95
    assert scorer.is_override_eligible(score, threshold=0.85) is True


def test_word_order_variation_author():
    scorer = ConfidenceScorer()
    score = scorer.compute_confidence(
        query_title="The Fellowship of the Ring",
        query_author="Tolkien, J. R. R.",
        candidate_title="The Fellowship of the Ring",
        candidate_author="J.R.R. Tolkien",
    )
    assert score >= 0.85
    assert scorer.is_override_eligible(score, threshold=0.85) is True


def test_author_mismatch_penalty():
    # Common generic title matching, but different author
    scorer = ConfidenceScorer()
    score = scorer.compute_confidence(
        query_title="It",
        query_author="Jane Doe",
        candidate_title="It",
        candidate_author="Stephen King",
    )
    # Due to author penalty, score must be capped < 0.50
    assert score < 0.50
    assert scorer.is_override_eligible(score, threshold=0.85) is False


def test_missing_author_query():
    scorer = ConfidenceScorer()
    score = scorer.compute_confidence(
        query_title="Dune",
        query_author=None,
        candidate_title="Dune",
        candidate_author="Frank Herbert",
    )
    # Title matches perfectly, but author is unknown in seed; capped at 0.75
    assert 0.60 <= score <= 0.75
    assert scorer.is_override_eligible(score, threshold=0.85) is False
