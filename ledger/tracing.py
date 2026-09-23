"""PRISM wiring. Every model call and every agent run goes through here.

Set PRISM_DISABLED=1 to run without sending anything (e.g. while iterating on prompts,
to protect the 100/day analysis quota on the free tier).
"""
from __future__ import annotations

import os
import atexit
from functools import lru_cache

from prismtrace import PRISMtrace


@lru_cache(maxsize=1)
def client() -> PRISMtrace | None:
    if os.getenv("PRISM_DISABLED") == "1" or not os.getenv("PRISM_API_KEY"):
        return None
    c = PRISMtrace(api_key=os.environ["PRISM_API_KEY"], host=os.environ["PRISM_HOST"],
                   project_id=os.environ["PRISM_PROJECT_ID"])
    atexit.register(lambda: (c.flush(timeout=10), c.close()))
    return c


def trace_llm(*, version: str, model: str, messages: list[dict], output: str, latency_ms: int,
              tokens_in: int, tokens_out: int, session_id: str, metadata: dict | None = None) -> None:
    c = client()
    if c is None:
        return
    c.trace_llm(model=model, input_messages=messages, output=output, latency_ms=latency_ms,
                token_count_input=tokens_in, token_count_output=tokens_out,
                agent_id="ledger", agent_name=f"ledger-{version}", session_id=session_id,
                metadata={"version": version, **(metadata or {})})


def trajectory(*, version: str, session_id: str, steps: list[dict], model: str,
               final_status: str = "success") -> None:
    """Ordered steps of one run. Verifier verdicts appear here as steps named check:*."""
    c = client()
    if c is None:
        return
    c.submit_trajectory(steps, agent_id="ledger", agent_name=f"ledger-{version}",
                        conversation_id=session_id, model=model, final_status=final_status)


def step(label: str, output: str, *, tool: str | None = None, input_summary: str = "",
         status: str = "success") -> dict:
    # PRISM's Task Completion rule (CORR-001) looks for a step_type of final_answer.
    kind = "tool_call" if tool else ("final_answer" if label == "final_answer" else "reasoning")
    s = {"step_type": kind, "label": label,
         "output_summary": output[:2000], "status": status}
    if tool:
        s["tool_name"] = tool
    if input_summary:
        s["input_summary"] = input_summary[:2000]
    return s
