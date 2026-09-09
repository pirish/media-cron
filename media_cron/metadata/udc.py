from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from media_cron.metadata.models import BookMetadata, UDCClassification

logger = logging.getLogger(__name__)


@runtime_checkable
class UDCResolverProtocol(Protocol):
    """Protocol for resolving Universal Decimal Classification notations."""

    def resolve(
        self,
        subjects: list[str],
        classification_hints: list[str] | None = None,
    ) -> UDCClassification | None:
        """Maps candidate subject strings or classification hints to a UDC notation.

        Returns None if no matching classification can be confidently determined.
        """
        ...


class UDCResolver:
    """Resolves Universal Decimal Classification (UDC) notations from subjects and classification hints."""

    def __init__(self, summary_table_path: Path | None = None) -> None:
        if summary_table_path is None:
            summary_table_path = Path(__file__).parent / "data" / "udc_summary.json"
        self.summary_table_path = summary_table_path
        self.classes: dict[str, dict[str, Any]] = {}
        self.dewey_crosswalk: dict[str, str] = {}
        self._load_table()

    def _load_table(self) -> None:
        if not self.summary_table_path.exists():
            logger.warning("UDC summary table not found at %s", self.summary_table_path)
            return

        try:
            with open(self.summary_table_path, encoding="utf-8") as f:
                data = json.load(f)
            self.classes = data.get("classes", {})
            self.dewey_crosswalk = data.get("dewey_crosswalk", {})
        except Exception as e:
            logger.error("Failed loading UDC summary table from %s: %s", self.summary_table_path, e)

    def resolve(
        self,
        subjects: list[str] | BookMetadata,
        classification_hints: list[str] | None = None,
    ) -> UDCClassification | None:
        subj_list: list[str] = []
        hints = list(classification_hints or [])

        if isinstance(subjects, BookMetadata):
            subj_list = list(subjects.subjects)
            if subjects.extra and "ddc" in subjects.extra:
                ddc_val = subjects.extra["ddc"]
                if isinstance(ddc_val, list):
                    hints.extend(ddc_val)
                elif isinstance(ddc_val, str):
                    hints.append(ddc_val)
        elif isinstance(subjects, list):
            subj_list = list(subjects)

        # 1. Exact / Substring Subject Keyword Matching
        # Prioritize deepest subclass notations (longer notations or classes with parents)
        best_class: dict[str, Any] | None = None
        best_depth: int = -1

        for notation, c_info in self.classes.items():
            keywords = [k.lower() for k in c_info.get("keywords", [])]
            matched = False
            for s in subj_list:
                s_lower = s.lower().strip()
                for kw in keywords:
                    # Match if exact match or keyword appears as complete phrase/words in subject
                    if kw == s_lower or re.search(r"\b" + re.escape(kw) + r"\b", s_lower):
                        matched = True
                        break
                if matched:
                    break

            if matched:
                # Calculate hierarchy depth (number of segments, dots, hyphens, and parent presence)
                depth = len(notation) + (10 if c_info.get("parent") else 0)
                if depth > best_depth:
                    best_depth = depth
                    best_class = c_info

        if best_class is not None:
            return UDCClassification(
                notation=best_class["notation"],
                description=best_class.get("name", ""),
                parent_notation=best_class.get("parent"),
                confidence=1.0,
                source="summary_table",
            )

        # 2. Dewey / Classification Crosswalk Fallback
        for hint in hints:
            cleaned_hint = hint.strip()
            m = re.match(r"^(\d{3})", cleaned_hint)
            if m:
                prefix = m.group(1)
                udc_not = self.dewey_crosswalk.get(prefix)
                if udc_not and udc_not in self.classes:
                    c_info = self.classes[udc_not]
                    return UDCClassification(
                        notation=c_info["notation"],
                        description=c_info.get("name", ""),
                        parent_notation=c_info.get("parent"),
                        confidence=0.85,
                        source="dewey_crosswalk",
                    )

        # 3. No match found -> graceful None
        return None
