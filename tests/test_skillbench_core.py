from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from skillbench.dashboard import export_dashboard, render_dashboard_html
from skillbench.cases import CaseSelection, generate_eval_set, select_eval_cases, validate_eval_set, write_eval_set
from skillbench.cli import main as skillbench_main
from skillbench.config import SkillBenchConfig
from skillbench.evolve import run_evolution
from skillbench.evaluate_skill import run_evaluation
from skillbench.judges import build_judge_backend
from skillbench.runners import FullAgentRunner
from skillbench.reports import build_ci_result, build_comparison, build_junit_xml, build_sarif_report, write_sarif_report
from skillbench.schemas import EvalCase, EvalSet


SAMPLE_SKILL = ROOT / "examples" / "skills" / "sample-skill" / "SKILL.md"
EVAL_SET = ROOT / "examples" / "eval_sets" / "basic-skill-eval.json"


def test_eval_writes_report(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)

    report_path = Path(report.artifacts["report_json"])
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["total_score"] >= 7
    assert data["worst_case_id"]
    assert (report_path.parent / "case_results.jsonl").exists()
    assert (report_path.parent / "summary.md").exists()


def test_eval_writes_judge_artifacts_and_summary(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent
    first = report.case_results[0]

    assert (run_dir / "summary.md").exists()
    assert (run_dir / first.evidence["judge_input_path"]).exists()
    assert (run_dir / first.evidence["judge_output_path"]).exists()


def test_generate_cases_writes_metadata_and_case_types(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke", count=8)
    output = write_eval_set(eval_set, tmp_path / "generated.json")

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["profile"] == "smoke"
    assert data["source_skill_hash"].startswith("sha256:")
    assert {case["type"] for case in data["cases"]} >= {"should-trigger", "should-not-trigger", "ambiguous", "safety"}
    assert all(case["tags"] for case in data["cases"])


def test_validate_cases_passes_generated_eval_set(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke", count=8)
    output = write_eval_set(eval_set, tmp_path / "generated.json")

    result = validate_eval_set(output, skill_path=SAMPLE_SKILL, require_hash_match=True)

    assert result["passed"] is True
    assert result["cases"] == 8
    assert result["errors"] == []


def test_validate_cases_rejects_duplicate_case_ids(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke", count=2)
    eval_set.cases[1].id = eval_set.cases[0].id
    output = write_eval_set(eval_set, tmp_path / "bad.json")

    result = validate_eval_set(output)

    assert result["passed"] is False
    assert any(error["type"] == "duplicate-case-id" for error in result["errors"])


def test_case_selection_filters_by_tags_mode_and_limit():
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="release")

    selected = select_eval_cases(
        eval_set,
        CaseSelection(include_tags=["release"], exclude_tags=["full-agent"], mode="judge-only", limit=2),
    )

    assert len(selected.cases) == 2
    assert selected.metadata["selection"]["original_case_count"] == len(eval_set.cases)
    assert selected.metadata["selection"]["selected_case_count"] == 2
    assert all(case.mode == "judge-only" for case in selected.cases)
    assert all("release" in case.tags and "full-agent" not in case.tags for case in selected.cases)


def test_eval_case_selection_limits_written_eval_set(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke")
    eval_set_path = write_eval_set(eval_set, tmp_path / "generated.json")

    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "run", include_tags=["safety"])

    assert [result.case_id for result in report.case_results] == ["safety-001"]
    run_dir = Path(report.artifacts["report_json"]).parent
    written_eval_set = json.loads((run_dir / "eval_set.json").read_text(encoding="utf-8"))
    assert [case["id"] for case in written_eval_set["cases"]] == ["safety-001"]
    assert written_eval_set["metadata"]["selection"]["include_tags"] == ["safety"]


def test_list_cases_cli_json_outputs_case_inventory(tmp_path, capsys):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke")
    eval_set_path = write_eval_set(eval_set, tmp_path / "generated.json")

    exit_code = skillbench_main(["list-cases", str(eval_set_path), "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert data["eval_set_id"] == eval_set.id
    assert data["case_count"] == len(eval_set.cases)
    assert "safety" in data["tags"]
    assert any(case["id"] == "safety-001" and "safety" in case["tags"] for case in data["cases"])


def test_list_cases_cli_respects_selection_filters(tmp_path, capsys):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke")
    eval_set_path = write_eval_set(eval_set, tmp_path / "generated.json")

    exit_code = skillbench_main(["list-cases", str(eval_set_path), "--include-tag", "safety", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert [case["id"] for case in data["cases"]] == ["safety-001"]
    assert data["selection"]["include_tags"] == ["safety"]


def test_evolution_passes_case_selection_to_nested_evaluations(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke")
    eval_set_path = write_eval_set(eval_set, tmp_path / "generated.json")

    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "evo", rounds=1, case_ids=["safety-001"])
    mutated_report = json.loads(Path(evolution.steps[0].report_path).read_text(encoding="utf-8"))

    assert [result["case_id"] for result in mutated_report["case_results"]] == ["safety-001"]


def test_evolution_records_candidates_and_steps(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path, rounds=1)

    evolution_path = Path(evolution.artifacts["evolution_json"])
    assert evolution_path.exists()
    data = json.loads(evolution_path.read_text(encoding="utf-8"))
    assert len(data["candidates"]) >= 2
    assert len(data["steps"]) == 1
    assert data["best_candidate_id"].startswith("candidate_")


def test_dashboard_renders_evolution_round_detail(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path, rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent
    html = render_dashboard_html(run_dir / "evolution" / "rounds" / "0")

    assert "Evolution Round 0" in html
    assert "Reflection" in html
    assert "Mutation" in html
    assert "Decision" in html


def test_export_dashboard_writes_evolution_round_pages(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "evo", rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "evo-site")

    assert "index.html" in manifest["pages"]
    round_page = tmp_path / "evo-site" / "evolution" / "rounds" / "0" / "index.html"
    assert round_page.exists()
    assert "Evolution Round 0" in round_page.read_text(encoding="utf-8")


def test_dashboard_renders_report(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    html = render_dashboard_html(Path(report.artifacts["report_json"]).parent)

    assert "SkillBench Report" in html
    assert "Dimension Scores" in html
    assert "should-trigger-eval" in html


def test_dashboard_case_detail_route_reads_artifacts(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent
    case_id = report.case_results[0].case_id
    html = render_dashboard_html(run_dir / "cases" / case_id)

    assert case_id in html
    assert "Evidence" in html
    assert "Judge Input" in html


def test_dashboard_case_detail_renders_full_agent_artifacts(tmp_path):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; import sys; '
        'Path(\'artifact.txt\').write_text(\'agent file\', encoding=\'utf-8\'); '
        'print(\'stdout-marker\'); print(\'stderr-marker\', file=sys.stderr)"'
    )
    eval_set = EvalSet(
        id="agent-dashboard-eval",
        cases=[
            EvalCase(
                id="agent-dashboard-case",
                mode="full-agent",
                type="behavior",
                input="collect visible artifacts",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "agent-dashboard-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", agent_command=command)
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "cases" / "agent-dashboard-case")

    assert "Agent Run" in html
    assert "Agent Stdout" in html
    assert "stdout-marker" in html
    assert "Agent Stderr" in html
    assert "stderr-marker" in html
    assert "Agent Files" in html
    assert "artifact.txt" in html


def test_dashboard_case_detail_renders_custom_judge_error(tmp_path):
    bad_judge = tmp_path / "bad_judge.py"
    bad_judge.write_text("print('not json')\n", encoding="utf-8")
    eval_set = EvalSet(
        id="dashboard-bad-judge-eval",
        cases=[EvalCase(id="dashboard-bad-judge-case", input="x", dimensions=["safety"])],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "dashboard-bad-judge-eval.json")
    config = SkillBenchConfig(
        output_root=tmp_path / "runs",
        judge_backend="custom-command",
        judge_command=f'"{sys.executable}" "{bad_judge}"',
    )
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "cases" / "dashboard-bad-judge-case")

    assert "Judge Error" in html
    assert "invalid-json" in html
    assert "not json" in html


def test_export_dashboard_writes_static_report_pages(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "run")
    run_dir = Path(report.artifacts["report_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "site")

    assert "index.html" in manifest["pages"]
    first_case_page = tmp_path / "site" / "cases" / report.case_results[0].case_id / "index.html"
    assert first_case_page.exists()
    assert "Judge Input" in first_case_page.read_text(encoding="utf-8")


def test_export_dashboard_static_case_page_includes_full_agent_artifacts(tmp_path):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; Path(\'artifact.txt\').write_text(\'agent file\', encoding=\'utf-8\'); '
        'print(\'stdout-marker\')"'
    )
    eval_set = EvalSet(
        id="agent-static-eval",
        cases=[
            EvalCase(
                id="agent-static-case",
                mode="full-agent",
                type="behavior",
                input="collect static artifacts",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "agent-static-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", agent_command=command)
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    export_dashboard(run_dir, tmp_path / "site")

    case_page = tmp_path / "site" / "cases" / "agent-static-case" / "index.html"
    text = case_page.read_text(encoding="utf-8")
    assert "Agent Run" in text
    assert "stdout-marker" in text
    assert "artifact.txt" in text


def test_export_dashboard_static_case_page_includes_judge_error(tmp_path):
    bad_judge = tmp_path / "bad_judge.py"
    bad_judge.write_text("print('not json')\n", encoding="utf-8")
    eval_set = EvalSet(
        id="static-bad-judge-eval",
        cases=[EvalCase(id="static-bad-judge-case", input="x", dimensions=["safety"])],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "static-bad-judge-eval.json")
    config = SkillBenchConfig(
        output_root=tmp_path / "runs",
        judge_backend="custom-command",
        judge_command=f'"{sys.executable}" "{bad_judge}"',
    )
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    export_dashboard(run_dir, tmp_path / "site")

    case_page = tmp_path / "site" / "cases" / "static-bad-judge-case" / "index.html"
    text = case_page.read_text(encoding="utf-8")
    assert "Judge Error" in text
    assert "invalid-json" in text
    assert "not json" in text


def test_full_agent_runner_records_file_evidence(tmp_path):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; import sys; Path(\'artifact.txt\').write_text(sys.stdin.read(), encoding=\'utf-8\')"'
    )
    case = EvalCase(
        id="agent-evidence",
        mode="full-agent",
        type="behavior",
        input="write this into an artifact",
        dimensions=["evidence_quality", "safety"],
    )
    result = FullAgentRunner(command=command).run_case(SAMPLE_SKILL.read_text(encoding="utf-8"), case, tmp_path)

    behavior = result.evidence["behavior"]
    assert behavior["returncode"] == 0
    assert {"path": "artifact.txt", "size": len(case.input)} in behavior["files"]
    run_dir = Path(behavior["workdir"])
    assert (run_dir / "input.txt").exists()
    assert (run_dir / "command.json").exists()
    assert (run_dir / "stdout.txt").exists()
    assert (run_dir / "stderr.txt").exists()
    assert (run_dir / "exit_code.txt").exists()
    assert (run_dir / "files.json").exists()


def test_full_agent_runner_records_timeout_evidence(tmp_path):
    command = f'"{sys.executable}" -c "import time; time.sleep(2)"'
    case = EvalCase(
        id="agent-timeout",
        mode="full-agent",
        type="behavior",
        input="this command will time out",
        dimensions=["evidence_quality", "safety"],
    )

    result = FullAgentRunner(command=command, timeout_sec=0.1).run_case(SAMPLE_SKILL.read_text(encoding="utf-8"), case, tmp_path)

    behavior = result.evidence["behavior"]
    run_dir = Path(behavior["workdir"])
    assert behavior["timed_out"] is True
    assert behavior["returncode"] is None
    assert "timed out" in behavior["stderr"].lower()
    assert (run_dir / "stdout.txt").exists()
    assert (run_dir / "stderr.txt").exists()
    assert (run_dir / "exit_code.txt").read_text(encoding="utf-8") == "timeout"
    assert (run_dir / "files.json").exists()


def test_evaluation_uses_configured_full_agent_timeout(tmp_path):
    command = f'"{sys.executable}" -c "import time; time.sleep(2)"'
    eval_set = EvalSet(
        id="timeout-eval",
        cases=[
            EvalCase(
                id="timeout-case",
                mode="full-agent",
                type="behavior",
                input="run slowly",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "timeout-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", agent_command=command, agent_timeout_sec=0.1)

    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)

    behavior = report.case_results[0].evidence["behavior"]
    assert behavior["timed_out"] is True
    assert behavior["returncode"] is None


def test_custom_command_judge_returns_case_result(tmp_path):
    fake = tmp_path / "fake_judge.py"
    fake.write_text(
        "import json, sys\n"
        "payload=json.load(sys.stdin)\n"
        "json.dump({'case_id': payload['case']['id'], 'score': 8.5, "
        "'dimension_scores': {'safety': 9}, 'rationale': 'ok', "
        "'suggestion': 'keep', 'evidence_refs': []}, sys.stdout)\n",
        encoding="utf-8",
    )
    backend = build_judge_backend("custom-command", f'"{sys.executable}" "{fake}"')
    result = backend.judge("skill text", EvalCase(id="case-1", input="x", dimensions=["safety"]))

    assert result.score == 8.5
    assert result.dimension_scores["safety"] == 9


def test_custom_command_judge_failure_is_recorded_as_case_result(tmp_path):
    bad_judge = tmp_path / "bad_judge.py"
    bad_judge.write_text("print('not json')\n", encoding="utf-8")
    eval_set = EvalSet(
        id="bad-judge-eval",
        cases=[EvalCase(id="bad-judge-case", input="x", dimensions=["safety"])],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "bad-judge-eval.json")
    config = SkillBenchConfig(
        output_root=tmp_path / "runs",
        judge_backend="custom-command",
        judge_command=f'"{sys.executable}" "{bad_judge}"',
    )

    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)

    result = report.case_results[0]
    run_dir = Path(report.artifacts["report_json"]).parent
    assert result.score == 0
    assert result.failed_dimensions == ["safety"]
    assert result.evidence["judge_error"]["kind"] == "invalid-json"
    assert "not json" in result.evidence["judge_error"]["stdout"]
    assert (run_dir / result.evidence["judge_output_path"]).exists()


def test_ci_json_result_fails_threshold(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    result = build_ci_result(report, min_score=9.9, min_safety=9.0)

    assert result["passed"] is False
    assert result["failures"]


def test_ci_regression_gate_fails_against_baseline(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    baseline = {
        "run_id": "baseline",
        "total_score": report.total_score + 0.5,
        "dimension_scores": {name: score + 0.5 for name, score in report.dimension_scores.items()},
    }

    result = build_ci_result(
        report,
        min_score=0.0,
        min_safety=0.0,
        baseline=baseline,
        fail_on_regression=True,
        max_regression=0.0,
    )

    assert result["passed"] is False
    assert result["regression"]["total_delta"] == -0.5
    assert any(failure["type"] == "regression" for failure in result["failures"])


def test_junit_xml_reports_ci_failures(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    result = build_ci_result(report, min_score=9.9, min_safety=0.0)
    xml = build_junit_xml(result)

    assert "<testsuite" in xml
    assert "failures=\"1\"" in xml


def test_ci_text_mode_writes_default_junit_xml(tmp_path):
    output_dir = tmp_path / "ci-runs"

    exit_code = skillbench_main(
        [
            "ci",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(output_dir),
            "--min-score",
            "0",
            "--min-safety",
            "0",
        ]
    )

    run_dir = Path((output_dir / "latest.txt").read_text(encoding="utf-8").strip())
    assert exit_code == 0
    assert (run_dir / "junit.xml").exists()


def test_sarif_report_maps_ci_failures_to_results(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    result = build_ci_result(report, min_score=9.9, min_safety=0.0)

    sarif = build_sarif_report(result)

    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "SkillBench"
    assert run["results"][0]["ruleId"] == "skillbench.threshold"
    assert run["results"][0]["level"] == "error"
    assert run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].endswith("report.json")


def test_write_sarif_report_creates_file(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "run")
    result = build_ci_result(report, min_score=9.9, min_safety=0.0)
    output = write_sarif_report(result, tmp_path / "skillbench.sarif")

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["runs"][0]["results"]


def test_build_comparison_reports_total_and_dimension_deltas(tmp_path):
    left = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "left")
    right = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "right")

    comparison = build_comparison(
        json.loads(Path(left.artifacts["report_json"]).read_text(encoding="utf-8")),
        json.loads(Path(right.artifacts["report_json"]).read_text(encoding="utf-8")),
    )

    assert comparison["total_delta"] == 0
    assert "safety" in comparison["dimension_deltas"]


def test_compare_cli_json_outputs_machine_readable_comparison(tmp_path, capsys):
    left = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "left")
    right = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "right")

    exit_code = skillbench_main(["compare", left.artifacts["report_json"], right.artifacts["report_json"], "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    comparison_path = Path(right.artifacts["report_json"]).parent / "comparison.json"
    assert exit_code == 0
    assert data["left_run_id"] == left.run_id
    assert data["right_run_id"] == right.run_id
    assert data["total_delta"] == 0
    assert comparison_path.exists()


def test_report_cli_json_outputs_persisted_report(tmp_path, capsys):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "run")
    run_dir = Path(report.artifacts["report_json"]).parent

    exit_code = skillbench_main(["report", str(run_dir), "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert data["run_id"] == report.run_id
    assert data["total_score"] == report.total_score
    assert data["case_results"]
