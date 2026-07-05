from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark
from .calibrate import run_calibration
from .cases import CaseSelection, generate_eval_set, load_eval_set_data, select_eval_cases, validate_eval_set, write_eval_set
from .config import SkillBenchConfig
from .evolve import run_evolution
from .evaluate_skill import run_evaluation
from .observability.logging_io import read_json, resolve_run_dir
from .reports import build_ci_result, build_comparison, write_ci_result, write_comparison, write_junit_xml, write_sarif_report
from .runners import AGENT_RUNNERS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillbench", description="Evaluate and evolve Codex skills.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_parser = sub.add_parser("generate-cases", help="Generate a deterministic eval set for a skill.")
    gen_parser.add_argument("skill_path")
    gen_parser.add_argument("--profile", choices=["smoke", "release", "stress"], default="smoke")
    gen_parser.add_argument("--count", type=int)
    gen_parser.add_argument("--output")

    validate_parser = sub.add_parser("validate-cases", help="Validate an eval set schema and optional source skill hash.")
    validate_parser.add_argument("eval_set")
    validate_parser.add_argument("--skill-path")
    validate_parser.add_argument("--require-hash-match", action="store_true")
    validate_parser.add_argument("--json", action="store_true")

    list_parser = sub.add_parser("list-cases", help="List case ids, tags, modes, and dimensions in an eval set.")
    list_parser.add_argument("eval_set")
    list_parser.add_argument("--json", action="store_true")
    _add_case_selection_args(list_parser)

    eval_parser = sub.add_parser("eval", help="Run a single skill evaluation.")
    eval_parser.add_argument("skill_path")
    eval_parser.add_argument("--eval-set")
    eval_parser.add_argument("--output-dir")
    eval_parser.add_argument("--mode", choices=["judge-only", "full-agent"])
    eval_parser.add_argument("--comet", action="store_true")
    eval_parser.add_argument("--judge-backend", choices=["auto", "local-heuristic", "custom-command"], default=None)
    eval_parser.add_argument("--judge-command", default=None)
    eval_parser.add_argument("--agent-runner", choices=AGENT_RUNNERS, default=None)
    eval_parser.add_argument("--agent-command", default=None)
    eval_parser.add_argument("--agent-timeout", type=float, help="Full-agent command timeout in seconds.")
    _add_case_selection_args(eval_parser)

    evo_parser = sub.add_parser("evo", help="Run GEPA-style skill evolution.")
    evo_parser.add_argument("skill_path")
    evo_parser.add_argument("--eval-set")
    evo_parser.add_argument("--output-dir")
    evo_parser.add_argument("--rounds", type=int, default=3)
    evo_parser.add_argument("--comet", action="store_true")
    evo_parser.add_argument("--judge-backend", choices=["auto", "local-heuristic", "custom-command"], default=None)
    evo_parser.add_argument("--judge-command", default=None)
    evo_parser.add_argument("--agent-runner", choices=AGENT_RUNNERS, default=None)
    evo_parser.add_argument("--agent-command", default=None)
    evo_parser.add_argument("--agent-timeout", type=float, help="Full-agent command timeout in seconds.")
    _add_case_selection_args(evo_parser)

    ci_parser = sub.add_parser("ci", help="Run evaluation and fail on thresholds.")
    ci_parser.add_argument("skill_path")
    ci_parser.add_argument("--eval-set")
    ci_parser.add_argument("--output-dir")
    ci_parser.add_argument("--min-score", type=float, default=8.0)
    ci_parser.add_argument("--min-safety", type=float, default=7.0)
    ci_parser.add_argument("--judge-backend", choices=["auto", "local-heuristic", "custom-command"], default=None)
    ci_parser.add_argument("--judge-command", default=None)
    ci_parser.add_argument("--agent-runner", choices=AGENT_RUNNERS, default=None)
    ci_parser.add_argument("--agent-command", default=None)
    ci_parser.add_argument("--agent-timeout", type=float, help="Full-agent command timeout in seconds.")
    ci_parser.add_argument("--json", action="store_true")
    ci_parser.add_argument("--baseline", help="Baseline report.json or run directory for regression checks.")
    ci_parser.add_argument("--fail-on-regression", action="store_true")
    ci_parser.add_argument("--max-regression", type=float, default=0.0)
    ci_parser.add_argument("--junit", help="Write JUnit XML to this path. Defaults to junit.xml in the run directory when omitted with --json disabled.")
    ci_parser.add_argument("--sarif", help="Write SARIF 2.1.0 output to this path for code scanning integrations.")
    _add_case_selection_args(ci_parser)

    calibrate_parser = sub.add_parser("calibrate", help="Run repeated evaluations and summarize judge stability.")
    calibrate_parser.add_argument("skill_path")
    calibrate_parser.add_argument("--eval-set")
    calibrate_parser.add_argument("--output-dir")
    calibrate_parser.add_argument("--samples", type=int, default=3)
    calibrate_parser.add_argument("--max-total-range", type=float, default=0.25)
    calibrate_parser.add_argument("--mode", choices=["judge-only", "full-agent"])
    calibrate_parser.add_argument("--judge-backend", choices=["auto", "local-heuristic", "custom-command"], default=None)
    calibrate_parser.add_argument("--judge-command", default=None)
    calibrate_parser.add_argument("--agent-runner", choices=AGENT_RUNNERS, default=None)
    calibrate_parser.add_argument("--agent-command", default=None)
    calibrate_parser.add_argument("--agent-timeout", type=float, help="Full-agent command timeout in seconds.")
    calibrate_parser.add_argument("--json", action="store_true")
    _add_case_selection_args(calibrate_parser)

    benchmark_parser = sub.add_parser("benchmark", help="Run the bundled benchmark fixtures and write benchmark.json.")
    benchmark_parser.add_argument("--fixtures", default="examples/benchmarks/skills")
    benchmark_parser.add_argument("--eval-set", default="examples/benchmarks/eval_sets/skill-quality-benchmark.json")
    benchmark_parser.add_argument("--output-dir")
    benchmark_parser.add_argument("--judge-backend", choices=["auto", "local-heuristic", "custom-command"], default=None)
    benchmark_parser.add_argument("--judge-command", default=None)
    benchmark_parser.add_argument("--json", action="store_true")

    report_parser = sub.add_parser("report", help="Print a compact report summary.")
    report_parser.add_argument("run_dir")
    report_parser.add_argument("--json", action="store_true", help="Print the persisted report JSON.")

    compare_parser = sub.add_parser("compare", help="Compare two report.json files or run dirs.")
    compare_parser.add_argument("left")
    compare_parser.add_argument("right")
    compare_parser.add_argument("--json", action="store_true", help="Print machine-readable comparison JSON.")

    dash_parser = sub.add_parser("dashboard", help="Serve the FastAPI dashboard for a run directory.")
    dash_parser.add_argument("run_dir")
    dash_parser.add_argument("--host", default="127.0.0.1")
    dash_parser.add_argument("--port", type=int, default=8765)

    export_parser = sub.add_parser("export-dashboard", help="Export a run dashboard to static HTML files.")
    export_parser.add_argument("run_dir")
    export_parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-cases":
        eval_set = generate_eval_set(args.skill_path, profile=args.profile, count=args.count)
        output = Path(args.output) if args.output else Path(".skillbench") / "evals" / f"{eval_set.id}.json"
        path = write_eval_set(eval_set, output)
        print(json.dumps({"eval_set_id": eval_set.id, "cases": len(eval_set.cases), "output": str(path)}, ensure_ascii=False))
        return 0

    if args.command == "validate-cases":
        result = validate_eval_set(
            args.eval_set,
            skill_path=args.skill_path,
            require_hash_match=args.require_hash_match,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            status = "passed" if result["passed"] else "failed"
            print(f"Eval set validation {status}: {result.get('eval_set_id', args.eval_set)}")
            for error in result.get("errors", []):
                print(f"ERROR [{error['type']}]: {error['message']}")
            for warning in result.get("warnings", []):
                print(f"WARN  [{warning['type']}]: {warning['message']}")
        return 0 if result["passed"] else 1

    if args.command == "list-cases":
        eval_set = load_eval_set_data(args.eval_set)
        eval_set = select_eval_cases(eval_set, _case_selection(args))
        inventory = _case_inventory(eval_set)
        if args.json:
            print(json.dumps(inventory, ensure_ascii=False))
        else:
            print(_format_case_inventory(inventory))
        return 0

    if args.command == "eval":
        config = SkillBenchConfig.from_env(args.output_dir)
        config.comet_enabled = bool(args.comet or config.comet_enabled)
        if args.judge_backend:
            config.judge_backend = args.judge_backend
        if args.judge_command:
            config.judge_command = args.judge_command
        _apply_agent_args(config, args)
        if args.agent_timeout is not None:
            config.agent_timeout_sec = args.agent_timeout
        report = run_evaluation(
            args.skill_path,
            eval_set_path=args.eval_set,
            output_dir=args.output_dir,
            config=config,
            mode_override=args.mode,
            **_case_selection_kwargs(args),
        )
        print(json.dumps({"run_id": report.run_id, "total_score": report.total_score, "report": report.artifacts["report_json"]}, ensure_ascii=False))
        return 0

    if args.command == "evo":
        config = SkillBenchConfig.from_env(args.output_dir)
        config.comet_enabled = bool(args.comet or config.comet_enabled)
        if args.judge_backend:
            config.judge_backend = args.judge_backend
        if args.judge_command:
            config.judge_command = args.judge_command
        _apply_agent_args(config, args)
        if args.agent_timeout is not None:
            config.agent_timeout_sec = args.agent_timeout
        evolution = run_evolution(
            args.skill_path,
            eval_set_path=args.eval_set,
            output_dir=args.output_dir,
            rounds=args.rounds,
            config=config,
            **_case_selection_kwargs(args),
        )
        print(json.dumps({"run_id": evolution.run_id, "best_candidate_id": evolution.best_candidate_id, "evolution": evolution.artifacts["evolution_json"]}, ensure_ascii=False))
        return 0

    if args.command == "ci":
        config = SkillBenchConfig.from_env(args.output_dir)
        config.min_total_score = args.min_score
        config.min_safety_score = args.min_safety
        if args.judge_backend:
            config.judge_backend = args.judge_backend
        if args.judge_command:
            config.judge_command = args.judge_command
        _apply_agent_args(config, args)
        if args.agent_timeout is not None:
            config.agent_timeout_sec = args.agent_timeout
        report = run_evaluation(
            args.skill_path,
            eval_set_path=args.eval_set,
            output_dir=args.output_dir,
            config=config,
            **_case_selection_kwargs(args),
        )
        baseline = _load_report(args.baseline) if args.baseline else None
        ci_result = build_ci_result(
            report,
            min_score=args.min_score,
            min_safety=args.min_safety,
            baseline=baseline,
            fail_on_regression=args.fail_on_regression,
            max_regression=args.max_regression,
        )
        ci_path = Path(report.artifacts["report_json"]).parent / "ci_result.json"
        write_ci_result(ci_result, ci_path)
        junit_path = Path(args.junit) if args.junit else None
        if junit_path is None and not args.json:
            junit_path = Path(report.artifacts["report_json"]).parent / "junit.xml"
        if junit_path:
            write_junit_xml(ci_result, junit_path)
        if args.sarif:
            write_sarif_report(ci_result, args.sarif)
        if args.json:
            print(json.dumps(ci_result, ensure_ascii=False))
        else:
            safety = report.dimension_scores.get("safety", 10.0)
            print(f"SkillBench total={report.total_score:.2f} safety={safety:.2f} worst_case={report.worst_case_id}")
            if not ci_result["passed"]:
                print(f"Report: {report.artifacts['report_json']}")
                print(f"CI result: {ci_path}")
            if junit_path:
                print(f"JUnit: {junit_path}")
            if args.sarif:
                print(f"SARIF: {args.sarif}")
        if not ci_result["passed"]:
            return 1
        return 0

    if args.command == "calibrate":
        config = SkillBenchConfig.from_env(args.output_dir)
        if args.judge_backend:
            config.judge_backend = args.judge_backend
        if args.judge_command:
            config.judge_command = args.judge_command
        _apply_agent_args(config, args)
        if args.agent_timeout is not None:
            config.agent_timeout_sec = args.agent_timeout
        result = run_calibration(
            args.skill_path,
            eval_set_path=args.eval_set,
            output_dir=args.output_dir,
            samples=args.samples,
            max_total_range=args.max_total_range,
            config=config,
            mode_override=args.mode,
            **_case_selection_kwargs(args),
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(
                f"SkillBench calibration stable={result['stable']} "
                f"samples={result['samples']} total_range={result['total_score']['range']}"
            )
            print(f"Calibration: {result['artifacts']['calibration_json']}")
        return 0 if result["stable"] else 1

    if args.command == "benchmark":
        config = SkillBenchConfig.from_env(args.output_dir or ".skillbench/benchmarks")
        if args.judge_backend:
            config.judge_backend = args.judge_backend
        if args.judge_command:
            config.judge_command = args.judge_command
        result = run_benchmark(
            args.fixtures,
            args.eval_set,
            output_dir=args.output_dir or config.output_root,
            config=config,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(_format_benchmark(result))
        return 0

    if args.command == "report":
        report = _load_report(args.run_dir)
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(_format_report(report))
        return 0

    if args.command == "compare":
        left = _load_report(args.left)
        right = _load_report(args.right)
        comparison = build_comparison(left, right)
        output_dir = resolve_run_dir(args.right)
        output_path = (output_dir if output_dir.is_dir() else output_dir.parent) / "comparison.json"
        write_comparison(comparison, output_path)
        if args.json:
            print(json.dumps(comparison, ensure_ascii=False))
        else:
            print(_format_compare(left, right))
            print(f"Comparison: {output_path}")
        return 0

    if args.command == "dashboard":
        from .dashboard.app import serve

        serve(args.run_dir, host=args.host, port=args.port)
        return 0

    if args.command == "export-dashboard":
        from .dashboard import export_dashboard

        manifest = export_dashboard(args.run_dir, args.output)
        print(json.dumps(manifest, ensure_ascii=False))
        return 0

    parser.error("unknown command")
    return 2


def _load_report(path: str | Path) -> dict:
    value = resolve_run_dir(path)
    if value.is_dir():
        value = value / "report.json"
    return read_json(value)


def _add_case_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-id", action="append", dest="case_ids", help="Run only this case id. Repeat to select multiple cases.")
    parser.add_argument("--include-tag", action="append", dest="include_tags", help="Run cases containing this tag. Repeat for OR matching.")
    parser.add_argument("--exclude-tag", action="append", dest="exclude_tags", help="Skip cases containing this tag. Repeat for OR matching.")
    parser.add_argument("--case-mode", choices=["judge-only", "full-agent"], help="Run only cases declared with this mode.")
    parser.add_argument("--limit", type=int, help="Run at most this many selected cases after filtering.")


def _case_selection(args: argparse.Namespace) -> CaseSelection:
    return CaseSelection(
        case_ids=args.case_ids or [],
        include_tags=args.include_tags or [],
        exclude_tags=args.exclude_tags or [],
        mode=args.case_mode,
        limit=args.limit,
    )


def _case_selection_kwargs(args: argparse.Namespace) -> dict:
    return {
        "case_ids": args.case_ids,
        "include_tags": args.include_tags,
        "exclude_tags": args.exclude_tags,
        "case_mode": args.case_mode,
        "limit": args.limit,
    }


def _apply_agent_args(config: SkillBenchConfig, args: argparse.Namespace) -> None:
    if getattr(args, "agent_runner", None):
        config.agent_runner = args.agent_runner
    if getattr(args, "agent_command", None):
        config.agent_command = args.agent_command


def _case_inventory(eval_set) -> dict:
    cases = [
        {
            "id": case.id,
            "mode": case.mode,
            "type": case.type,
            "tags": list(case.tags),
            "dimensions": list(case.dimensions),
            "weight": case.weight,
            "difficulty": case.difficulty,
            "category": case.category,
            "golden_behavior": list(case.golden_behavior),
            "anti_patterns": list(case.anti_patterns),
            "rubric_notes": list(case.rubric_notes),
        }
        for case in eval_set.cases
    ]
    return {
        "eval_set_id": eval_set.id,
        "profile": eval_set.profile,
        "source_skill_hash": eval_set.source_skill_hash,
        "case_count": len(cases),
        "tags": sorted({tag for case in eval_set.cases for tag in case.tags}),
        "modes": sorted({case.mode for case in eval_set.cases}),
        "types": sorted({case.type for case in eval_set.cases}),
        "selection": eval_set.metadata.get("selection"),
        "cases": cases,
    }


def _format_case_inventory(inventory: dict) -> str:
    lines = [
        f"Eval set: {inventory['eval_set_id']}",
        f"Profile: {inventory.get('profile')}",
        f"Cases: {inventory['case_count']}",
        f"Tags: {', '.join(inventory.get('tags', [])) or '-'}",
        "ID\tMODE\tTYPE\tDIFFICULTY\tCATEGORY\tTAGS\tDIMENSIONS",
    ]
    for case in inventory.get("cases", []):
        lines.append(
            "\t".join(
                [
                    str(case["id"]),
                    str(case["mode"]),
                    str(case["type"]),
                    str(case["difficulty"]),
                    str(case["category"]),
                    ",".join(case.get("tags", [])) or "-",
                    ",".join(case.get("dimensions", [])) or "-",
                ]
            )
        )
    return "\n".join(lines)


def _format_report(report: dict) -> str:
    lines = [
        f"Run: {report['run_id']}",
        f"Candidate: {report['candidate_id']}",
        f"Total: {report['total_score']} ({report['grade']})",
        f"Worst case: {report.get('worst_case_id')}",
        "Dimensions:",
    ]
    for name, score in sorted(report.get("dimension_scores", {}).items()):
        lines.append(f"  {name}: {score}")
    return "\n".join(lines)


def _format_compare(left: dict, right: dict) -> str:
    delta = float(right["total_score"]) - float(left["total_score"])
    lines = [
        f"Left:  {left['run_id']} total={left['total_score']}",
        f"Right: {right['run_id']} total={right['total_score']}",
        f"Delta: {delta:+.3f}",
        "Dimension deltas:",
    ]
    names = sorted(set(left.get("dimension_scores", {})) | set(right.get("dimension_scores", {})))
    for name in names:
        lval = float(left.get("dimension_scores", {}).get(name, 0.0))
        rval = float(right.get("dimension_scores", {}).get(name, 0.0))
        lines.append(f"  {name}: {rval - lval:+.3f}")
    return "\n".join(lines)


def _format_benchmark(result: dict) -> str:
    lines = [
        f"Benchmark: {result['benchmark_id']}",
        f"Run: {result['run_id']}",
        f"Fixtures: {result['fixture_count']}",
        "Ranking:",
    ]
    for item in result.get("ranking", []):
        lines.append(
            f"  {item['rank']}. {item['fixture_id']} total={item['total_score']} "
            f"grade={item['grade']} worst_case={item.get('worst_case_id')}"
        )
    lines.append(f"Benchmark JSON: {result['artifacts']['benchmark_json']}")
    return "\n".join(lines)
