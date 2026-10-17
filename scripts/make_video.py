"""Rebuild the backup demo video from the running UIs and the PRISM screenshots.

12 slides, ~90 s: UI pages shot headless from :8787/:8788 (1440x900), PRISM pages from
docs/screenshots/, each with a caption band, concatenated by ffmpeg.

    ./scripts/demo_up.sh && .venv/bin/python scripts/make_video.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "video"
SHOTS = OUT / "shots"
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
W, H, BAND = 1440, 900, 150

SLIDES = [  # (source, caption lines, seconds) — source is a URL to shoot or a file under docs/screenshots
    ("http://localhost:8787/?deal=P9VFKNR0", [
        "Every month a finance team signs a forecast built from a CRM that reps fill in optimistically.",
        "Ledger reads what the buyer actually said on every deal and shows a receipt for every claim.",
        "Commit $274,814 · best case $472,060 · and why each excluded dollar is excluded, one click away."], 8),
    ("http://localhost:8787/?view=proof", [
        "Same 235 deals, outcomes hidden, every model call through Nicrron (Claude Sonnet 5.5).",
        "CRM rules: 0% of the semantic problems. The same model asked to 'find the issues': 72% recall,",
        "10 of 86 clean deals flagged, 6 invented numbers. Ledger: 94% recall, 99% precision, 0 and 0."], 9),
    ("http://localhost:8787/?deal=P9VFKNR0", [
        "Dontechi · GTXPro. CRM says Negotiation, close Nov 13. Ledger says 10% and four receipts:",
        "buyer 'suspend all new vendor onboarding' vs the stage · the close date vs a paused buyer ·",
        "rep 'engagement remains high' after that — happy ears · auto-reply: the champion left."], 8),
    ("http://localhost:8787/?deal=OEBJXZN6", [
        "The sibling Dontechi deal: the naive agent rates it 75% on 'Nadia Osei approved it'.",
        "Ledger: primary contact left Dontechi, per the auto-reply on the other deal.",
        "A rules engine can't do that. A rep in a hurry won't."], 7),
    ("http://localhost:8787/?version=v1&deal=CMCVD0N8", [
        "Warephase · GTXPro, naive agent: the buyer wrote '2 units at list, so $14,463 total' —",
        "and the model copies $14,463 straight into the forecast."], 6),
    ("http://localhost:8787/?deal=CMCVD0N8", [
        "Ledger on the same deal: 2 × $4,821 is $9,642. The buyer's own arithmetic, caught before a PO.",
        "The model reads; code compares; nothing without a quote is shown."], 7),
    ("http://localhost:8788/?deal=2003", [
        "Live: an 8-deal HubSpot export a judge can edit, run through Nicrron in seconds.",
        "Fabrikam: contact left + a 31-day-old 'PO next week' + the sibling deal still listing her.",
        "Draft CRM corrections a human approves; export in the CRM's own columns."], 8),
    ("prism_14_session_steps.jpg", [
        "PRISM proof 1 — Sessions → Steps: every deal is a 12-step run.",
        "plan · crm · rules · claim ledger · verification · checks · assessment · decide · quote verifier · answer."], 7),
    ("prism_15_alert_fired.jpg", [
        "PRISM proof 2 — an alert that matters: 'model call stalled > 20 s'.",
        "Fired on a real run this morning: 25,942 ms on a naive-agent batch."], 6),
    ("prism_16_agent_intelligence.jpg", [
        "PRISM proof 3 — PRISM's own words on the naive agent: 'Agent fabricates deal data on pipeline",
        "reviews, undermining sales forecasting reliability … add guardrails to prevent deal fabrication.'",
        "That is the Ledger design."], 9),
    ("prism_17_root_cause.jpg", [
        "Root Cause: the ledger-v1 cluster — this morning's naive runs, unsupported answers, no recovery —",
        "and the ledger-v3 cluster whose last failure is yesterday: same deals, nothing since the fix.",
        "PRISM also clustered 470 of our runs as failures: finding 18, fixed, re-proved 17/17 rules."], 9),
    ("http://localhost:8787/?digest=1", [
        "Monday digest per rep and manager: new, recurring, resolved, promises past due, forecast delta.",
        "A forecast without receipts is a guess with a nice spreadsheet. Ledger gives finance the receipts."], 7),
]


def shoot(url: str, path: Path) -> None:
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                    "--virtual-time-budget=20000", f"--screenshot={path}", url], check=True, capture_output=True, timeout=90)


def font(size: int):
    for f in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(src: Path, lines: list[str], idx: int, total: int) -> Image.Image:
    im = Image.open(src).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    frame = Image.new("RGB", (W, H + BAND), (14, 17, 23))
    frame.paste(im, (0, 0))
    d = ImageDraw.Draw(frame)
    f, y = font(26), H + 14
    for line in lines:
        d.text((24, y), line, fill=(236, 239, 244), font=f); y += 32
    d.text((W - 90, H + BAND - 30), f"{idx + 1}/{total}", fill=(150, 160, 175), font=font(20))
    return frame


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); SHOTS.mkdir(exist_ok=True)
    entries = []
    for i, (src, lines, secs) in enumerate(SLIDES):
        if src.startswith("http"):
            shot = SHOTS / f"shot_{i:02d}.png"
            shoot(src, shot)
        else:
            shot = ROOT / "docs" / "screenshots" / src
            if not shot.exists():
                print(f"skip {src}: missing", file=sys.stderr); continue
        out = OUT / f"frame_{i:02d}.png"
        compose(shot, lines, i, len(SLIDES)).save(out)
        entries.append((out.name, secs)); print(f"frame {i:02d} <- {src} ({secs}s)")
    lines = [f"file '{n}'\nduration {s}" for n, s in entries] + [f"file '{entries[-1][0]}'"]
    (OUT / "frames.txt").write_text("\n".join(lines) + "\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "frames.txt"),
                    "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(OUT / "ledger_demo_backup.mp4")],
                   check=True, cwd=OUT)
    total = sum(s for _, s in entries)
    print(f"wrote {OUT / 'ledger_demo_backup.mp4'}: {len(entries)} slides, {total}s")


if __name__ == "__main__":
    main()
