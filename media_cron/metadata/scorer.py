import difflib
import re


class ConfidenceScorer:
    """Evaluates string similarity and calculates match confidence scores."""

    CLUTTER_PATTERNS = [
        r"\(unabridged\)",
        r"\[audiobook\]",
        r"\(audiobook\)",
        r"part\s*\d+",
        r"cd\s*\d+",
        r"disc\s*\d+",
        r"chapter\s*\d+",
        r"\d+kbps",
        r"\d+hz",
        r"(?:mp3|m4b|m4a|flac|aac)",
    ]

    def normalize_title(self, text: str) -> str:
        s = text.lower()
        for pat in self.CLUTTER_PATTERNS:
            s = re.sub(pat, " ", s, flags=re.IGNORECASE)
        # Strip trailing extension if present
        s = re.sub(r"\.[a-z0-9]{2,4}$", " ", s, flags=re.IGNORECASE)
        # Replace non-alphanumeric with spaces
        s = re.sub(r"[^\w\s]", " ", s)
        return " ".join(s.split())

    def normalize_author(self, text: str | None) -> str:
        if not text:
            return ""
        s = text.lower()
        # Handle "Last, First" by splitting on comma
        if "," in s:
            parts = [p.strip() for p in s.split(",")]
            s = " ".join(reversed(parts))
        s = re.sub(r"[^\w\s]", " ", s)
        return " ".join(s.split())

    def _token_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0

        # SequenceMatcher base ratio
        seq_ratio = difflib.SequenceMatcher(None, a, b).ratio()

        # Token set ratio
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return seq_ratio

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union) if union else 0.0

        # Substring bonus: if one is entirely contained in another
        sub_bonus = 0.0
        if a in b or b in a:
            sub_bonus = 0.15

        # Weighted combination capped at 1.0
        combined = 0.5 * seq_ratio + 0.5 * jaccard + sub_bonus
        return min(1.0, combined)

    def compute_confidence(
        self,
        query_title: str,
        query_author: str | None,
        candidate_title: str,
        candidate_author: str | None,
    ) -> float:
        norm_q_title = self.normalize_title(query_title)
        norm_c_title = self.normalize_title(candidate_title)

        title_sim = self._token_similarity(norm_q_title, norm_c_title)

        # If query author is not provided:
        if not query_author:
            # Score depends purely on title similarity, but capped at 0.75 because author is unverified
            return round(min(0.75, title_sim * 0.75), 3)

        norm_q_author = self.normalize_author(query_author)
        norm_c_author = self.normalize_author(candidate_author)

        author_sim = self._token_similarity(norm_q_author, norm_c_author)

        # Author mismatch penalty: if author matches poorly (< 0.40), cap confidence at 0.40
        if author_sim < 0.40:
            return round(min(0.39, title_sim * 0.40), 3)

        composite = 0.55 * title_sim + 0.45 * author_sim
        return round(min(1.0, composite), 3)

    def is_override_eligible(self, confidence: float, threshold: float = 0.85) -> bool:
        return confidence >= threshold
