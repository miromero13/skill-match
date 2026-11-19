# Whisper Base: bounded Spanish candidate evaluation

**Not approved for examinations.** A second candidate still changed a meaning-bearing negation. No application code, readiness guard, grading policy or pass threshold was changed to approve it.

## Candidate and execution

- Local multilingual Whisper Base float32 encoder/decoder with existing Sherpa runtime, Spanish transcription on CPU.
- Conversion: `csukuangfj/sherpa-onnx-whisper-base`, revision `bb53ee204431c90d314c1cc08d28d23e5b7927cc`.
- Published LFS SHA256/byte counts checked for both ONNX files; vocabulary SHA256 checked against the identical verified vocabulary from the previous candidate. Full URLs, sizes and hashes are in `manifest.json`.
- Provision job65 completed without overwrite, preserving Tiny. Files reside only in ignored isolated-worktree `backend/app/models/weights/theory-whisper-base/`; no application records or cloud inference.
- Local OS voices Mónica and Paulina synthesized five fixed statements each, ten WAVs total. Expectations were saved before inference. No human recordings or application questions were read or modified.
- Evaluation job66 exited1:4/10 exact normalized matches. All expectations, transcripts and measured timings are in `synthetic-results.json`; raw audio remains ignored scratch only.

## Interpretation

Normalization removes case, accents and punctuation, but does not rewrite words or convert numbers. Two mismatches were benign formatting equivalents: `quince, no cincuenta` became `15, no 50`. Therefore4/10 exact agreement is **not** the semantic accuracy of this model.

The decisive failure occurs with both voices:

- Expected: `Una lista no es inmutable. Una tupla no es mutable.`
- Mónica: `Una lista no es inmutable, una tuplana no es inmutable.`
- Paulina: `una lista no es inmutable, una tupla no es inmutable`

The second sentence reverses the property distinction. Other cases also merge technical words with the negation, such as `tuplano` or `tu plano`. Correctly preserving the intentionally wrong statement in another case is desirable transcription behavior: an ASR engine must transcribe the speaker, not silently correct knowledge.

There was one candidate evaluation, no retry, no edited expectations and no lowered threshold. Synthetic examples neither establish real-user efficacy nor replace independent review. The original Tiny failure remains documented separately. `APPROVED_FOR_EXAMS` remains false and no semantic answer grader exists.

## Remaining decision

A trustworthy oral-certification pipeline needs representative Spanish/human-audio validation and an explicitly permitted grading approach. Do not enable real attempts based only on these synthetic results or successful native execution.
