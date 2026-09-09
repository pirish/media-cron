# Technical Research: Audiobook Identification and Author Disambiguation

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md)

## Overview & Goals

This research evaluates technical choices for identifying audiobooks, disambiguating authors, querying external book metadata services, caching lookups, and clustering multi-file audiobook directories. In accordance with the Media-Cron Constitution, all implementations must prioritize standard library solutions, container friendliness, strict testability, and zero third-party network runtime dependencies.

---

## 1. External Metadata Provider APIs

### Open Library Books API
- **Role**: Default zero-configuration book metadata provider (free, public, no authentication required).
- **Search Endpoint**: `https://openlibrary.org/search.json?q={query}&limit=5` or `https://openlibrary.org/search.json?title={title}&author={author}&limit=5`
- **Response Format**: JSON containing `docs` array with:
  - `title` (str)
  - `author_name` (list[str])
  - `first_publish_year` (int)
  - `key` (str, work ID e.g. `/works/OL262758W`)
  - `isbn` (list[str])
- **Rate Limits & Guidelines**: Community guidelines request ≤ 1 request per second and an informative `User-Agent` header (`media-cron/1.0 (https://github.com/...)`).
- **Failure Modes**: HTTP 429 (rate-limited), HTTP 503 (maintenance), connection timeouts.
- **Decision**: Adopt Open Library as the default built-in provider for general book and author resolution.

### Audnexus API
- **Role**: Optional specialized audiobook provider providing deep audiobook metadata (ASIN, narrator, series, volume).
- **Search Endpoint**: `https://api.audnexus.com/books?title={title}&author={author}` or `https://api.audnexus.com/books/{asin}`
- **Response Format**: JSON array of matching book objects:
  - `asin` (str)
  - `title` (str)
  - `authors` (list[{"name": str}])
  - `narrators` (list[{"name": str}])
  - `series` (list[{"name": str, "position": str}])
  - `releaseDate` (str)
  - `summary` (str)
- **Authentication**: Zero authentication required for standard endpoints.
- **Decision**: Implement built-in `AudnexusProvider` querying the public Audnexus API, activated when enabled in config or placed in the provider cascade.

### Alternatives Considered
- **Google Books API**: Comprehensive commercial catalog, but unauthenticated requests face strict IP quotas and require Google Cloud Console project keys for reliable throughput. Retained as an architectural extension point rather than default.
- **Audible Direct Scraping**: Fragile, violates Terms of Service, risks IP blacklisting. Rejected in favor of Audnexus API.
- **MusicBrainz**: Excellent for music, but coverage for modern audiobooks and author attribution is sparse compared to dedicated book catalogs.

---

## 2. Confidence Scoring & String Matching

### Requirements
- Compute a normalized similarity score $[0.0, 1.0]$ between candidate metadata and audio file clues.
- Require $\ge 0.85$ (85%) confidence before external metadata is permitted to override local author/title tags.
- Run entirely in pure Python without binary C-extensions (like `python-Levenshtein` or `rapidfuzz`).

### Algorithm Selection
- **Text Normalization**:
  1. Lowercase all text.
  2. Strip common release clutter: `(unabridged)`, `[audiobook]`, `part \d+`, `cd \d+`, `mp3`, `m4b`, `kbps`.
  3. Replace punctuation and underscores with spaces.
  4. Collapse multiple whitespace characters into single spaces.
- **Matching Engine**:
  - Use standard library `difflib.SequenceMatcher` to compute base token similarity ratio.
  - Compute Token Set Similarity: split title and author into word sets to handle word-order variations (e.g., "Tolkien, J.R.R." vs. "J. R. R. Tolkien").
  - Title Similarity ($S_T \in [0.0, 1.0]$) and Author Similarity ($S_A \in [0.0, 1.0]$).
  - Composite Confidence Formula:
    $$\text{Confidence} = 0.55 \times S_T + 0.45 \times S_A$$
  - Penalty Guard: If $S_A < 0.40$ (author completely mismatches despite title matching), cap confidence at $0.40$ to eliminate false-positive book matches on generic titles like "It" or "Dune".
- **Decision**: Implement `ConfidenceScorer` in `media_cron/metadata/scorer.py` using pure Python `difflib` and token sets.

---

## 3. Multi-File Audiobook Bundle Clustering

### Problem
Audiobooks are frequently split into multiple files:
- `Author - Title/01 - Chapter 1.mp3`, `02 - Chapter 2.mp3`
- `Title/CD1/Track01.mp3`, `Title/CD2/Track01.mp3`
Treating each track as an isolated work triggers dozens of redundant API requests and risks mismatched metadata across chapters.

### Clustering Heuristic
1. **Directory Inspection**: When scanning audio files, group items by immediate parent directory, or top-level parent if subdirectories match disc patterns (`cd\s*\d+`, `disc\s*\d+`, `part\s*\d+`).
2. **Tag Consensus**:
   - Inspect embedded tags across all audio tracks in the bundle.
   - Tally the `album` and `artist`/`albumartist`/`composer` values.
   - If $\ge 50\%$ of tracks share an album tag, adopt it as the candidate book title.
   - If tags are missing, parse the parent folder name for `Author - Title` or `Title` patterns.
3. **Single Query Dispatch**:
   - Issue a single external metadata query for the whole bundle.
   - Distribute the resolved `AudiobookAsset` metadata (canonical author, title, year, series, narrator) across all constituent chapter files.
- **Decision**: Implement `AudiobookBundleAggregator` to cluster multi-file audio tracks into cohesive `AudiobookAsset` groups prior to external lookup.

---

## 4. Persistent Response Caching & Rate Limiting

### Requirements
- Persist query results across recurring cron runs.
- Prevent duplicate network calls for unchanged files.
- Configurable TTL (default 30 days).
- Zero external database dependencies (pure file-based JSON).

### Cache Design
- **Storage Location**: Configurable path defaulting to `.media-cron-cache/audiobook_cache.json` (or system/container cache volume).
- **Cache Key**: `hashlib.sha256(f"{provider}:{normalized_title}:{normalized_author}".encode()).hexdigest()`
- **Schema**:
  ```json
  {
    "version": 1,
    "entries": {
      "<cache_key>": {
        "provider": "openlibrary",
        "title_query": "the hobbit",
        "author_query": "j r r tolkien",
        "timestamp": 1725830000.0,
        "ttl_seconds": 2592000,
        "confidence": 0.94,
        "match": {
          "title": "The Hobbit",
          "author": "J.R.R. Tolkien",
          "year": 1937,
          "narrator": null,
          "series": "The Lord of the Rings",
          "volume": "0",
          "work_id": "OL262758W"
        }
      }
    }
  }
  ```
- **Concurrency & Safety**:
  - Atomic writes: serialize JSON to `.audiobook_cache.json.tmp.<pid>` and rename atomically (`os.replace`).
  - Read gracefully ignores corrupted or partial files, resetting safely.
- **Rate Limiting**:
  - Thread-safe or process-level token bucket/last-request timestamp ensuring $\ge 1.0$s interval between requests for Open Library.
- **Decision**: Implement `MetadataCache` in `media_cron/metadata/cache.py`.

---

## 5. Pure Standard Library HTTP Client

### Requirements
- No runtime dependencies on `requests`, `httpx`, or `urllib3`.
- Strict timeout enforcement to avoid hanging cron jobs.
- Clean mockability for automated contract testing.

### Design
- Utilize `urllib.request.urlopen` with explicit timeout (default 5.0 seconds).
- Set descriptive `User-Agent: media-cron/0.3.0 (+https://github.com/pirish/media-cron)`.
- Wrap errors into standard domain exceptions: `ProviderUnavailableError`, `ProviderRateLimitError`, `ProviderTimeoutError`.
- **Decision**: Implement `BaseMetadataProvider` in `media_cron/metadata/base.py` wrapping standard library `urllib.request`.
