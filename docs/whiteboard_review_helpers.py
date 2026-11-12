#!/usr/bin/env python3
"""Helpers for a delegated (托管) gate review: Gemini listens to / watches the material, Codex checks the text and looks at pictures.  Their reports are HINTS for the final
reviewer (a fresh read-only Claude Opus run, `whiteboard_gate.py review ... --helpers <folder>`), never evidence and never a verdict.

  .venv/bin/python docs/whiteboard_review_helpers.py run <project> <stage> [--only gemini|codex] [--keep]
  .venv/bin/python docs/whiteboard_review_helpers.py full <project> <stage>        run, then `whiteboard_gate.py review --helpers` (use it in the BACKGROUND)

Needs the host's `whiteboard_gate.py request <project> <stage>` first (it lists the material and fingerprints it).  What `run` does:
  1. copies the material into /home/MyProject/_scratch/gate-<project>-<stage>-<n>/m/ (WHY.md, INDEX.md; never .env, keys, tokens; refuses a text file that looks like it holds a key or an ip:port);
     videos are shrunk to a 480p proxy (cut in 90 s pieces), pictures and sound are copied as they are
  2. Gemini (agy, read-only, one run per audio file group / video piece): blind transcription of the sound and what is seen on screen, compared by THIS script with the expected text (3+ differing characters = flagged)
  3. Codex sol (read-only, pictures attached with -i, at most 6 big-model runs on the whole machine): checks against the stage checklist, quotes must be verbatim (checked here)
  4. writes projects/<p>/review/gate-helpers-<stage>-<n>/{gemini.json,codex.json,manifest.json}; manifest.fingerprint is the material's fingerprint (the review refuses a stale one)
  5. deletes the workspace by its exact path
Tests: WB_HELPER_FAKE_DIR=<dir with fake_gemini.json / fake_codex.json> replaces both models (no model is called)."""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import whiteboard_gate as G  # noqa: E402

SCRATCH = Path(os.environ.get("WB_HELPER_SCRATCH", "/home/MyProject/_scratch"))
AGY = "/home/MyProject/openhands-team/.runtime/antigravity-cli/agy"
GEMINI_MODEL = "gemini-3.8-flash-high"
CODEX_MODEL, CODEX_EFFORT = "gpt-6.1-sol", "xhigh"
CODEX_MACHINE_MAX = 6
# 2026-11-09: overflow to the user's second server ("codexbox", its own official subscription account, so real extra quota).
# When local Codex is at the cap, a job goes there instead of waiting. WB_REMOTE_CODEX=0 turns it off.
CODEXBOX = os.environ.get("WB_CODEXBOX", "/root/.claude/scripts/codex/codexbox.py")
REMOTE_CODEX_MAX = 3
CODEXBOX_PY = os.environ.get("WB_CODEXBOX_PY", "/usr/bin/python3")   # needs pexpect; the project venv has none
GEMINI_PARALLEL = 4
PIECE_SECONDS = 90
# file names that hold credentials; "SECRET" alone is not enough (lesson 4's memory test calls its cases r01_003_qwen_SECRET_FULL.json) - the content scan below still runs
SKIP_NAMES = re.compile(r"(^\.env|\.env$|crosscheck|oauth|credential|(^|[_.-])(client_)?secrets?\.(json|txt|ya?ml|env)$|\.youtube-token|\.key$|\.pem$|id_rsa)", re.I)
TEXT_SUFFIXES = {".json", ".md", ".txt", ".srt", ".html", ".py", ".yaml", ".yml", ".tsv", ".csv", ".js", ".cjs", ".sh"}
SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password)\"?\s*[=:]\s*\"?[A-Za-z0-9_\-]{16,}|\bsk-[A-Za-z0-9]{20,}")
ADDR_RE = re.compile(r"\b(?!127\.0\.0\.1\b)\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}\b")
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}


def now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- workspace
def _safe_remove(ws):
    """Delete a workspace we made (it carries our marker), by exact path, never a link, never outside the scratch folder."""
    ws = Path(ws)
    if ws.is_dir() and not ws.is_symlink() and ws.parent == SCRATCH and (ws / "WHY.md").exists() and "gate-review-helpers" in (ws / "WHY.md").read_text(encoding="utf-8"):
        shutil.rmtree(ws)


def _proxy(src, dst_dir, stem):
    """480p proxy of a video, cut in PIECE_SECONDS pieces; returns the piece files."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    pat = dst_dir / f"{stem}.proxy_%02d.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=-2:480", "-c:v", "libx264", "-preset", "veryfast", "-crf", "33", "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                        "-f", "segment", "-segment_time", str(PIECE_SECONDS), "-reset_timestamps", "1", str(pat)], capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg proxy failed for {src.name}: {r.stderr[-300:]}")
    return sorted(dst_dir.glob(f"{stem}.proxy_*.mp4"))


def build_workspace(P, stage, pid, n, files):
    ws = SCRATCH / f"gate-{pid}-{stage}-{n}"
    if ws.exists():
        _safe_remove(ws)
        if ws.exists():
            raise RuntimeError(f"{ws} exists and is not one of ours; refusing")
    (ws / "m").mkdir(parents=True)
    (ws / "out").mkdir()
    (ws / "WHY.md").write_text(f"# gate-review-helpers {pid} {stage} {n}\n- 谁建的：docs/whiteboard_review_helpers.py（复审主持会话），{now()[:19]} UTC\n"
                               f"- 为什么：托管评审的小弟（Gemini 听看、Codex 核对）的只读工作区，材料是拷贝，不含密钥\n- 什么时候可以删：评审结论写出后立即（脚本自己删；残留就按名字删）\n", encoding="utf-8")
    items = {"audio": [], "video": [], "image": [], "text": [], "other": []}
    refused = []
    for q in G._expand_files(files):
        if SKIP_NAMES.search(q.name):
            refused.append(f"{q.name}（名字像密钥／令牌）")
            continue
        try:
            rel = q.relative_to(P)
        except ValueError:
            rel = Path("_ext") / q.name
        dst = ws / "m" / rel
        suf = q.suffix.lower()
        if suf in TEXT_SUFFIXES and q.stat().st_size <= 4_000_000:
            txt = q.read_text(encoding="utf-8", errors="replace")
            if SECRET_RE.search(txt) or ADDR_RE.search(txt):
                refused.append(f"{rel}（像含密钥或 ip:端口）")
                continue
        if suf in VIDEO_SUFFIXES:
            for piece in _proxy(q, dst.parent, dst.stem):
                items["video"].append(piece)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(q, dst)
        key = "audio" if suf in AUDIO_SUFFIXES else "image" if suf in G.IMAGE_SUFFIXES else "text" if suf in TEXT_SUFFIXES else "other"
        items[key].append(dst)
    # the checklists the reviewer works to
    ck = ws / "m" / "_checklist"
    ck.mkdir()
    for name in sorted({"00-always.md", G.STAGE_CHECKLIST[stage]}):
        shutil.copy2(ROOT / "docs/whiteboard/checklists" / name, ck / name)
    for extra in ("docs/whiteboard/series.yaml", "docs/whiteboard/style-guide-agent.zh-CN.md"):
        if (ROOT / extra).exists():
            shutil.copy2(ROOT / extra, ck / Path(extra).name)
    return ws, items, refused


def write_index(ws, items, refused, originals=()):
    lines = ["# 文件清单（只读；不要运行任何命令去改东西；读不到写 not_found，不要凭记忆）"]
    for k, label in (("audio", "声音"), ("video", "视频（480p 代理，每段至多 90 秒）"), ("image", "图片"), ("text", "文字"), ("other", "其他")):
        for p in items[k]:
            lines.append(f"- [{label}] {p.relative_to(ws)}")
    lines.append("- [清单] m/_checklist/（本门的检查清单与系列风格文件）")
    lines.append("")
    lines.append("说明：INDEX.md 在工作区根目录，材料在 m/ 下。视频已转成 480p 代理并切成片段（`<原名>.proxy_NN.mp4`，按顺序拼起来就是原片），原件没有拷进来，但它们在主持登记的材料里。")
    if originals:
        lines += ["登记的原件（相对课程目录）："] + [f"- {o}" for o in originals]
    if refused:
        lines += ["", "有这些材料因疑似含密钥或地址没有拷进来："] + [f"- {r}" for r in refused]
    (ws / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- Gemini
AUDIO_SCHEMA = {"type": "object", "properties": {"can_hear": {"type": "boolean"}, "clips": {"type": "array", "items": {"type": "object", "properties": {
    "file": {"type": "string"}, "transcript": {"type": "string"}, "voice": {"type": "string"},
    "issues": {"type": "array", "items": {"type": "object", "properties": {"what": {"type": "string"}, "approx_second": {"type": "number"}}, "required": ["what"]}}},
    "required": ["file", "transcript"]}}, "notes": {"type": "string"}}, "required": ["can_hear", "clips"]}
VIDEO_SCHEMA = {"type": "object", "properties": {"can_see": {"type": "boolean"}, "can_hear": {"type": "boolean"}, "heard_text": {"type": "string"}, "events": {"type": "array", "items": {
    "type": "object", "properties": {"approx_second": {"type": "number"}, "what": {"type": "string"}}, "required": ["what"]}}, "problems": {"type": "array", "items": {
        "type": "object", "properties": {"approx_second": {"type": "number"}, "kind": {"type": "string"}, "what": {"type": "string"}}, "required": ["what"]}}, "notes": {"type": "string"}},
    "required": ["can_see", "can_hear", "events"]}
READ_SCHEMA = {"type": "object", "properties": {"hard_sentences": {"type": "array", "items": {"type": "object", "properties": {
    "where": {"type": "string"}, "quote": {"type": "string"}, "why": {"type": "string"}}, "required": ["where", "why"]}}, "unclear_or_contradictory": {"type": "array", "items": {"type": "string"}},
    "notes": {"type": "string"}}, "required": ["hard_sentences"]}


_CN = "零一二三四五六七八九"


def _int_cn(n):
    """Spoken Chinese for 0..9999 (enough for narration numbers)."""
    if n < 10:
        return _CN[n]
    out, units = "", [(1000, "千"), (100, "百"), (10, "十")]
    zero = False
    for v, u in units:
        d, n = divmod(n, v)
        if d:
            if zero:
                out += "零"
            out += ("" if (v == 10 and d == 1 and not out) else _CN[d]) + u
            zero = False
        elif out:
            zero = True
    if n:
        out += ("零" if zero else "") + _CN[n]
    return out


def _digits_to_cn(s):
    """Speech-to-text writes numbers in digits ("80", "1.5"); the narration spells them ("八十", "一点五")."""
    def rep(m):
        whole, _, frac = m.group(0).partition(".")
        return (_int_cn(int(whole)) if len(whole) <= 4 else "".join(_CN[int(c)] for c in whole)) + ("点" + "".join(_CN[int(c)] for c in frac) if frac else "")
    return re.sub(r"\d+(?:\.\d+)?", rep, s or "")


def _norm(s):
    return re.sub(r"[\s，。！？、；：“”‘’（）()\[\],.!?:;\"'…—\-]", "", _digits_to_cn(s))


def expected_texts(ws, P):
    """clip file name -> expected narration text, from the narration timeline when the material has it."""
    out = {}
    try:
        tl = json.loads((P / "assets/audio/narration_timeline.json").read_text(encoding="utf-8"))
        for s in tl.get("sections", []):
            for c in s.get("clips", []):
                out[Path(c.get("file", "")).name] = c.get("text", "")
    except (OSError, ValueError):
        pass
    # 样音: voice_sample_texts.json holds the teacher text ("T") and the dialogue; voice_sample_T.wav is "T", voice_sample_P_<x>.wav is the whole dialogue
    for tf in sorted((P / "assets/audio/samples").glob("voice_sample*texts.json")):
        try:
            vt = json.loads(tf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(vt.get("T"), str):
            out.setdefault("voice_sample_T.wav", vt["T"])
        dia = "".join(x.get("text", "") for x in vt.get("dialogue", []) if isinstance(x, dict))
        if dia:
            for w in (P / "assets/audio/samples").glob("voice_sample_P_*.wav"):
                if not w.name.endswith("_raw.wav"):
                    out.setdefault(w.name, dia)
    return out


def gemini_jobs(stage, ws, items, note="", expected=None):
    """[(name, prompt, schema, kind, files)]"""
    jobs = []
    common = "读 INDEX.md，再做下面的事。不要运行任何命令。你的报告只是线索，由评审再核；只写你真听到、看到的，不确定写进 notes，不要编造。"
    audio = [p for p in items["audio"] if not p.name.endswith("_raw.wav") and not p.name.startswith("_")]
    if stage in ("sample", "assets") and audio:
        group, total = [], 0.0
        groups = []
        for p in audio:
            d = G._ffprobe_duration(p) or 0
            if group and (total + d > 240 or len(group) >= 8):
                groups.append(group)
                group, total = [], 0.0
            group.append(p)
            total += d
        if group:
            groups.append(group)
        for i, g in enumerate(groups, 1):
            names = "、".join(str(p.relative_to(ws)) for p in g)
            jobs.append((f"audio{i}", f"{common}\n听这些音频：{names}。**不要看任何稿子**，每个文件逐字写下听到的内容（transcript，听不清的用[听不清]）；另外列出读错的字、拖长或被截断的词、奇怪的停顿、爆音杂音（issues，给大约第几秒）；voice 用一句话描述音色。无法听音频就 can_hear 填 false，不要编造。",
                         AUDIO_SCHEMA, "audio", g))
    focus = re.search(r"(?:重点听|盲听重点[^：:。]*|重点[^：:。]{0,8}听[^：:。]*)[:：](.+?)(?:。|$)", note or "")
    if stage in ("sample", "assets") and audio and focus:
        terms = [x for x in re.split(r"[、，,；;（）()“”\s]+", focus.group(1)) if len(x) >= 2 and not re.search(r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùü]", x)]
        hit = [p for p in audio if any(x in (expected or {}).get(p.name, "") for x in terms)]
        pick = (hit or audio)[:8]
        names = "、".join(str(p.relative_to(ws)) for p in pick)
        jobs.append(("pinyin", f"{common}\n听这些音频：{names}。主持请特别听这些词的读音：{focus.group(1)}。对每个词，找到它在哪个文件、大约第几秒，写下你实际听到的读音（带声调的拼音）和你听到的整句；听不到这个词就写 not_found。把结果放进 clips：每个词一条，file 写文件，transcript 写“词｜听到的拼音｜整句”，issues 里写读得不对或拿不准的。",
                     AUDIO_SCHEMA, "pinyin", pick))
    if stage in ("edit", "compose") and items["video"]:
        for i, v in enumerate(items["video"], 1):
            jobs.append((f"video{i}", f"{common}\n看并听 {v.relative_to(ws)}（约 {PIECE_SECONDS} 秒内的 480p 代理）。events：按时间顺序写画面上出现或变化的东西（秒数只是大概）；heard_text：逐字写听到的旁白；problems：只写你明确看到或听到的毛病（文字被压住或截断、画面和旁白对不上、卡住不动、声音断掉或爆音、同一个角色两张图叠在一起），写 kind 和大约第几秒。注意：这段是从整片按固定时长切出来的代理，第一句和最后一句可能被切在句子中间，切点处的断句不要报；老师或搭档换姿势时有大约半秒的叠化是设计，不要报；问答之间约 3 秒的静默是设计。无法看或听就把 can_see／can_hear 填 false，不要编造。",
                         VIDEO_SCHEMA, "video", [v]))
    texts = [p for p in items["text"]]
    if stage in ("plan", "proposal", "script", "scene_plan", "publish") and texts:
        names = "、".join(str(p.relative_to(ws)) for p in texts[:12])
        jobs.append(("reader", f"{common}\n你是一个大一零基础新生，读这些文字材料：{names}。把你一遍读不懂、卡住、前后矛盾、或者觉得被当成已经懂了的地方列出来（hard_sentences：where 写文件与位置，quote 逐字引原句不超过 80 字，why 写为什么）；unclear_or_contradictory 写整体上说不清的事。没有就写空数组。",
                     READ_SCHEMA, "reader", texts[:12]))
    return jobs


def run_gemini(job, ws, fake):
    name, prompt, schema, kind, files = job
    out = ws / "out" / f"gemini_{name}.json"
    if fake:
        data = json.loads((Path(fake) / "fake_gemini.json").read_text(encoding="utf-8"))
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return {"name": name, "status": "ok", "kind": kind, "files": [str(f.relative_to(ws)) for f in files], "result": data, "seconds": 0}
    sch = ws / "out" / f"schema_{name}.json"
    sch.write_text(json.dumps(schema), encoding="utf-8")
    env = dict(os.environ, LIGHTPANDA_DISABLE_TELEMETRY="true")
    t0 = time.time()
    try:
        r = subprocess.run(["timeout", "1500", AGY, "-p", prompt, "--model", GEMINI_MODEL, "--sandbox", "--json-schema", str(sch), "--output-format", "json"],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=ws, env=env, timeout=1560)
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "failed", "reason": "timeout", "kind": kind, "files": [str(f.relative_to(ws)) for f in files]}
    out.write_text(r.stdout, encoding="utf-8")
    try:
        d = json.loads(r.stdout)
        data = d.get("structured_output")
        if not isinstance(data, dict):
            txt = d.get("response") or ""
            data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except (ValueError, AttributeError):
        return {"name": name, "status": "failed", "reason": f"no JSON result (exit {r.returncode}): {(r.stderr or r.stdout)[:200]}", "kind": kind, "files": [str(f.relative_to(ws)) for f in files]}
    # What counts is what came back, not what the model says about its own senses: in the 2026-11-05 trial one run transcribed all 8 clips well and still wrote can_hear=false
    # ("I only read what the file reader returns"), so the flag is kept in the report but is not the test.
    if kind == "audio":
        got = {Path(c.get("file", "")).name for c in data.get("clips", []) if (c.get("transcript") or "").strip()}
        ok, why = all(f.name in got for f in files), "no transcript for: " + ", ".join(f.name for f in files if f.name not in got)
    elif kind == "pinyin":
        ok, why = bool(data.get("clips")), "no word reported"
    elif kind == "video":
        ok, why = bool(data.get("events")) and (bool((data.get("heard_text") or "").strip()) or data.get("can_hear") is True), "no events or no heard text for the piece"
    else:
        ok, why = True, ""
    return {"name": name, "status": "ok" if ok else "failed", "reason": "" if ok else why, "kind": kind,
            "files": [str(f.relative_to(ws)) for f in files], "result": data, "seconds": round(time.time() - t0, 1)}


def compare_transcripts(run, expected):
    """Mechanical check done HERE: blind transcript vs the narration text. The transcript is machine speech-to-text, so one wrong character (a homophone, 课/颗) is normal and
    only listed as "soft"; a clip is flagged when 3 or more characters differ or the similarity is below 0.8."""
    flags = []
    for c in (run.get("result") or {}).get("clips", []):
        exp = expected.get(Path(c.get("file", "")).name)
        if exp:
            a, b = _norm(c.get("transcript", "")), _norm(exp)
            sm = difflib.SequenceMatcher(None, a, b)
            ops = sm.get_opcodes()
            truncated = bool(ops) and ops[-1][0] == "insert" and ops[-1][1] == len(a)      # the transcript stops early (long clips): not a misreading
            diff = sum(max(i2 - i1, j2 - j1) for k, (tag, i1, i2, j1, j2) in enumerate(ops) if tag != "equal" and not (truncated and k == len(ops) - 1))
            if diff:
                flags.append({"file": c.get("file"), "similarity": round(sm.ratio(), 3), "differing_chars": diff, "severity": "major" if (diff >= 3 or (sm.ratio() < 0.8 and not truncated)) else "soft", "transcript_stops_early": truncated,
                              "transcript": c.get("transcript", "")[:160], "expected": exp[:160]})
    return flags


# ---------------------------------------------------------------- Codex
ADDENDA = {
    "plan": "核计划：难点表每条有“学生怎么想／讲法／证据”；与大纲目标一致；不用系列禁用的比喻（series.yaml 的 forbid_terms）；实验范围与成立条件写清；有没有超出已批准内容或要花钱的事。",
    "proposal": "核提案：来源是否足够且可核；与已批准计划一致；有没有把一次结果当规律；系列名、课名这类只有用户能定的事有没有被悄悄定掉。",
    "script": "核脚本：旁白无英文字母与阿拉伯数字、句长、每段字数；每个数字在数字登记里有出处；E131（一次结果当规律、实测范围没交代：哪个模型、哪一天、关没关思考、各几遍）；“每次、总是、一定、一模一样”只能用在数据确实如此处；搭档的话与旁白逐句对应。",
    "scene_plan": "核场景计划：每个场景有呈现手段；角色出场有依据；事件锚点是旁白的子串；相邻事件间隔 0.3–9.5 秒；板书里手打的数字、模型名、日期为零（应由代码从数据读）；画面诚实规则。",
    "sample": "核样音：样音文字与角色设定相符（E124：搭档要儿童／可爱的候选）；声音文件齐全；文字里没有会读错的写法（英文字母、数字、生僻多音字）。声音本身由 Gemini 听，你不判音色好坏。",
    "assets": "核素材：配音片段覆盖旁白每一句且只一次；搭档片段与 partner_lines 一一对应；字幕与旁白文字一致；姿势图和插画逐张看（E91：顺着胳膊找到肩、数手指，有没有多指缺指、肢体错位、背景脏）。",
    "edit": "核样片：看附的帧和联系表，对照场景计划里的事件和旁白锚点；E121：最挤的帧上有没有文字压框线、被截断、互相叠；E117：搭档同一时刻只能有一张图；E122：深色面板上的字够不够清楚；检查脚本的输出里有 ERROR 或 TOO LATE 就是 blocking。",
    "compose": "核成片：compose-notes.json 里每一条画面描述，对着附的帧（review_dense 拼图、问答时刻拼图）核对得上不（E112）；有没有黑帧、卡死、问答静默对不上；时长与配音时间线是否吻合；已批准的内容有没有被悄悄改动。",
    "publish": "核发布包：简介和电子书里的每个实测数字，对着归档的原始记录（records、claims）核（E96）；“每次、总是、一定、全靠”之类的词，对着本课数据核（E101）；“人工、真人”字样到底是谁做的（E108：AI 模型）；章节时间与成片是否一致（E105、E113）；电子书页面文字里有没有任务书措辞或工作记录混进来（E102、E130）。",
}


def codex_jobs(stage, ws, items, pid):
    imgs = items["image"]
    batches = [imgs[i:i + 8] for i in range(0, len(imgs), 8)] or [[]]
    if len(batches) > 3:                       # at most 3 runs of 8 pictures: spread the pick over the whole list
        step = len(imgs) / 24
        pick = [imgs[int(i * step)] for i in range(24)]
        batches = [pick[i:i + 8] for i in range(0, 24, 8)]
    jobs = []
    for i, b in enumerate(batches, 1):
        names = "\n".join(f"  - {p.relative_to(ws)}" for p in b)
        task = (f"# 任务：你是白板课《{pid}》“{G.DELEGABLE_WORD[stage]}”这一门的小弟（核对员），不是评审：报告只是线索，评审（另一个模型）会自己再核。\n\n"
                f"规则：只读 INDEX.md（在工作区根目录）列的材料（在 m/ 里）；视频只有代理片段，原件不在，别因为找不到原件就判缺；不联网；不运行被审对象的代码（可以用 grep、ffprobe、python 做只读统计）；不读工作区外的东西；引文每条不超过 120 字，必须逐字来自材料；读不到写“未核实”。\n"
                f"先读 m/_checklist/ 里的清单（逐条对照“要人判断”各条）。\n\n本门要点：{ADDENDA[stage]}\n\n"
                + (f"这次随任务附了 {len(b)} 张图（用 -i 附上，你直接就能看到），它们是：\n{names}\n逐张看：文字被压住、截断、重叠，肢体、手指，对比度；每张给一句结论。\n\n" if b else "")
                + ("（这是第 %d／%d 批图；文字材料只在第 1 批里核，其他批只看图。）\n\n" % (i, len(batches)) if len(batches) > 1 else "")
                + "最终消息只给 JSON：{\"findings\":[{\"severity\":\"blocking|minor\",\"where\":\"文件与位置\",\"issue\":\"…\",\"quote\":\"逐字引文\"}],\"checked\":[\"你实际核对过的项，每项一句\"],\"not_checked\":[\"没法核的项和原因\"]}。")
        jobs.append((f"codex{i}", task, b))
    return jobs


def _codex_running():
    r = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True)
    return sum(1 for line in r.stdout.splitlines() if re.search(r"codex.* exec ", line) and "grep" not in line)


def _remote_enabled():
    return os.environ.get("WB_REMOTE_CODEX", "1") != "0" and Path(CODEXBOX).exists()


def _remote_free():
    try:
        r = subprocess.run([CODEXBOX_PY, CODEXBOX, "count"], capture_output=True, text=True, timeout=90)
        return r.returncode == 0 and int((r.stdout.strip().splitlines() or ["99"])[-1]) < REMOTE_CODEX_MAX
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return False


def run_codex_remote(job, ws):
    """Run one Codex job on codexbox. Returns a run dict, or None when the remote refused the workspace (caller falls back to local)."""
    name, _task, imgs = job
    out_rel, ev_rel = f"out/{name}_final.txt", f"out/{name}.events.jsonl"
    cmd = [CODEXBOX_PY, CODEXBOX, "run", str(ws), "--model", CODEX_MODEL, "--effort", CODEX_EFFORT, "--mode", "ro",
           "--out", out_rel, "--events", ev_rel, "--timeout", "3000", "--prompt", f"读 TASK_{name}.md 并严格按它做。"]
    for p in imgs:
        cmd += ["-i", str(p)]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=3400)
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "failed", "reason": "timeout (remote)", "where": "codexbox"}
    if r.returncode == 2 and "REFUSED" in r.stdout:
        return None
    try:
        txt = (ws / out_rel).read_text(encoding="utf-8")
        data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except (OSError, ValueError):
        return {"name": name, "status": "failed", "where": "codexbox", "reason": f"no JSON result (remote exit {r.returncode}): {(r.stdout + r.stderr)[-300:]}"}
    return {"name": name, "status": "ok", "result": data, "seconds": round(time.time() - t0, 1), "where": "codexbox"}


def run_codex(job, ws, fake):
    name, task, imgs = job
    out = ws / "out" / f"{name}_final.txt"
    (ws / f"TASK_{name}.md").write_text(task, encoding="utf-8")
    if fake:
        data = json.loads((Path(fake) / "fake_codex.json").read_text(encoding="utf-8"))
        return {"name": name, "status": "ok", "result": data, "seconds": 0}
    waited = 0
    while _codex_running() >= CODEX_MACHINE_MAX and waited < 1200:
        if _remote_enabled() and _remote_free():
            r = run_codex_remote(job, ws)
            if r is not None:
                return r
        time.sleep(30)
        waited += 30
    cmd = ["timeout", "3000", "codex", "exec", "-m", CODEX_MODEL, "-c", f"model_reasoning_effort={CODEX_EFFORT}", "-s", "read-only", "-C", str(ws), "--skip-git-repo-check", "--ephemeral", "--json"]
    for p in imgs:
        cmd += ["-i", str(p)]
    cmd += ["-o", str(out), f"读 TASK_{name}.md 并严格按它做。"]
    t0 = time.time()
    with (ws / "out" / f"{name}.events.jsonl").open("w", encoding="utf-8") as ev:
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=ev, stderr=subprocess.STDOUT, cwd=ws, timeout=3100)
        except subprocess.TimeoutExpired:
            return {"name": name, "status": "failed", "reason": "timeout"}
    try:
        txt = out.read_text(encoding="utf-8")
        data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except (OSError, ValueError):
        tail = (ws / "out" / f"{name}.events.jsonl").read_text(encoding="utf-8", errors="replace")[-300:]
        return {"name": name, "status": "failed", "reason": f"no JSON result (exit {r.returncode}); events tail: {tail}"}
    return {"name": name, "status": "ok", "result": data, "seconds": round(time.time() - t0, 1), "where": "local"}


def check_quotes(ws, runs):
    """Mechanical check done HERE: does each finding's quote occur verbatim in some text file of the workspace?"""
    blobs = []
    for q in (ws / "m").rglob("*"):
        if q.is_file() and q.suffix.lower() in TEXT_SUFFIXES and q.stat().st_size < 4_000_000:
            blobs.append(re.sub(r"\s+", "", q.read_text(encoding="utf-8", errors="replace")))
    for run in runs:
        for f in (run.get("result") or {}).get("findings", []):
            qt = re.sub(r"\s+", "", f.get("quote", "") or "")
            f["quote_found_verbatim"] = bool(qt) and any(qt in b for b in blobs)


# ---------------------------------------------------------------- main
def cmd_run(args):
    pdir = Path(args.projects)
    pid, stage = args.project, args.stage
    P = pdir / pid
    req = G._load_request(pdir, pid, stage)
    d = G._dload(pdir, pid)
    if not req or not d or d.get("status") != "active":
        print(f"拒绝：没有登记过的 request，或托管不是进行中。先 `whiteboard_gate.py request {pid} {stage}`。")
        return 1
    n = req["expected_n"]
    files = req["files"]
    if G._fingerprint(pdir, pid, stage, files) != req["fingerprint"]:
        print("拒绝：材料在 request 之后被改过；请主持会话重新 request。")
        return 1
    hdir = P / "review" / f"gate-helpers-{stage}-{n}"
    hdir.mkdir(parents=True, exist_ok=True)
    fake = os.environ.get("WB_HELPER_FAKE_DIR")
    manifest = {"project": pid, "stage": stage, "n": n, "time": now(), "fingerprint": req["fingerprint"], "gemini": {"status": "skipped"}, "codex": {"status": "skipped"}}
    ws = None
    try:
        ws, items, refused = build_workspace(P, stage, pid, n, files)
        write_index(ws, items, refused, [str(Path(q).relative_to(P)) if str(q).startswith(str(P)) else Path(q).name for q in G._expand_files(files)][:200])
        manifest.update({"workspace": str(ws), "refused_files": refused})
        gem_runs, cdx_runs = [], []
        gj = [] if args.only == "codex" else gemini_jobs(stage, ws, items, req.get("note", ""), expected_texts(ws, P))
        cj = [] if args.only == "gemini" else codex_jobs(stage, ws, items, pid)
        with ThreadPoolExecutor(max_workers=GEMINI_PARALLEL) as gx, ThreadPoolExecutor(max_workers=3) as cx:
            gf = [gx.submit(run_gemini, j, ws, fake) for j in gj]
            cf = [cx.submit(run_codex, j, ws, fake) for j in cj]
            gem_runs = [f.result() for f in gf]
            # one retry for a failed Gemini run (2026-11-05 trial: one run was refused read_file in headless mode, the same files read fine elsewhere)
            redo = [i for i, r in enumerate(gem_runs) if r["status"] != "ok"]
            for i, f in zip(redo, [gx.submit(run_gemini, gj[i], ws, fake) for i in redo]):
                again = f.result()
                again["retry_of_failure"] = gem_runs[i].get("reason", "")
                gem_runs[i] = again
            cdx_runs = [f.result() for f in cf]
        exp = expected_texts(ws, P)
        for r in gem_runs:
            if r.get("kind") == "audio" and r.get("status") == "ok":
                r["transcript_mismatches"] = compare_transcripts(r, exp)
                for c in (r.get("result") or {}).get("clips", []):
                    c["expected_text"] = exp.get(Path(c.get("file", "")).name)       # next to the model's "issues", so the reviewer can tell a speech-to-text slip from a real misreading
        check_quotes(ws, cdx_runs)
        need_gem = stage in G.MEDIA_GATES
        if gj:
            manifest["gemini"] = {"status": "ok" if gem_runs and all(r["status"] == "ok" for r in gem_runs) else "failed", "runs": len(gem_runs),
                                  "failed": [r["name"] for r in gem_runs if r["status"] != "ok"], "model": GEMINI_MODEL}
        elif need_gem:
            manifest["gemini"] = {"status": "failed", "reason": "no audio/video in the material to listen to or watch"} if args.only != "codex" else {"status": "skipped"}
        if cj:
            manifest["codex"] = {"status": "ok" if cdx_runs and all(r["status"] == "ok" for r in cdx_runs) else "failed", "runs": len(cdx_runs),
                                 "failed": [r["name"] for r in cdx_runs if r["status"] != "ok"], "model": f"{CODEX_MODEL}+{CODEX_EFFORT}"}
        (hdir / "gemini.json").write_text(json.dumps({"runs": gem_runs}, ensure_ascii=False, indent=1), encoding="utf-8")
        (hdir / "codex.json").write_text(json.dumps({"runs": cdx_runs}, ensure_ascii=False, indent=1), encoding="utf-8")
        flags = [f for r in gem_runs for f in r.get("transcript_mismatches", [])]
        manifest["transcript_mismatches"] = sum(1 for f in flags if f["severity"] == "major")
        manifest["transcript_soft_differences"] = sum(1 for f in flags if f["severity"] == "soft")
        manifest["finished"] = now()
    except Exception as e:                                  # noqa: BLE001 - a helper crash must leave a manifest that says "failed", never a half-written ok
        manifest["gemini"], manifest["codex"] = {"status": "failed", "reason": f"helper script error: {e!r}"[:300]}, {"status": "failed", "reason": f"helper script error: {e!r}"[:300]}
        print(f"小弟脚本出错：{e!r}")
    finally:
        (hdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        if ws is not None and not args.keep:
            _safe_remove(ws)
    print(f"小弟报告：gemini={manifest['gemini']['status']} codex={manifest['codex']['status']}，转写与旁白对不上的片段 {manifest.get('transcript_mismatches', 0)} 个（差一两个字的 {manifest.get('transcript_soft_differences', 0)} 个不算）→ {hdir}")
    return 0


def cmd_full(args):
    rc = cmd_run(args)
    if rc != 0:
        return rc
    P = Path(args.projects) / args.project
    req = G._load_request(Path(args.projects), args.project, args.stage)
    hdir = P / "review" / f"gate-helpers-{args.stage}-{req['expected_n']}"
    cmd = [sys.executable, str(ROOT / "docs/whiteboard_gate.py"), "--projects", str(args.projects), "review", args.project, args.stage, "--helpers", str(hdir)]
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", default=str(ROOT / "projects"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "full"):
        s = sub.add_parser(name)
        s.add_argument("project")
        s.add_argument("stage", choices=G.DELEGABLE)
        s.add_argument("--only", choices=["gemini", "codex"], default=None)
        s.add_argument("--keep", action="store_true", help="keep the workspace (debugging)")
    args = ap.parse_args()
    return {"run": cmd_run, "full": cmd_full}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
