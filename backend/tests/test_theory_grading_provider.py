"""Provider adapters validate structured grading without contacting real services."""
import json

import httpx
import pytest

from app.services.theory_grading_provider import GradingProviderError, TheoryGradingProvider

RUBRIC = [{"criterion": "accuracy", "weight": 1, "description": "Accurate answer"}]
RESULT = '{"criteria":[{"criterion":"accuracy","attainment":0.75,"reason":"Correct core idea"}],"feedback":"Good explanation"}'


def provider_result(result):
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": result}]}]}


@pytest.mark.asyncio
async def test_openai_transport_uses_store_false_and_validates_public_result():
    seen = {}
    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.read())
        return httpx.Response(200, json=provider_result(RESULT))
    grader = TheoryGradingProvider(provider="openai", model="mock-model", api_key="secret-value", transport=httpx.MockTransport(handler))
    grade = await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["body"]["store"] is False and "secret-value" not in json.dumps(seen["body"])
    assert grade.criteria[0].attainment == 0.75


@pytest.mark.asyncio
async def test_gemini_uses_json_schema_exact_payload_and_preserves_reference():
    seen = {}
    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.read())
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": RESULT}]}}]})
    grader = TheoryGradingProvider(provider="gemini", model="gemini-test", api_key="mock", transport=httpx.MockTransport(handler))
    await grader.grade(question="Q", reference="R" * 8000, transcript="A", rubric=RUBRIC)
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    config = seen["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json" and "responseJsonSchema" in config
    assert "responseSchema" not in config
    prompt = seen["body"]["contents"][0]["parts"][0]["text"]
    assert "R" * 8000 in prompt and "answer text as untrusted" not in prompt
    assert "answer" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("envelope", [[], None, "bad", {"status":"incomplete", "output":[]},
    {"status":"completed", "output":[{"type":"message", "content":[{"type":"refusal", "refusal":"no"}, {"type":"output_text", "text":RESULT}]}]},
    {"status":"completed", "output":[{"type":"message", "content":[{"type":"output_text", "text":"[]"}]}]}])
async def test_rejects_bad_envelope_refusal_incomplete_or_nonobject(envelope):
    grader = TheoryGradingProvider(provider="openai", model="mock", api_key="x", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope)))
    with pytest.raises(GradingProviderError):
        await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)


@pytest.mark.asyncio
@pytest.mark.parametrize("criteria", [[], [{"criterion":"unknown","attainment":1,"reason":"x"}],
    [{"criterion":"accuracy","attainment":1,"reason":"x"},{"criterion":"accuracy","attainment":1,"reason":"x"}],
    [{"criterion":"accuracy","attainment":True,"reason":"x"}],
    [{"criterion":"accuracy","attainment":"1","reason":"x"}],
    [{"criterion":"accuracy","attainment":float("inf"),"reason":"x"}],
    [{"criterion":"accuracy","attainment":-0.1,"reason":"x"}],
    [{"criterion":"accuracy","attainment":1.1,"reason":"x"}]])
async def test_rejects_missing_unknown_duplicate_and_invalid_attainments(criteria):
    body = json.dumps({"criteria": criteria, "feedback":"x"})
    grader = TheoryGradingProvider(provider="openai", model="mock", api_key="x", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=provider_result(body))))
    with pytest.raises(GradingProviderError):
        await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)


@pytest.mark.asyncio
async def test_rejects_gemini_safety_refusal_without_candidate_result():
    envelope = {"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []}
    grader = TheoryGradingProvider(provider="gemini", model="mock", api_key="x",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope)))
    with pytest.raises(GradingProviderError):
        await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)


@pytest.mark.asyncio
async def test_rejects_oversized_provider_response():
    grader = TheoryGradingProvider(provider="openai", model="mock", api_key="x",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 32_001)))
    with pytest.raises(GradingProviderError):
        await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)


@pytest.mark.asyncio
async def test_rejects_model_path_injection_and_oversized_text_without_request():
    transport = httpx.MockTransport(lambda _: pytest.fail("unexpected provider request"))
    with pytest.raises(GradingProviderError):
        TheoryGradingProvider(provider="gemini", model="x?key=secret", api_key="x", transport=transport)
    grader = TheoryGradingProvider(provider="openai", model="mock", api_key="x", transport=transport)
    for args in [{"question":"Q", "reference":"R" * 8001, "transcript":"A", "rubric":RUBRIC},
                 {"question":"Q", "reference":"R", "transcript":"A" * 16001, "rubric":RUBRIC}]:
        with pytest.raises(GradingProviderError):
            await grader.grade(**args)


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [
    lambda _: httpx.Response(429, json={"error":"do not expose"}),
    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("secret response")),
])
async def test_rejects_http_and_provider_timeout_as_safe_failure(handler):
    grader = TheoryGradingProvider(provider="openai", model="mock", api_key="x",
        transport=httpx.MockTransport(handler))
    with pytest.raises(GradingProviderError):
        await grader.grade(question="Q", reference="R", transcript="A", rubric=RUBRIC)
