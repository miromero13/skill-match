# Local Whisper runtime for theory exam testing

The runtime runs locally on CPU using the installed Whisper assets. A prior synthetic probe found semantic transcription errors. `THEORY_ASR_ENABLED` controls whether the local runtime may be exercised; enabling it is for team validation and does not certify model quality.

## Provenance

- Runtime: existing pinned `sherpa-onnx==2.0.1`, offline Whisper Spanish transcription on CPU.
- Model: multilingual Whisper Tiny, encoder int8 and decoder float; not the English-only `.en` variant.
- Conversion repository: `csukuangfj/sherpa-onnx-whisper-tiny`, revision `65176e2deb88badc814a94058666cadccc29b61c`.
- Official Sherpa source links this conversion repository: https://github.com/k2-fsa/sherpa/blob/master/docs/source/onnx/spoken-language-identification/pretrained_models.rst
- Original Whisper license: MIT, https://github.com/openai/whisper/blob/main/LICENSE; copied in `LICENSE.whisper`. This notice is not independent legal clearance of converted artifacts.
- Artifact URLs, byte counts and SHA256 are in `manifest.json`. ONNX hashes were compared with published LFS SHA256 identifiers. The vocabulary's Git blob hash was checked against the published repository tree and its SHA256 recorded.

Only these three verified artifacts were installed, without overwrite, in the isolated SM-39 worktree's ignored `backend/app/models/weights/theory-whisper/` directory. No application data, dependency manifests or global configuration were changed. They are not committed, not installed in the original checkout, and never downloaded while handling an exam request.

## Observed native result

A local operating-system voice generated WAV PCM Spanish speech, without cloud services or human recordings:

> Las listas de Python son mutables, mientras que las tuplas son inmutables.

Actual native transcript, job62:

> las elistas de príton son mutables, mientras que las tuple son bien mutables.

Inference completed in0.523s. The initial smoke script exited0 because it only asserted nonempty output containing `listas` and `mutables`; those assertions were insufficient. Manual comparison of the already produced transcript demonstrates that the negation/property distinction was not preserved. **This is a failed content-fidelity check, not a successful efficacy benchmark.** No retry, threshold weakening or model substitution was used to claim success.

## What remains

A representative Spanish evaluation set must include negation, technical vocabulary, paraphrases, accents, silence/noise and different microphones. Compare against known transcripts and human judgments before enabling an exam model. A synthetic sample cannot establish recognition efficacy, accessibility, semantic grading correctness or production readiness.

Local-only transcriber execution does not implement the requested semantic answer grader. No Gemini/OpenAI API is called here.
