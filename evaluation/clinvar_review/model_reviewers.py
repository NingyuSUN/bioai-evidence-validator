"""Run LLM reviewers over the blinded ClinVar review packet, for comparison with expert labels.

    python3 evaluation/clinvar_review/model_reviewers.py run \
        --packet artifacts/clinvar-review/reviewer_packet --output artifacts/clinvar-review/models \
        --backends claude codex gemini --limit 3

    uv run --frozen python evaluation/clinvar_review/model_reviewers.py export \
        --output artifacts/clinvar-review/models --key artifacts/clinvar-review/maintainer/key.json

`run` gives each model exactly what a human reviewer gets: RUBRIC.md and one case's submissions
under its opaque code. It never reads the maintainer key. Each call is a fresh, non-interactive
CLI session in an empty temporary directory, one case per call, answering through a JSON schema.
Tools are disabled where the CLI allows it (Claude Code: all tools; Codex: browser tools, user
config and MCP servers, read-only sandbox). Antigravity cannot disable web search, so every tool
call is detected from its event stream and recorded; a case answered with tool use is retried once
and otherwise marked `later_information_seen = yes`. `run` needs only the standard library, so it
works wherever the CLIs are installed (for example WSL), and it resumes where it stopped.

`export` (run by the maintainer, with the key) writes model labels in the protocol annotation
format and as predictions for `bioevidence review score`. Model labels are not independent human
annotations; keep them in their own files.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

USES = ["research_summary", "clinical_reference", "expert_reference"]
CHOICES = {"statement_label": ["correct", "incorrect", "uncertain"],
           **{use: ["admitted", "review_required", "rejected"] for use in USES},
           "later_information_seen": ["no", "yes"]}
ANSWER_FIELDS = ["statement_label", "statement_rationale",
                 *[f for use in USES for f in (use, f"{use}_rationale")], "later_information_seen"]
SCHEMA = {"type": "object", "additionalProperties": False, "required": ANSWER_FIELDS,
          "properties": {f: {"type": "string", "enum": CHOICES[f]} if f in CHOICES else {"type": "string"}
                         for f in ANSWER_FIELDS}}
PROMPT = """You are one of several independent reviewers in a blinded evaluation of human germline \
variant classifications. Apply the rubric below exactly, using your own professional judgment.

Rules for this task:
- Judge only the submissions shown for this case, as ClinVar held them in September 2023.
- Do not use tools, files, the web or any other lookup; rely on the evidence shown and general \
background knowledge only.
- If you recognise this variant and know what happened to it after September 2023, answer \
later_information_seen = "yes" and still label it as you would have in September 2023.
- Give a short rationale for every label.
- Reply with one JSON object matching the required schema and nothing else.

<rubric>
{rubric}
</rubric>

<case code="{code}">
Gene: {gene}
Submissions held by ClinVar in September 2023 ({count}):
{summary}
</case>
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_executable(name: str) -> str:
    """Locate a CLI, including Node tools installed under nvm, which login shells do not load."""
    found = shutil.which(name)
    if found:
        return found
    candidates = sorted(glob.glob(os.path.expanduser(f"~/.nvm/versions/node/*/bin/{name}")))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(f"{name} not found on PATH or under ~/.nvm")


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)


# Backends: how to call each CLI and how to read its answer, tool use and token usage.

def claude_command(model: str, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    return ([find_executable("claude"), "-p", "--model", model, "--tools", "", "--strict-mcp-config",
             "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(SCHEMA)], prompt)


def claude_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    data = json.loads(stdout)
    if data.get("is_error") or "structured_output" not in data:
        raise ValueError(f"Claude returned no structured output: {data.get('subtype')}")
    server = data.get("usage", {}).get("server_tool_use", {})
    tools = [name for name, count in server.items() if count] + [d.get("tool_name", "?") for d in data.get("permission_denials", [])]
    usage = data.get("usage", {})
    return data["structured_output"], tools, {"input_tokens": usage.get("input_tokens", 0)
                                              + usage.get("cache_read_input_tokens", 0)
                                              + usage.get("cache_creation_input_tokens", 0),
                                              "output_tokens": usage.get("output_tokens"),
                                              "cost_usd": data.get("total_cost_usd")}


CODEX_DISABLED = ["browser_use", "browser_use_external", "browser_use_full_cdp_access", "in_app_browser"]


def codex_command(model: str, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    disable = [arg for feature in CODEX_DISABLED for arg in ("--disable", feature)]
    return ([find_executable("codex"), "exec", "-m", model, "--ignore-user-config", *disable, "--sandbox", "read-only",
             "--skip-git-repo-check", "--ephemeral", "--json", "--output-schema", str(schema_path),
             "-o", "last.json", "-"], prompt)


def codex_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    answer = json.loads((workdir / "last.json").read_text(encoding="utf-8"))
    tools: list[str] = []
    usage: dict[str, Any] = {"warnings": 0}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if event.get("type") == "item.completed" and isinstance(item, dict):
            kind = item.get("type")
            if kind == "error":
                usage["warnings"] += 1  # e.g. an MCP server failing to connect; not a tool call
            elif kind not in ("agent_message", "reasoning"):
                tools.append(str(kind))  # anything else (commands, MCP or web calls) counts as tool use
        if event.get("type") == "turn.completed":
            usage.update(input_tokens=event.get("usage", {}).get("input_tokens"),
                         output_tokens=event.get("usage", {}).get("output_tokens"))
    return answer, tools, usage


def gemini_command(model: str, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    return ([find_executable("agy"), "--model", model, "--output-format", "stream-json", "--json-schema",
             str(schema_path), "--sandbox", "--print-timeout", f"{timeout}s", "--print", prompt], None)


def gemini_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # The answer sits in the final result event, e.g. {"event": "result", "result": {"structured_output": ...}}.
    final = next((d for e in reversed(events) for d in walk(e) if "structured_output" in d), None)
    if final is None:
        raise ValueError("Antigravity returned no structured output")
    tools = [d["tool_name"] for e in events for d in walk(e) if isinstance(d.get("tool_name"), str)
             and d["tool_name"] != "finish"]
    steps = sorted({d["step_type"] for e in events for d in walk(e) if isinstance(d.get("step_type"), str)})
    usage = final.get("usage", {})
    return final["structured_output"], tools, {"input_tokens": usage.get("input_tokens"),
                                               "output_tokens": usage.get("output_tokens"), "step_types": steps}


BACKENDS: dict[str, dict[str, Any]] = {
    "claude": {"model": "claude-opus-5-5", "cli": "claude", "command": claude_command, "parse": claude_parse},
    "codex": {"model": "gpt-6-astra", "cli": "codex", "command": codex_command, "parse": codex_parse},
    "gemini": {"model": "gemini-3.1-pro-high", "cli": "agy", "command": gemini_command, "parse": gemini_parse},
}


def validate_answer(answer: Any) -> dict[str, str]:
    if not isinstance(answer, dict):
        raise ValueError("answer is not a JSON object")
    missing = [f for f in ANSWER_FIELDS if not isinstance(answer.get(f), str)]
    bad = [f for f, allowed in CHOICES.items() if answer.get(f) not in allowed]
    if missing or bad:
        raise ValueError(f"missing {missing}, invalid {bad}")
    return {f: answer[f].strip() for f in ANSWER_FIELDS}


def execute(argv: list[str], stdin: str | None, workdir: Path, timeout: int) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(argv[0]).parent), env.get("PATH", "")])  # node beside nvm CLIs
    return subprocess.run(argv, input=stdin, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def review_case(backend: str, model: str, case: dict[str, str], rubric: str, timeout: int,
                runner: Callable = execute) -> dict[str, Any]:
    """One fresh CLI session for one case, in an empty directory; retried once on tool use or a bad answer."""
    spec = BACKENDS[backend]
    prompt = PROMPT.format(rubric=rubric.strip(), code=case["case_code"], gene=case["gene"],
                           count=case["submissions"], summary=case["summary"])
    attempts: list[dict[str, Any]] = []
    for attempt in (1, 2):
        started = time.monotonic()
        record: dict[str, Any] = {"attempt": attempt, "tools_used": [], "error": None}
        with tempfile.TemporaryDirectory(prefix="bioai-review-") as directory:
            workdir = Path(directory)
            schema_path = workdir / "schema.json"
            schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
            argv, stdin = spec["command"](model, schema_path, prompt, timeout)
            try:
                done = runner(argv, stdin, workdir, timeout)
                record["returncode"] = done.returncode
                record["stderr_tail"] = done.stderr[-800:]
                answer, tools, usage = spec["parse"](done.stdout, workdir)
                record.update(labels=validate_answer(answer), tools_used=tools, usage=usage)
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
        record["seconds"] = round(time.monotonic() - started, 1)
        attempts.append(record)
        if record["error"] is None and not record["tools_used"]:
            break
    final = attempts[-1]
    labels = final.get("labels")
    if labels and final["tools_used"]:
        labels["later_information_seen"] = "yes"  # a tool call may have reached later information
    return {"code": case["case_code"], "backend": backend, "model": model, "prompt_sha256": sha256_text(prompt),
            "ok": labels is not None, "labels": labels, "tools_used": final["tools_used"], "attempts": attempts,
            "finished_at": dt.datetime.now(dt.UTC).isoformat()}


def read_packet(packet: Path) -> tuple[list[dict[str, str]], str]:
    with (packet / "labels.csv").open(encoding="utf-8", newline="") as handle:
        cases = list(csv.DictReader(handle))
    return cases, (packet / "RUBRIC.md").read_text(encoding="utf-8")


def cli_version(name: str) -> str:
    try:
        done = subprocess.run([find_executable(name), "--version"], capture_output=True, text=True, timeout=60)
        return (done.stdout or done.stderr).strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "unknown"


def write_labels(folder: Path, cases: list[dict[str, str]], results: dict[str, dict]) -> None:
    """The reviewer labels.csv, filled in: importable with import_sheets.py like a returned workbook."""
    columns = list(cases[0])
    rows = []
    for case in cases:
        row = dict(case)
        result = results.get(case["case_code"])
        if result and result["ok"]:
            row.update(result["labels"])
            row["sources_consulted"] = ("model knowledge only; no tools" if not result["tools_used"]
                                        else "tool use detected: " + ", ".join(sorted(set(result["tools_used"]))))
            row["minutes_spent"] = str(round(sum(a["seconds"] for a in result["attempts"]) / 60, 2))
        rows.append(row)
    with (folder / "labels.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> int:
    cases, rubric = read_packet(args.packet)
    if args.set != "all":
        cases = [c for c in cases if c["set"] == args.set]
    if args.codes:
        wanted = set(args.codes.split(","))
        cases = [c for c in cases if c["case_code"] in wanted]
    if args.limit:
        cases = cases[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"backends": {}}
    manifest.update({"packet_labels_sha256": sha256_text((args.packet / "labels.csv").read_text(encoding="utf-8")),
                     "rubric_sha256": sha256_text(rubric), "prompt_template_sha256": sha256_text(PROMPT),
                     "schema_sha256": sha256_text(json.dumps(SCHEMA, sort_keys=True)),
                     "note": "Model labels are not independent human annotations."})
    jobs = []
    for backend in args.backends:
        model = getattr(args, f"{backend}_model") or BACKENDS[backend]["model"]
        folder = args.output / backend
        (folder / "raw").mkdir(parents=True, exist_ok=True)
        manifest["backends"][backend] = {"model": model, "cli": BACKENDS[backend]["cli"],
                                         "cli_version": cli_version(BACKENDS[backend]["cli"])}
        for case in cases:
            raw = folder / "raw" / f"{case['case_code']}.json"
            if raw.exists() and json.loads(raw.read_text(encoding="utf-8")).get("ok"):
                continue  # resume: this case already has a valid answer
            jobs.append((backend, model, case, raw))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(jobs)} call(s) to make across {len(args.backends)} backend(s); "
          f"{len(cases) * len(args.backends) - len(jobs)} already done", flush=True)

    def work(job):
        backend, model, case, raw = job
        result = review_case(backend, model, case, rubric, args.timeout)
        raw.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers * len(args.backends)) as pool:
        for n, result in enumerate(pool.map(work, jobs), start=1):
            failures += not result["ok"]
            status = "ok" if result["ok"] else "FAILED " + str(result["attempts"][-1]["error"])[:120]
            tools = f" tools={result['tools_used']}" if result["tools_used"] else ""
            print(f"[{n}/{len(jobs)}] {result['backend']} {result['code']}: {status}{tools}", flush=True)

    all_cases, _ = read_packet(args.packet)
    for backend in args.backends:
        folder = args.output / backend
        results = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (folder / "raw").glob("*.json")}
        write_labels(folder, all_cases, results)
    summarize(args.output, args.backends)
    return 1 if failures else 0


def summarize(output: Path, backends: list[str]) -> None:
    rows = []
    for backend in backends:
        for path in sorted((output / backend / "raw").glob("*.json")):
            r = json.loads(path.read_text(encoding="utf-8"))
            last = r["attempts"][-1]
            rows.append({"backend": backend, "model": r["model"], "code": r["code"], "ok": r["ok"],
                         "attempts": len(r["attempts"]), "seconds": sum(a["seconds"] for a in r["attempts"]),
                         "tools_used": ";".join(r["tools_used"]),
                         "input_tokens": (last.get("usage") or {}).get("input_tokens"),
                         "output_tokens": (last.get("usage") or {}).get("output_tokens"), "error": last["error"] or ""})
    with (output / "runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["backend"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for backend in backends:
        mine = [r for r in rows if r["backend"] == backend]
        if mine:
            done = [r for r in mine if r["ok"]]
            print(f"{backend}: {len(done)}/{len(mine)} answered, {sum(bool(r['tools_used']) for r in mine)} with tool use, "
                  f"median {sorted(r['seconds'] for r in mine)[len(mine) // 2]:.0f} s per case")


def export(args: argparse.Namespace) -> int:
    """Maintainer step: model labels -> protocol annotations and predictions (needs the key)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import import_sheets  # noqa: PLC0415 - needs the bioevidence_validator package, unlike `run`

    key = json.loads(args.key.read_text(encoding="utf-8"))
    manifest = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
    annotations, predictions = [], []
    for backend, info in manifest["backends"].items():
        labels = import_sheets.read_labels(args.output / backend / "labels.csv")
        reviewer = f"model:{info['model']}"
        rows, _ = import_sheets.convert(labels, key, reviewer_id=reviewer,
                                        qualification=f"LLM {info['model']} via {info['cli_version']}; "
                                                      "not an independent human annotation",
                                        annotated_at=args.annotated_at)
        annotations += rows
        for row in rows:
            code = row["annotation_id"].split(":")[-2]
            predictions.append({"case_id": row["case_id"], "requested_use": row["requested_use"],
                                "record_sha256": row["record_sha256"], "profile_sha256": row["profile_sha256"],
                                "method": reviewer, "predicted_status": row["admission_label"],
                                "subset": key["cases"][code]["role"]})
    target = args.output / "model_annotations.csv"
    if target.exists():
        target.unlink()  # regenerated from raw answers each time
    import_sheets.append(target, annotations)
    with (args.output / "model_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(predictions)
    print(f"Wrote {len(annotations)} annotation rows and {len(predictions)} predictions for "
          f"{len(manifest['backends'])} model(s) to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    go = steps.add_parser("run", help="Ask the models; reads only the reviewer packet")
    go.add_argument("--packet", type=Path, required=True)
    go.add_argument("--output", type=Path, required=True)
    go.add_argument("--backends", nargs="+", choices=list(BACKENDS), default=list(BACKENDS))
    for name, spec in BACKENDS.items():
        go.add_argument(f"--{name}-model", help=f"default {spec['model']}")
    go.add_argument("--set", choices=["calibration", "test", "all"], default="all")
    go.add_argument("--codes", help="Comma-separated case codes")
    go.add_argument("--limit", type=int)
    go.add_argument("--workers", type=int, default=2, help="Concurrent calls per backend")
    go.add_argument("--timeout", type=int, default=600, help="Seconds per call")
    out = steps.add_parser("export", help="Maintainer: write annotations and predictions using the key")
    out.add_argument("--output", type=Path, required=True)
    out.add_argument("--key", type=Path, required=True)
    out.add_argument("--annotated-at", default=dt.date.today().isoformat())
    args = parser.parse_args(argv)
    return run(args) if args.step == "run" else export(args)


if __name__ == "__main__":
    sys.exit(main())
