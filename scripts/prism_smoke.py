"""Send one live trace to PRISM to confirm the connection. No model key needed."""
import os, time, uuid
from prismtrace import PRISMtrace

client = PRISMtrace(
    api_key=os.environ["PRISM_API_KEY"],
    host=os.environ["PRISM_HOST"],
    project_id=os.environ["PRISM_PROJECT_ID"],
)
session = f"smoke-{uuid.uuid4().hex[:8]}"
client.trace_llm(
    model="stub-no-model",
    input_messages=[{"role": "user", "content": "Which deals should Dustin Brinkmann's team work this week?"}],
    output="(connection check) No model was called; this trace only verifies ingest.",
    latency_ms=1,
    agent_name="pipeline-review-v0",
    session_id=session,
    metadata={"version": "v0", "purpose": "smoke-test"},
)
client.flush(timeout=10)
client.close()
print("sent", session)
