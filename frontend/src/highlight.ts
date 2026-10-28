import type { Finding } from "./types";

export interface SafeSpan {
  start: number;
  end: number;
  fallback: boolean;
}

// Convert backend code-point offsets to safe JavaScript slice indexes.
// Highlight only if the exact quote matches.
export function locateFinding(
  text: string,
  finding: Pick<Finding, "span">
): SafeSpan | null {
  const { start, end, quote } = finding.span;
  const chars = Array.from(text);

  if (
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 0 &&
    end > start &&
    end <= chars.length
  ) {
    const jsStart = chars.slice(0, start).join("").length;
    const jsEnd = chars.slice(0, end).join("").length;

    if (text.slice(jsStart, jsEnd) === quote) {
      return {
        start: jsStart,
        end: jsEnd,
        fallback: false
      };
    }
  }

  // Only use a quote fallback if exactly one match exists.
  if (!quote) return null;

  const i = text.indexOf(quote);

  if (i < 0 || text.indexOf(quote, i + 1) >= 0) {
    return null;
  }

  return {
    start: i,
    end: i + quote.length,
    fallback: true
  };
}

export function replaceFinding(
  text: string,
  finding: Finding
): string | null {
  if (finding.suggested_replacement === null) {
    return null;
  }

  const span = locateFinding(text, finding);

  if (!span) return null;

  return (
    text.slice(0, span.start) +
    finding.suggested_replacement +
    text.slice(span.end)
  );
}