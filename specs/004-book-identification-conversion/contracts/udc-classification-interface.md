# Contract: Universal Decimal Classification (UDC) Interface

**Feature**: Book Identification, UDC Classification, and EPUB Conversion  
**Branch**: `004-book-identification-conversion`  
**Date**: 2026-09-09  

## 1. UDC Resolution Protocol

```python
from typing import Protocol, runtime_checkable
from media_cron.metadata.models import UDCClassification


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
```

---

## 2. Summary Table Schema (`udc_summary.json`)

The bundled reference mapping structure:

```json
{
  "classes": {
    "0": {
      "notation": "0",
      "name": "Science and Knowledge. Organization. Computer Science. Information",
      "keywords": ["computer science", "information technology", "cybernetics", "data", "bibliography"]
    },
    "5": {
      "notation": "5",
      "name": "Mathematics and Natural Sciences",
      "keywords": ["mathematics", "physics", "chemistry", "biology", "astronomy", "geology"]
    },
    "6": {
      "notation": "6",
      "name": "Applied Sciences. Medicine. Technology",
      "keywords": ["medicine", "engineering", "technology", "agriculture", "management"]
    },
    "8": {
      "notation": "8",
      "name": "Language. Linguistics. Literature",
      "keywords": ["language", "linguistics", "literature", "poetry", "drama"]
    },
    "82-31": {
      "notation": "82-31",
      "name": "Literature - Fiction - Novels",
      "parent": "8",
      "keywords": ["fiction", "novel", "novels", "literature fiction", "prose"]
    },
    "82-311.9": {
      "notation": "82-311.9",
      "name": "Literature - Fiction - Science fiction",
      "parent": "82-31",
      "keywords": ["science fiction", "sci-fi", "space opera", "dystopian", "cyberpunk"]
    },
    "82-312.4": {
      "notation": "82-312.4",
      "name": "Literature - Fiction - Suspense, Thrillers, Mystery",
      "parent": "82-31",
      "keywords": ["mystery", "thriller", "suspense", "detective", "crime fiction"]
    },
    "82-312.9": {
      "notation": "82-312.9",
      "name": "Literature - Fiction - Fantasy",
      "parent": "82-31",
      "keywords": ["fantasy", "epic fantasy", "urban fantasy", "magic", "sword and sorcery"]
    },
    "82-32": {
      "notation": "82-32",
      "name": "Literature - Short stories",
      "parent": "8",
      "keywords": ["short stories", "anthology", "collected stories"]
    },
    "82-93": {
      "notation": "82-93",
      "name": "Literature - Children's literature. Juvenile literature",
      "parent": "8",
      "keywords": ["children's literature", "juvenile fiction", "young adult", "ya fiction", "children"]
    },
    "9": {
      "notation": "9",
      "name": "Geography. Biography. History",
      "keywords": ["history", "biography", "memoir", "geography", "travel", "autobiography"]
    }
  },
  "dewey_crosswalk": {
    "800": "8",
    "813": "82-31",
    "823": "82-31",
    "500": "5",
    "600": "6",
    "900": "9"
  }
}
```

---

## 3. Resolution Rules

1. **Exact Subject Keyword Match**: Match subject token sets against class keywords. Deepest subclass notation wins (e.g. `"science fiction"` selects `82-311.9` over parent `82-31`).
2. **Dewey/LCC Crosswalk Fallback**: If subject keywords don't match but Dewey classification is present in catalog metadata (e.g., `813.54`), map the 3-digit prefix to the corresponding UDC notation.
3. **Broad Parent Fallback**: If specific genre details are ambiguous but broad subject exists (e.g., "Fiction"), assign parent class `82-31`.
4. **Graceful None**: If no keywords or classification codes match, return `None` (unclassified). Do not raise exceptions or abort processing.
