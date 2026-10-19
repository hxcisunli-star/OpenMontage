"""Narration / script lint for a whiteboard lesson, shared by every lesson (replaces the FORB / JARGON / statistics copies inside each build_script.py).
Run:  .venv/bin/python docs/whiteboard_script_lint.py projects/<lesson> [--lesson N] [--allow 词1,词2] [--target SECONDS] [--json]      exit code 1 on any ERROR
Checks on artifacts/script.json (rules apply from lesson 11, when the plain-language assertions started):
  ERROR  English letters or Arabic digits in the narration (numbers are spoken in Chinese characters; commands and file names live on the board only)
  ERROR  a hard word from docs/whiteboard/wordlist.yaml (from >= its lesson, not allowed for this lesson); --allow lists this lesson's NEW terms (then say each once, with a plain sentence)
  ERROR  average sentence > 24 characters or longest sentence > 50 (split at full stops, do not change the word count)
  ERROR  a section longer than 600 characters, or two neighbouring picture cues more than 10 s apart
  ERROR  a quiz question text that is not in the narration exactly once
  ERROR  planned duration (characters x 0.238 s + 3 s per quiz silence + 0.7 s between sections) outside 360-480 s;  WARN more than 8 % from the proposal target
It also prints the character budget for the target so the first draft lands in range (13 lessons had a first draft that was too short or too long)."""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whiteboard_lessons import number_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPC, QUIZ_SIL, GAP = 0.238, 3.0, 0.7
AVG_MAX, SENT_MAX, SECTION_MAX, CUE_GAP_MAX = 24, 50, 600, 10
RANGE = (360, 480)
STRICT_FROM = 11


def load_terms():
    return yaml.safe_load((ROOT / "docs/whiteboard/wordlist.yaml").read_text(encoding="utf-8"))["terms"]


def lint(script, lesson, allow=(), target=None):
    secs = script["sections"]
    meta = script.get("metadata", {})
    text = "".join(s["text"] for s in secs)
    errors, warns, info = [], [], {}
    sents = [x for x in re.split(r"[。？！]", text) if x.strip()]
    lens = [len(x) for x in sents]
    info.update(characters=len(text), sentences=len(sents), avg_sentence=round(statistics.mean(lens), 1), max_sentence=max(lens))
    if lesson is not None and lesson < STRICT_FROM:
        info["note"] = f"lesson {lesson} < {STRICT_FROM}: the rules were not in force yet, nothing checked"
        return errors, warns, info
    ascii_words = sorted(set(re.findall(r"[A-Za-z]+", text)))
    digits = re.findall(r"[0-9]", text)
    if ascii_words:
        errors.append(f"English letters in the narration: {ascii_words[:8]}")
    if digits:
        errors.append(f"{len(digits)} Arabic digit(s) in the narration (say the number in Chinese characters)")
    for term, spec in load_terms().items():
        n = lesson if lesson is not None else 999
        if n >= spec.get("from", STRICT_FROM) and n not in (spec.get("allow_in") or []) and term not in allow and term in text:
            where = next((s["id"] for s in secs if term in s["text"]), "?")
            errors.append(f"hard word “{term}” x{text.count(term)} (first in {where}); say it plainly, or --allow it as this lesson's new term")
    if info["avg_sentence"] > AVG_MAX:
        errors.append(f"average sentence {info['avg_sentence']} > {AVG_MAX}")
    if info["max_sentence"] > SENT_MAX:
        long = max(sents, key=len)
        errors.append(f"longest sentence {info['max_sentence']} > {SENT_MAX}: {long[:40]}…")
    for s in secs:
        if len(s["text"]) > SECTION_MAX:
            errors.append(f"section {s['id']} has {len(s['text'])} characters > {SECTION_MAX}")
    ts = [c["timestamp_seconds"] for s in secs for c in s.get("enhancement_cues", [])]
    gaps = [(round(b - a, 1), round(a, 1)) for a, b in zip(ts, ts[1:])]
    info["max_cue_gap"] = max((g for g, _ in gaps), default=0)
    for g, at in gaps:
        if g > CUE_GAP_MAX:
            errors.append(f"picture cues {g}s apart after {at}s (> {CUE_GAP_MAX}); split the long event in two")
    quiz = meta.get("quiz_pauses", [])
    for q in quiz:
        c = text.count(q["after_exact_text"])
        if c != 1:
            errors.append(f"quiz text {q['after_exact_text']!r} appears {c} times (must be exactly once)")
    est = len(text) * SPC + QUIZ_SIL * len(quiz) + GAP * (len(secs) - 1)
    info["planned_seconds"] = round(est, 1)
    tgt = target or meta.get("proposal_target_seconds")
    if tgt:
        chars = (tgt - QUIZ_SIL * len(quiz) - GAP * (len(secs) - 1)) / SPC
        info.update(target_seconds=tgt, target_characters=round(chars), budget_characters=[round(chars * 0.97), round(chars * 1.03)])
        if abs(est - tgt) / tgt > 0.08:
            warns.append(f"planned {est:.0f}s is {100 * (est - tgt) / tgt:+.0f}% from the target {tgt}s (budget {info['budget_characters'][0]}-{info['budget_characters'][1]} characters; measured speech has been 1-9 % shorter than planned)")
    if not RANGE[0] <= est <= RANGE[1]:
        errors.append(f"planned duration {est:.0f}s outside {RANGE[0]}-{RANGE[1]}s")
    return errors, warns, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--lesson", type=int)
    ap.add_argument("--allow", default="")
    ap.add_argument("--target", type=float)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    proj = Path(args.proj)
    script = json.loads((proj / "artifacts/script.json").read_text(encoding="utf-8"))
    lesson = args.lesson or number_of(proj.name)
    errors, warns, info = lint(script, lesson, [w for w in args.allow.split(",") if w], args.target)
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warns, "info": info}, ensure_ascii=False, indent=1))
    else:
        for w in warns:
            print("WARN ", w)
        for e in errors:
            print("ERROR", e)
        print(f"script lint (lesson {lesson}): {len(errors)} error(s), {len(warns)} warning(s)  {info}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
