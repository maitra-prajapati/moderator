import {
  describe,
  expect,
  it
} from "vitest";

import {
  locateFinding,
  replaceFinding
} from "../src/highlight";

import type { Finding } from "../src/types";

const f = (
  start: number,
  end: number,
  quote: string
) => ({
  span: { start, end, quote }
});

describe("Unicode-safe finding spans", () => {
  it("maps Python code-point offsets across emoji to UTF-16", () => {
    expect(
      locateFinding(
        "🚀 Try Flow Pilot",
        f(6, 16, "Flow Pilot")
      )
    ).toEqual({
      start: 7,
      end: 17,
      fallback: false
    });
  });

  it("uses unique quote as fallback only", () => {
    expect(
      locateFinding(
        "a Flow Pilot b",
        f(99, 110, "Flow Pilot")
      )
    ).toEqual({
      start: 2,
      end: 12,
      fallback: true
    });

    expect(
      locateFinding(
        "Flow Pilot and Flow Pilot",
        f(99, 110, "Flow Pilot")
      )
    ).toBeNull();
  });

  it("refuses mismatched or ambiguous quote locations", () => {
    expect(
      locateFinding(
        "Hello",
        f(0, 4, "World")
      )
    ).toBeNull();
  });

  it("replaces only the verified quote", () => {
    const finding = {
      ...f(0, 10, "Flow Pilot"),
      suggested_replacement: "FlowPilot"
    } as Finding;

    expect(
      replaceFinding(
        "Flow Pilot works",
        finding
      )
    ).toBe("FlowPilot works");
  });
});