import { describe, expect, it } from "vitest"
import {
  evidencePayload,
  safeEvidenceUrl,
  validateEvidence,
} from "@/types/skill-evidence"

describe("evidence contract", () => {
  it.each([
    "javascript:alert(1)",
    "file:///tmp/x",
    "/relative",
    "https://user:secret@example.com",
    "https://@example.com",
  ])("rejects unsafe links: %s", (url) => {
    expect(safeEvidenceUrl(url)).toBeNull()
  })
  it("normalizes and preserves path/query/fragment", () => {
    expect(safeEvidenceUrl("HTTPS://EXAMPLE.COM:443/a?x=1#b")).toBe(
      "https://example.com/a?x=1#b"
    )
  })
  it("produces a complete PUT body without server fields", () => {
    expect(
      evidencePayload({
        title: " Project ",
        description: "  ",
        url: "https://example.com",
        evidence_type: "OTHER",
      })
    ).toEqual({
      title: "Project",
      description: null,
      url: "https://example.com/",
      evidence_type: "OTHER",
    })
  })
  it("validates required text and expanded URL length", () => {
    const errors = validateEvidence({
      title: "  ",
      description: "x".repeat(2001),
      url: "https://example.com/" + "é".repeat(500),
      evidence_type: "VIDEO",
    })
    expect(errors.title).toBeTruthy()
    expect(errors.description).toBeTruthy()
    expect(errors.url).toBeTruthy()
  })
})
