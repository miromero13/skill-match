# SM-40 — Programming sandbox

SM-40 evaluates the practical programming stage after the member completes the SM-39 theory stage. It does not use a generative model to decide whether code is correct.

## Flow

1. ADMIN creates a draft challenge for a catalog skill and level at `/admin/programming`.
2. ADMIN adds public and hidden stdin/stdout test cases.
3. ADMIN publishes the draft. Publishing archives the previous published version for the same skill and level.
4. The MEMBER completes theory and opens `/evaluation/:id/code`.
5. The backend resolves the published challenge for the evaluation's theory level.
6. Public runs execute without consuming a submission. A final submission executes all tests and is stored.

`/admin/capture` remains the dataset collection path. Its programming samples can support future curated challenges or local models, but samples are not exposed directly as exams.

## Execution controls

The runner uses a pre-pulled Docker image with no network, no capabilities, no privilege escalation, read-only source mount, a temporary `/tmp`, CPU/memory/process limits, a timeout, and bounded stdout/stderr. The image is configured with `SANDBOX_DOCKER_IMAGE`; deployment must pull and validate it before serving submissions. The request path never downloads images.

The backend parses Python with `ast` before execution and rejects dangerous imports/calls. Test correctness is determined by exit status, timeout, bounded output, and normalized stdout equality. AST quality metrics belong to SM-41; solution defense belongs to SM-42.

## Configuration

- `SANDBOX_DOCKER_IMAGE`: pre-pulled Python image.
- `SANDBOX_DOCKER_BINARY`: Docker-compatible executable.
- `SANDBOX_MAX_CONCURRENT_RUNS`: process concurrency cap.

The current frontend exposes Python-only authoring and execution. Docker integration and real browser validation must be verified in an environment with the configured image and daemon; unit tests do not prove container escape resistance.
