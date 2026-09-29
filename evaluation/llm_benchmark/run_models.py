"""Ask LLMs the benchmark tasks, with and without the ClinVar source, through their CLIs.

    python3 evaluation/llm_benchmark/run_models.py --split pilot --output artifacts/llm-benchmark \
        --backends claude codex gemini

Three conditions per task and model:
  no_source          the variant ID and gene only: the model answers from its own knowledge
  with_source        plus the variant's ClinVar 2023-09 submissions, as a table
  with_source_batch  25 variants with their submissions in one prompt, one result per variant: the
                     scale at which curation is actually done

Each call is a fresh, non-interactive CLI session in an empty temporary directory, answering
through a JSON schema, with tools disabled where the CLI allows it (Claude Code: all tools; Codex:
browser tools, user config and MCP servers, read-only sandbox). Antigravity cannot disable web
search, so tool calls are detected from its event stream; an answer given with tool use is retried
once and otherwise kept and flagged. The script reads only `tasks/<split>.jsonl`, never the
reference answers, needs only the standard library, and resumes where it stopped.
"""
from __future__ import annotations

import argparse
import concurrent.futures
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

ROOT = Path(__file__).resolve().parent
CONDITIONS = ["no_source", "with_source", "with_source_batch"]
BATCH_SIZE = 25
FIELDS = ["scv", "submitter", "classification", "review_status", "collection_method", "date_last_evaluated"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["decision", "conflict", "submissions", "rationale"],
    "properties": {
        "decision": {"type": "string", "enum": ["admit", "stop"]},
        "conflict": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "submissions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": FIELDS,
                                                   "properties": {f: {"type": "string"} for f in FIELDS}}},
        "rationale": {"type": "string"},
    },
}
PROMPT = """You are assisting a clinical variant curation team. Decide whether ClinVar's germline \
pathogenic or likely pathogenic (P/LP) classification of the variant below may be admitted to a \
clinical reference set, and list the ClinVar submissions (SCV records) behind your answer, as \
ClinVar held them in September 2023.

Admission policy for the clinical reference:
- Admit only if at least two different submitters gave criteria-based P/LP classifications, or an \
expert panel or practice guideline classified the variant P/LP; and no submission classifies it as \
uncertain significance, likely benign or benign.
- Otherwise, or if you cannot verify the submissions, answer "stop".

Rules:
- Do not use tools, files or the web.
- Report every submission exactly as ClinVar held it: SCV accession with version, submitter, \
classification, review status, collection method and date last evaluated.
- Never invent or guess a submission. If you do not know them, return an empty list and answer "stop".
- Set conflict to "yes" if any submission classifies the variant as uncertain significance, likely \
benign or benign; "no" if none does; "unknown" if you cannot tell.
- Reply with one JSON object matching the required schema and nothing else.

<variant>
ClinVar VariationID: {variation_id}
Gene: {gene}
</variant>
{source}"""
NO_SOURCE = "No source data is provided for this task."
# The same policy and rules as PROMPT, for many variants at once.
BATCH_ITEM = {**SCHEMA, "required": ["variation_id", *SCHEMA["required"]],
              "properties": {"variation_id": {"type": "string"}, **SCHEMA["properties"]}}
BATCH_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["results"],
                "properties": {"results": {"type": "array", "items": BATCH_ITEM}}}
BATCH_PROMPT = """You are assisting a clinical variant curation team. For each of the {count} variants \
below, decide whether ClinVar's germline pathogenic or likely pathogenic (P/LP) classification may be \
admitted to a clinical reference set, and list the ClinVar submissions (SCV records) behind your \
answer, as ClinVar held them in September 2023.

Admission policy for the clinical reference:
- Admit only if at least two different submitters gave criteria-based P/LP classifications, or an \
expert panel or practice guideline classified the variant P/LP; and no submission classifies it as \
uncertain significance, likely benign or benign.
- Otherwise, or if you cannot verify the submissions, answer "stop".

Rules:
- Do not use tools, files or the web.
- Report every submission exactly as ClinVar held it: SCV accession with version, submitter, \
classification, review status, collection method and date last evaluated.
- Never invent or guess a submission. If you do not know them, return an empty list and answer "stop".
- Set conflict to "yes" if any submission classifies the variant as uncertain significance, likely \
benign or benign; "no" if none does; "unknown" if you cannot tell.
- Return exactly one result per variant, with its ClinVar VariationID, in the order given.
- Reply with one JSON object matching the required schema and nothing else.

{variants}"""


def source_block(task: dict) -> str:
    if not task["source"]:
        return ("<clinvar_submissions release=\"2023-09\">\nClinVar holds no submissions for this VariationID."
                "\n</clinvar_submissions>")
    header = "| SCV | Submitter | Classification | Review status | Collection method | Date last evaluated |"
    rows = [header, "|---|---|---|---|---|---|"]
    rows += ["| " + " | ".join(row[f] for f in FIELDS) + " |" for row in task["source"]]
    return "<clinvar_submissions release=\"2023-09\">\n" + "\n".join(rows) + "\n</clinvar_submissions>"


def prompt_for(task: dict, condition: str) -> str:
    source = source_block(task) if condition == "with_source" else NO_SOURCE
    return PROMPT.format(variation_id=task["variation_id"], gene=task["gene"], source=source)


def batch_prompt(tasks: list[dict]) -> str:
    blocks = [f"<variant index=\"{n}\">\nClinVar VariationID: {task['variation_id']}\nGene: {task['gene']}\n"
              f"{source_block(task)}\n</variant>" for n, task in enumerate(tasks, start=1)]
    return BATCH_PROMPT.format(count=len(tasks), variants="\n\n".join(blocks))


def batches(tasks: list[dict]) -> list[dict]:
    """Consecutive tasks in task-ID order (a keyed hash, so categories are mixed)."""
    return [{"batch_id": f"batch-{n // BATCH_SIZE + 1:02d}", "tasks": tasks[n:n + BATCH_SIZE]}
            for n in range(0, len(tasks), BATCH_SIZE)]


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


# Backends, as in evaluation/clinvar_review/model_reviewers.py: how to call each CLI and read its answer.

def claude_command(model: str, schema: dict, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    return ([find_executable("claude"), "-p", "--model", model, "--tools", "", "--strict-mcp-config",
             "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(schema)], prompt)


def claude_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    data = json.loads(stdout)
    if data.get("is_error") or "structured_output" not in data:
        raise ValueError(f"Claude returned no structured output: {data.get('subtype')}: {str(data.get('result'))[:200]}")
    server = data.get("usage", {}).get("server_tool_use", {})
    tools = [name for name, count in server.items() if count] + [d.get("tool_name", "?") for d in data.get("permission_denials", [])]
    usage = data.get("usage", {})
    return data["structured_output"], tools, {"input_tokens": usage.get("input_tokens", 0)
                                              + usage.get("cache_read_input_tokens", 0)
                                              + usage.get("cache_creation_input_tokens", 0),
                                              "output_tokens": usage.get("output_tokens")}


CODEX_DISABLED = ["browser_use", "browser_use_external", "browser_use_full_cdp_access", "in_app_browser"]


def codex_command(model: str, schema: dict, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    disable = [arg for feature in CODEX_DISABLED for arg in ("--disable", feature)]
    return ([find_executable("codex"), "exec", "-m", model, "--ignore-user-config", *disable, "--sandbox", "read-only",
             "--skip-git-repo-check", "--ephemeral", "--json", "--output-schema", str(schema_path),
             "-o", "last.json", "-"], prompt)


def codex_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    if not (workdir / "last.json").exists():
        failed = [e for line in stdout.splitlines() if line.startswith("{")
                  for e in [json.loads(line)] if e.get("type") in ("turn.failed", "error")]
        raise ValueError(f"Codex returned no answer: {str(failed[-1] if failed else 'no error event')[:300]}")
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
                usage["warnings"] += 1
            elif kind not in ("agent_message", "reasoning"):
                tools.append(str(kind))
        if event.get("type") == "turn.completed":
            usage.update(input_tokens=event.get("usage", {}).get("input_tokens"),
                         output_tokens=event.get("usage", {}).get("output_tokens"))
    return answer, tools, usage


def gemini_command(model: str, schema: dict, schema_path: Path, prompt: str, timeout: int) -> tuple[list[str], str | None]:
    return ([find_executable("agy"), "--model", model, "--output-format", "stream-json", "--json-schema",
             str(schema_path), "--sandbox", "--print-timeout", f"{timeout}s", "--print", prompt], None)


def gemini_parse(stdout: str, workdir: Path) -> tuple[dict, list[str], dict]:
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    final = next((d for e in reversed(events) for d in walk(e) if "structured_output" in d), None)
    if final is None:
        raise ValueError("Antigravity returned no structured output")
    tools = [d["tool_name"] for e in events for d in walk(e) if isinstance(d.get("tool_name"), str)
             and d["tool_name"] != "finish"]
    usage = final.get("usage", {})
    return final["structured_output"], tools, {"input_tokens": usage.get("input_tokens"),
                                               "output_tokens": usage.get("output_tokens")}


CLIS: dict[str, dict[str, Any]] = {
    "claude": {"command": claude_command, "parse": claude_parse},
    "codex": {"command": codex_command, "parse": codex_parse},
    "agy": {"command": gemini_command, "parse": gemini_parse},
}
# Each vendor's most capable model and its small, fast tier, as used for curation at scale.
MODELS: dict[str, dict[str, str]] = {
    "claude-opus": {"cli": "claude", "model": "claude-opus-5-5", "tier": "frontier"},
    "gpt-astra": {"cli": "codex", "model": "gpt-6-astra", "tier": "frontier"},
    "gemini-pro": {"cli": "agy", "model": "gemini-3.1-pro-high", "tier": "frontier"},
    "claude-haiku": {"cli": "claude", "model": "claude-haiku-4-5-20251001", "tier": "fast"},
    "gpt-luna": {"cli": "codex", "model": "gpt-5.6-luna", "tier": "fast"},  # gpt-5.4-mini: not available to ChatGPT accounts
    "gemini-flash": {"cli": "agy", "model": "gemini-3.8-flash-medium", "tier": "fast"},
}


def validate_batch(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, dict) or set(answer) != {"results"} or not isinstance(answer["results"], list):
        raise ValueError("batch answer is not an object with a results list")
    for result in answer["results"]:
        if not isinstance(result, dict) or not isinstance(result.get("variation_id"), str):
            raise ValueError("batch result without a variation_id")
        validate_answer({k: v for k, v in result.items() if k != "variation_id"})
    return answer


def validate_answer(answer: Any) -> dict[str, Any]:
    """Check the schema by hand, since not every CLI enforces it."""
    if not isinstance(answer, dict) or set(answer) != set(SCHEMA["required"]):
        raise ValueError("answer is not an object with exactly the required fields")
    if answer["decision"] not in ("admit", "stop") or answer["conflict"] not in ("yes", "no", "unknown"):
        raise ValueError("invalid decision or conflict value")
    if not isinstance(answer["rationale"], str) or not isinstance(answer["submissions"], list):
        raise ValueError("invalid rationale or submissions")
    for row in answer["submissions"]:
        if not isinstance(row, dict) or set(row) != set(FIELDS) or not all(isinstance(row[f], str) for f in FIELDS):
            raise ValueError("invalid submission row")
    return answer


def execute(argv: list[str], stdin: str | None, workdir: Path, timeout: int) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(argv[0]).parent), env.get("PATH", "")])  # node beside nvm CLIs
    return subprocess.run(argv, input=stdin, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def ask(key: str, unit: dict, condition: str, timeout: int, runner: Callable = execute) -> dict:
    """One fresh CLI session for one task (or one batch); retried once on tool use or an invalid answer."""
    spec, model = CLIS[MODELS[key]["cli"]], MODELS[key]["model"]
    batch = condition == "with_source_batch"
    prompt = batch_prompt(unit["tasks"]) if batch else prompt_for(unit, condition)
    schema, check = (BATCH_SCHEMA, validate_batch) if batch else (SCHEMA, validate_answer)
    attempts: list[dict[str, Any]] = []
    for attempt in (1, 2):
        started = time.monotonic()
        record: dict[str, Any] = {"attempt": attempt, "tools_used": [], "error": None}
        with tempfile.TemporaryDirectory(prefix="bioai-llm-bench-") as directory:
            workdir = Path(directory)
            schema_path = workdir / "schema.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            argv, stdin = spec["command"](model, schema, schema_path, prompt, timeout)
            try:
                done = runner(argv, stdin, workdir, timeout)
                record["returncode"] = done.returncode
                record["stderr_tail"] = done.stderr[-800:]
                answer, tools, usage = spec["parse"](done.stdout, workdir)
                record.update(answer=check(answer), tools_used=tools, usage=usage)
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
        record["seconds"] = round(time.monotonic() - started, 1)
        attempts.append(record)
        if record["error"] is None and not record["tools_used"]:
            break
    final = attempts[-1]
    unit_id = ({"batch_id": unit["batch_id"], "task_ids": [t["task_id"] for t in unit["tasks"]]} if batch
               else {"task_id": unit["task_id"]})
    return {**unit_id, "backend": key, "model": model, "condition": condition,
            "prompt_sha256": sha256_text(prompt), "ok": final.get("answer") is not None, "answer": final.get("answer"),
            "tools_used": final["tools_used"], "attempts": attempts, "finished_at": dt.datetime.now(dt.UTC).isoformat()}


def cli_version(name: str) -> str:
    try:
        done = subprocess.run([find_executable(name), "--version"], capture_output=True, text=True, timeout=60)
        return (done.stdout or done.stderr).strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return "unknown"


def run(args: argparse.Namespace) -> int:
    tasks = [json.loads(line) for line in (ROOT / "tasks" / f"{args.split}.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.limit:
        tasks = tasks[:args.limit]
    out = args.output / args.split
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"backends": {}}
    manifest.update({"split": args.split, "prompt_template_sha256": sha256_text(PROMPT),
                     "batch_prompt_template_sha256": sha256_text(BATCH_PROMPT), "batch_size": BATCH_SIZE,
                     "schema_sha256": sha256_text(json.dumps(SCHEMA, sort_keys=True)),
                     "batch_schema_sha256": sha256_text(json.dumps(BATCH_SCHEMA, sort_keys=True)),
                     "tasks_sha256": sha256_text((ROOT / "tasks" / f"{args.split}.jsonl").read_text(encoding="utf-8"))})
    jobs = []
    for key in args.models:
        manifest["backends"][key] = {**MODELS[key], "cli_version": cli_version(MODELS[key]["cli"])}
        for condition in args.conditions:
            folder = out / key / condition
            folder.mkdir(parents=True, exist_ok=True)
            units = batches(tasks) if condition == "with_source_batch" else tasks
            for unit in units:
                raw = folder / f"{unit.get('batch_id') or unit['task_id']}.json"
                if raw.exists() and json.loads(raw.read_text(encoding="utf-8")).get("ok"):
                    continue  # resume: already answered
                jobs.append((key, unit, condition, raw))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(jobs)} call(s) to make", flush=True)

    def work(job):
        key, unit, condition, raw = job
        timeout = args.timeout * 3 if condition == "with_source_batch" else args.timeout
        result = ask(key, unit, condition, timeout)
        raw.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers * len(args.models)) as pool:
        for n, result in enumerate(pool.map(work, jobs), start=1):
            failures += not result["ok"]
            status = "ok" if result["ok"] else "FAILED " + str(result["attempts"][-1]["error"])[:120]
            tools = f" tools={result['tools_used']}" if result["tools_used"] else ""
            unit = result.get("batch_id") or result["task_id"]
            print(f"[{n}/{len(jobs)}] {result['backend']} {result['condition']} {unit}: {status}{tools}", flush=True)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["pilot", "test"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=CONDITIONS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=2, help="Concurrent calls per backend")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per call (three times this for a batch)")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
