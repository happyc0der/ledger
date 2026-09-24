"""PII never leaves for the model. Emails and phone numbers in activity text are replaced with
stable tokens before any prompt is built; the verifier compares against the same redacted text,
and quotes are re-inflated for display. Names are not redacted (they are the evidence)."""
from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")


class Redactor:
    def __init__(self):
        self.map: dict[str, str] = {}

    def redact(self, text: str) -> str:
        def sub(kind, m):
            v = m.group(0)
            tok = next((k for k, val in self.map.items() if val == v), None) or f"<{kind}_{sum(1 for k in self.map if k.startswith('<' + kind)) + 1}>"
            self.map[tok] = v
            return tok
        text = EMAIL.sub(lambda m: sub("email", m), str(text))
        return PHONE.sub(lambda m: sub("phone", m), text)

    def inflate(self, text: str) -> str:
        for tok, v in self.map.items():
            text = str(text).replace(tok, v)
        return text
