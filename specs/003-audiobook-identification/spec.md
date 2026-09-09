# Feature Specification: Audiobook Identification and Author Disambiguation

**Feature Branch**: `003-audiobook-identification`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "audiobooks: Best efforts should be made to identify the work being processed as well as the author, automatically. User configurable external services can be used."

## Clarifications

### Session 2026-09-08
- Q: Which external book metadata service(s) should be supported out-of-the-box as built-in provider adapters? → A: Open Library as the zero-configuration default, with Audnexus supported as an optional specialized audiobook provider.
- Q: When an external metadata service returns details that differ from embedded audio tags, what precedence rule should decide the authoritative author and title? → A: External matches override local author/title only when match confidence meets or exceeds a strict threshold (≥85%); otherwise local tags are preserved and external data only populates missing fields.
- Q: How should the identification engine group multi-file audiobooks into a single cohesive work before querying external services? → A: Album tag consensus with folder fallback (aggregating files sharing album tags across parent and disc subfolders; falling back to top-level parent directory name when tags are absent).
- Q: How should the system distinguish audiobooks from standard music files when processing incoming audio files? → A: Extension & path hint with spoken-word fallback (.m4b files and paths containing "audiobook" are classified as audiobooks immediately; general audio like .mp3/.m4a uses book lookup when in audiobook paths or lacking standard music tags).
- Q: Should external metadata lookup responses be cached locally across pipeline runs to minimize external API requests and respect rate limits? → A: Persistent file cache (caching external query results locally on disk with configurable TTL, defaulting to 30 days, across pipeline runs).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Local & External Identification for Single-File Audiobooks (Priority: P1)

An audiobook listener adds a standalone audiobook file (e.g., `.m4b` or `.mp3`) to their ingestion or staging folder. The system extracts local metadata (embedded audio tags and filename cues), checks configured external lookup services to verify and refine the work title and author name, and enriches the media asset with canonical author and title information for subsequent organization.

**Why this priority**: Single-file audiobooks represent the most common self-contained distribution format. Delivering accurate, zero-configuration-required author and title detection for single files provides an immediate, independently testable MVP.

**Independent Test**: Ingest a standalone `.m4b` file with partial or messy tags; verify the system accurately discovers the author and clean work title via embedded metadata and the primary external service without human intervention.

**Acceptance Scenarios**:

1. **Given** a single `.m4b` file with embedded tags indicating a known title and author, **When** the pipeline processes the file with an external lookup service enabled, **Then** the system confirms and standardizes the author name and work title and marks the asset as an identified audiobook.
2. **Given** a single `.mp3` audiobook file with missing or stripped tags but a recognizable filename (e.g., `Author - Book Title.mp3`), **When** processed by the identification system, **Then** the system parses filename candidate tokens, queries the external service, and accurately populates the author and title.
3. **Given** an external service is unavailable or times out, **When** a single-file audiobook is processed, **Then** the system falls back gracefully to local embedded tags and filename heuristics without crashing or halting the batch.

---

### User Story 2 - Multi-File Audiobook Bundle Identification (Priority: P2)

An audiobook listener adds a folder containing multiple chapter audio files (e.g., `Author - Title/Track 01.mp3`, `Track 02.mp3`, or nested disc subfolders like `CD1/`, `Part 2/`). The system recognizes the folder structure as a unified audiobook work rather than treating each audio file as an independent disjoint track, extracts consistent album- and folder-level author and title metadata via album tag consensus (falling back to parent directory naming if tags are absent), confirms the work via external lookup, and associates all constituent chapter files with the identified book work.

**Why this priority**: Many audiobooks are distributed as multi-track directories (chapter-based or multi-disc). Recognizing these files collectively as a single book prevents library clutter and avoids fragmented, mismatched tracks or redundant per-track API queries.

**Independent Test**: Provide a folder containing 10 chapter `.mp3` files across `CD1/` and `CD2/` subdirectories with identical album tags; verify the system outputs a single coherent audiobook identification with the shared author and work title applied across the entire bundle.

**Acceptance Scenarios**:

1. **Given** a directory containing multiple chapter audio files sharing a common album tag (even when arranged in disc subfolders), **When** the system scans the directory, **Then** it aggregates candidate cues to identify the single overarching book work and author without issuing duplicate queries per chapter.
2. **Given** a multi-file audiobook folder with absent or stripped embedded tags, **When** processed, **Then** the system uses the top-level parent folder name as the fallback bundle seed to discover the author and title.

---

### User Story 3 - Configurable External Metadata Services & Cascade Priority (Priority: P3)

A library administrator configures preferred external book metadata providers (with built-in support for Open Library as the zero-configuration default and Audnexus as an optional specialized audiobook provider) in the configuration file or environment variables, specifying provider priority, API endpoints, credentials (where required), and timeouts.

**Why this priority**: Different users rely on different catalogs or have varying network constraints. Allowing configurable external providers enables users to tailor lookup accuracy, respect rate limits, and choose open or specialized services.

**Independent Test**: Configure two external services in priority order; verify that the system queries the primary provider first and only invokes the secondary provider if the first produces no confident match or fails.

**Acceptance Scenarios**:

1. **Given** multiple external services configured in priority order, **When** looking up an audiobook, **Then** the system queries providers sequentially according to configured priority until a confident match is found.
2. **Given** an administrator disables all external services in configuration, **When** an audiobook is processed, **Then** the system operates entirely in local-only mode relying on embedded tags and filename heuristics.
3. **Given** an external provider configuration specifies custom network timeouts or rate limits, **When** queries are made, **Then** the system adheres strictly to the configured limits and aborts slow queries cleanly.

---

### User Story 4 - Ambiguity Resolution & Confidence Reporting (Priority: P4)

An operator runs the pipeline or inspects dry-run output on ambiguous or poorly-tagged audiobooks. The system computes a confidence score for external and local matches, safely defaults to preserving local cues when external candidates are ambiguous, and emits structured telemetry indicating the source, confidence level, and match details.

**Why this priority**: Prevents incorrect classification (false positives) when book titles are common or ambiguous, and provides clear visibility for automated cron operations.

**Independent Test**: Run pipeline with an audiobook file whose title matches multiple disparate books; verify the system evaluates author correspondence, selects the candidate exceeding the confidence threshold or falls back safely, and reports the match confidence in telemetry.

**Acceptance Scenarios**:

1. **Given** an external service query returning multiple search candidates, **When** one candidate matches both title and author with high confidence (≥85%), **Then** that candidate's canonical title and author are applied.
2. **Given** an external query returning candidate matches where confidence is below 85% or author conflicts, **When** evaluated, **Then** the system rejects low-confidence external title/author overrides and retains the local metadata, only adopting non-conflicting missing fields (e.g., narrator or series).
3. **Given** execution with `--dry-run` or `--format json`, **When** identification runs, **Then** the output includes the chosen work title, author, match source (local vs external provider), and confidence score without mutating filesystem state.

---

### Edge Cases

- **Network failures or unreachability**: External APIs experience outages, connection timeouts, or DNS failures during an automated cron run; the system must seamlessly fall back to local tags without failing the pipeline.
- **Multiple authors or contributors**: Books with multiple authors or editors (e.g., "Neil Gaiman & Terry Pratchett"); the system must reliably extract and normalize primary author information without dropping collaborators.
- **Narrator vs. author confusion**: Embedded audio tags frequently place the narrator in the "artist" tag and author in "composer" or "album artist"; the system must correctly distinguish the author of the work from the narrator/performer.
- **Extremely short or generic titles**: Works titled "It", "1984", or "Dune" return large volumes of external results; author verification must be enforced to prevent false-positive matches.
- **Offline / air-gapped environments**: When network access is blocked or disabled, local-only heuristics must operate at full speed without attempting blocked network requests.
- **Rate limiting (HTTP 429)**: When an external service rate-limits queries, the system must respect backoff or gracefully fall back to the next configured provider.
- **Music vs. audiobook disambiguation**: General `.mp3` or `.m4a` files without path hints; the system must avoid misclassifying music tracks as audiobooks by honoring unambiguous music tags and requiring audiobook path hints or spoken-word tags before querying book catalogs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically extract author and work title from embedded audio metadata tags (such as ID3v2, MP4/M4B atoms, Vorbis comments) and filename/directory naming patterns.
- **FR-002**: System MUST identify audiobooks distributed as single audio files (`.m4b`, `.mp3`, `.m4a`, etc.) and multi-file directory structures (chapter tracks within parent and disc subfolders), grouping multi-file works via album tag consensus and falling back to top-level parent folder naming when tags are missing.
- **FR-003**: System MUST support user-configurable external metadata services declared in configuration files and overridable via environment variables, providing built-in adapter implementations for Open Library (default zero-configuration provider) and Audnexus (specialized audiobook provider).
- **FR-004**: System MUST allow configuring multiple external providers with an explicit priority order (defaulting to Open Library first, followed by Audnexus when enabled), querying providers in sequence until a qualifying match is found.
- **FR-005**: System MUST compute a confidence score for candidate metadata matches, requiring a strict confidence threshold (≥85%) before external search results can override existing local author and work title tags.
- **FR-006**: System MUST fall back to local embedded metadata and filename heuristics whenever external services are disabled, unreachable, timed out, rate-limited, or return low-confidence (<85%) results.
- **FR-007**: System MUST provide a local-only operation mode that bypasses all network queries.
- **FR-008**: System MUST extract and preserve secondary audiobook metadata attributes when available, including narrator, series name, volume/book number, and publication year.
- **FR-009**: System MUST guarantee idempotent identification: running identification repeatedly against the same input files produces identical author and title outcomes.
- **FR-010**: System MUST emit structured telemetry and logs detailing the identified work title, author, confidence score, and identification source (local tags, filename heuristic, or external provider name).
- **FR-011**: System MUST support dry-run simulation, predicting and reporting identification results without modifying filesystem paths or file tags.
- **FR-012**: System MUST enforce configurable network timeouts and retry limits on all external API requests to prevent pipeline stalls during automated cron execution.
- **FR-013**: System MUST classify audio files as audiobooks when using `.m4b` extension or located in paths containing "audiobook" keywords; general audio files (`.mp3`, `.m4a`) in non-audiobook paths MUST only trigger audiobook processing if path hints exist or when local tags indicate spoken word / book content.
- **FR-014**: System MUST cache external lookup responses in a local persistent cache file with a configurable time-to-live (TTL, defaulting to 30 days) to minimize external API roundtrips and avoid rate limits across repeated executions.

### Key Entities *(include if feature involves data)*

- **AudiobookAsset**: Represents an identified audiobook work (single file or cohesive multi-file folder), containing clean work title, author, narrator, series title, volume number, publication year, duration, audio format, and identification confidence.
- **ExternalServiceConfig**: Represents a configured external metadata provider, specifying provider identifier (e.g., `openlibrary`, `audnexus`), enabled status, priority order, endpoint URL, optional authentication/API key, request timeout, and rate-limiting parameters.
- **MetadataMatch**: Represents a metadata match candidate evaluated by the identification engine, containing matched title, author, year, external work identifier, provider source name, and calculated confidence score.
- **MetadataCache**: Persistent cache storage containing cached lookup results keyed by normalized title/author query strings, provider source, timestamp, and expiration TTL.
- **IdentificationTelemetry**: Telemetry summary capturing per-file or per-work identification outcomes, match sources, confidence ratings, lookup latencies, cache hit/miss status, and error/fallback events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of standard single-file and multi-file audiobooks containing standard tags or canonical naming patterns are correctly identified with author and title without manual user intervention.
- **SC-002**: External metadata queries complete within 3.0 seconds per title under normal network conditions.
- **SC-003**: 100% of external service interruptions (timeouts, HTTP 429, HTTP 5xx, or network unavailability) fall back to local metadata without crashing the pipeline or leaving orphaned temporary files.
- **SC-004**: Dry-run simulation accurately outputs identified author, title, and match confidence for 100% of tested assets without mutating source files.
- **SC-005**: Zero third-party runtime HTTP dependencies introduced; external network interactions operate using standard, container-safe runtime libraries.
- **SC-006**: Repeated lookups for previously cached audiobook titles resolve from the local cache in under 50 milliseconds without initiating outbound network connections.

## Assumptions

- **Local-first resilience**: The system must remain fully functional in offline or air-gapped environments, relying on embedded metadata and filename heuristics when external lookups are disabled or unavailable.
- **Default provider availability**: Open Library is enabled as the default keyless book metadata service, with Audnexus available as an optional specialized provider for audiobooks (narrator, series, chapter data), while supporting user-defined custom endpoints.
- **Directory cohesion**: In multi-file audiobook directories, files belonging to the same album tag consensus or parent directory hierarchy (including disc subfolders) are grouped as a single unified work.
- **Precedence order**: High-confidence external matches (≥85% match confidence) take precedence to normalize and standardize title, author, and secondary metadata, while local tags take precedence over lower-confidence or ambiguous external results.
- **Persistent cache storage**: The metadata cache is persisted in a dedicated, volume-mountable cache directory (e.g., `.media-cron-cache/` or user-configured path) that does not pollute source or destination media folders.
