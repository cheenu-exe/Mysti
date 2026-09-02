"""Prompt-injection and secret-leak detection."""

from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionCheck:
    is_safe: bool
    risk_level: str
    patterns_matched: list[str]
    recommended_action: str


class InjectionDetector:
    _patterns = (
        "ignore previous instructions",
        "ignore all previous",
        "disregard your instructions",
        "new instructions:",
        "system prompt:",
        "you are now",
        "act as",
        "pretend to be",
        "roleplay as",
        "dan mode",
        "jailbreak",
    )
    _secret = re.compile(r"(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN .* PRIVATE KEY-----)")

    async def check_input(self, text: str) -> InjectionCheck:
        return self._check(text, output=False)

    async def check_output(self, text: str) -> InjectionCheck:
        return self._check(text, output=True)

    def _check(self, text: str, output: bool) -> InjectionCheck:
        lowered = unicodedata.normalize("NFKC", text).lower()
        matched = [p for p in self._patterns if p in lowered]
        if any(ord(c) > 127 and unicodedata.category(c).startswith("L") for c in text):
            matched.append("unicode confusable")
        compact = re.sub(r"\s+", "", text)
        if len(compact) >= 24 and re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
            try:
                decoded = (
                    base64.b64decode(compact, validate=True)
                    .decode("utf-8", errors="ignore")
                    .lower()
                )
                if any(p in decoded for p in self._patterns):
                    matched.append("base64 encoded injection")
            except (ValueError, UnicodeError):
                pass
        if output and self._secret.search(text):
            matched.append("secret or API key leak")
        critical = output and any(
            x in matched for x in ("secret or API key leak", "system prompt:")
        )
        risk = (
            "critical"
            if critical
            else "high" if len(matched) >= 2 else "medium" if matched else "low"
        )
        return InjectionCheck(
            not matched, risk, matched, "block and review" if matched else "allow"
        )
