"""Run: python3 -m uk_hunter search [--format table|json|md]."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import shutil
from typing import Any
from urllib.parse import urlsplit

from .evaluate import evaluate
from .providers import fetch_feed

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def default_profile_path() -> Path:
    """Prioritise private overrides, including legacy v0.1 overlay paths."""
    for path in (
        ROOT / "local_config" / "search_profile.json",
        ROOT / "config" / "search_profile.json",
        ROOT / "config" / "profile.example.json",
    ):
        if path.exists():
            return path
    return ROOT / "config" / "profile.example.json"


def format_markdown(jobs: list[dict], failed: list[str], include_all: bool = False) -> str:
    counts = {v: sum(job.get("verdict") == v for job in jobs) for v in ("SHORTLIST", "REVIEW", "REJECT", "SKIP_OLD")}
    lines = ["# UK Job Hunter — candidate scan", "", f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
             f"Shortlisted: **{counts['SHORTLIST']}** · Review: **{counts['REVIEW']}** · Rejected: **{counts['REJECT']}** · Older: **{counts['SKIP_OLD']}**", "",
             "**A shortlist is a screening result, not confirmation that every essential criterion is met.**", ""]
    for verdict in (("SHORTLIST", "REVIEW", "REJECT", "SKIP_OLD") if include_all else ("SHORTLIST", "REVIEW")):
        subset = [j for j in jobs if j.get("verdict") == verdict]
        lines.extend([f"## {verdict.title()} ({len(subset)})", ""])
        if not subset:
            lines.extend(["None found in this scan.", ""])
        for j in subset:
            pay = "Not confirmed" if j.get("salary_min") is None and j.get("salary_max") is None else f"£{j.get('salary_min'):,}" if j.get("salary_min") is not None else "Below a verified maximum"
            if j.get("salary_max") is not None:
                pay += f"–£{j['salary_max']:,}" if j.get("salary_min") is not None else f" (£{j['salary_max']:,} max)"
            lines += [f"### {j['company']} — {j['title']}", f"- Fit score: **{j['score']}** (triage, not application likelihood)",
                      f"- Location: {j.get('location') or 'Unspecified'} · Workplace: {j.get('workplace_type')}",
                      f"- Annual basic pay: {pay}", f"- [Official vacancy]({j['url']})", "- Reasons: " + "; ".join(j.get("reasons", [])), ""]
    if failed:
        lines.extend(["## Source failures (do not interpret as no vacancies)", ""])
        lines.extend(f"- {f}" for f in failed)
        lines.append("")
    lines.extend(["## Important", "", "No applications are submitted automatically. Verify UK-wide remote eligibility, salary, qualifications, right to work, posting status and exact office attendance before applying.", ""])
    return "\n".join(lines)


def render_table(jobs: list[dict], failed: list[str], include_all: bool = False) -> str:
    lines = ["VERDICT    SCORE COMPANY            JOB TITLE / LOCATION"]
    for job in jobs:
        if not include_all and job.get("verdict") not in {"SHORTLIST", "REVIEW"}:
            continue
        lines.append(f"{job['verdict']:<10} {job['score']:>3}  {job['company'][:17]:<18} {job['title']} — {job.get('location', '')}")
        lines.append(f"    {job['url']}")
    if len(lines) == 1:
        lines.append("No roles passed the initial title/location filters (or no feeds could be fetched).")
    if failed:
        lines.extend(["SOURCE ERRORS:"] + [f"  {s}" for s in failed])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UK read-only job scanner: employer APIs, structured careers sites and optional licensed boards")
    sub = parser.add_subparsers(dest="command", required=True)
    initial = sub.add_parser("init", help="Create a local, Git-ignored search profile from the public example")
    initial.add_argument("--output", type=Path, default=ROOT / "local_config" / "search_profile.json")
    find = sub.add_parser("search")
    find.add_argument("--query", "-q", default="", help="Optional keyword filter across title, company, location and description")
    find.add_argument("--all", action="store_true", help="Search everything: include vacancies outside personal match preferences")
    find.add_argument("--location", "-l", default="United Kingdom", help="UK location only")
    find.add_argument("--jobage", type=int, default=None, help="Exclude known postings older than N days; unknown dates retained")
    find.add_argument("--limit", "-n", type=int, default=30)
    find.add_argument("--format", choices=["table", "json", "md", "plain"], default="table")
    find.add_argument("--remote", choices=["remote", "hybrid", "onsite"], default=None, help="Optional strict workplace filter")
    find.add_argument("--sources", type=Path, default=ROOT / "config" / "sources.json")
    find.add_argument("--profile", type=Path, default=default_profile_path())
    find.add_argument("--write-report", type=Path, default=None, help="Save Markdown report to local path")
    browser = sub.add_parser("web", help="Launch the private local browser app")
    browser.add_argument("--port", type=int, default=8765)
    browser.add_argument("--open", action="store_true", help="Open the app in your default browser")
    detail = sub.add_parser("detail")
    detail.add_argument("job_url", help="Previously returned job URL; never fetched directly")
    detail.add_argument("--format", choices=["json", "plain"], default="plain")
    detail.add_argument("--sources", type=Path, default=ROOT / "config" / "sources.json")
    args = parser.parse_args(argv)
    if args.command == "web":
        from .webapp import serve
        if not 1024 <= args.port <= 65535:
            parser.error("port must be between 1024 and 65535")
        serve(args.port, open_browser=args.open)
        return 0
    if args.command == "init":
        if args.output.exists():
            print(f"Refusing to overwrite existing profile: {args.output}", file=sys.stderr)
            return 1
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "config" / "profile.example.json", args.output)
        except OSError as exc:
            print(f"Could not initialize profile: {exc}", file=sys.stderr)
            return 1
        print(f"Created local profile: {args.output}\nEdit this file before searching. Do not commit it.")
        return 0
    try:
        sources = load_config(args.sources)["sources"]
        if not isinstance(sources, list) or not sources:
            raise ValueError("Configure at least one source in sources.json")
        if args.command == "search":
            if args.location.lower() not in {"uk", "gb", "remote", "united kingdom", "great britain"}:
                parser.error("This build supports the UK only; use --location 'United Kingdom' or 'Remote'")
            if args.limit < 1 or args.limit > 500 or (args.jobage is not None and args.jobage < 1):
                parser.error("limit must be 1..500 and jobage >=1")
            profile = load_config(args.profile)
        jobs, errors = [], []
        for source in sources:
            if source.get("enabled", True) is False:
                continue
            try:
                jobs.extend(fetch_feed(source))
            except (RuntimeError, ValueError, KeyError) as exc:
                errors.append(str(exc))
        if args.command == "detail":
            # Only show detail from records supplied by configured official feeds.
            match = next((j for j in jobs if j["url"] == args.job_url), None)
            if not match:
                print(json.dumps({"code": "NOT_FOUND", "error": "Job absent from configured live feeds", "source_errors": errors}), file=sys.stderr)
                return 1
            print(json.dumps(match, indent=2, ensure_ascii=False) if args.format == "json" else f"{match['title']} at {match['company']}\nLocation: {match['location']}\nURL: {match['url']}\n\n{match['description']}")
            return 0
        from .dedupe import unique_jobs
        scored = []
        for j in unique_jobs(jobs):
            if args.query and args.query.casefold() not in " ".join(str(j.get(k) or "") for k in ("title", "company", "location", "description")).casefold():
                continue
            if args.remote is not None and j.get("workplace_type", "unknown") != args.remote:
                continue
            scored.append(evaluate(j, profile, args.jobage))
        scored.sort(key=lambda x: ({"SHORTLIST": 0, "REVIEW": 1, "REJECT": 2, "SKIP_OLD": 3}.get(x["verdict"], 4), -x["score"], x["company"], x["title"]))
        shown = (scored if args.all else [j for j in scored if j["verdict"] in {"SHORTLIST", "REVIEW"}])[:args.limit]
        if args.format == "json":
            print(json.dumps({"results": [{"title": j["title"], "company": j["company"], "location": j["location"], "url": j["url"],
                    "date": j["date"], "source": j["source"], "fit": j["verdict"].lower(), "score": j["score"], "notes": j["reasons"]} for j in shown],
                              "counts": {k: sum(j["verdict"] == k for j in scored) for k in ("SHORTLIST", "REVIEW", "REJECT", "SKIP_OLD")},
                              "errors": errors}, ensure_ascii=False, indent=2))
        elif args.format == "md":
            print(format_markdown(shown, errors, include_all=args.all))
        else:
            print(render_table(shown, errors, include_all=args.all))
        if args.write_report:
            args.write_report.parent.mkdir(parents=True, exist_ok=True)
            args.write_report.write_text(format_markdown(shown, errors, include_all=args.all), encoding="utf-8")
        # Nonzero when *every* feed failed so unattended scans cannot falsely declare no jobs.
        return 2 if errors and len(errors) == len(sources) else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"code": "CONFIG_ERROR", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
