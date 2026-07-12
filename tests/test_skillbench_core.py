from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from skillbench.dashboard import export_dashboard, render_dashboard_html
from skillbench.cases import CaseSelection, bootstrap_eval_pack, catalog_eval_packs, generate_eval_set, select_eval_cases, validate_eval_set, write_eval_set
from skillbench.cli import main as skillbench_main
from skillbench.config import SkillBenchConfig
from skillbench.benchmark import run_benchmark
from skillbench.calibrate import run_calibration
from skillbench.evolve import run_evolution
from skillbench.evaluate_skill import run_evaluation
from skillbench.lift import run_lift
from skillbench.matrix import run_harness_matrix
from skillbench.judges import build_judge_backend
from skillbench.runners import FullAgentRunner, build_agent_adapter
from skillbench.reports import build_ci_result, build_comparison, build_harness_matrix_report, build_junit_xml, build_report_bundle, build_sarif_report, render_pr_comment, write_comparison, write_sarif_report
from skillbench.schemas import EvalCase, EvalSet


SAMPLE_SKILL = ROOT / "examples" / "skills" / "sample-skill" / "SKILL.md"
EVAL_SET = ROOT / "examples" / "eval_sets" / "basic-skill-eval.json"
BENCHMARK_FIXTURES = ROOT / "examples" / "benchmarks" / "skills"
BENCHMARK_EVAL_SET = ROOT / "examples" / "benchmarks" / "eval_sets" / "skill-quality-benchmark.json"
EVAL_PACKS_DIR = ROOT / "examples" / "eval_packs"
GENERIC_SKILL_SMOKE_PACK = EVAL_PACKS_DIR / "generic-skill-smoke.json"
PR_COMMENT_WORKFLOW = ROOT / ".github" / "workflows" / "skillbench-pr-comment.yml"
BUNDLE_WORKFLOW = ROOT / ".github" / "workflows" / "skillbench-bundles.yml"


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


def test_eval_writes_dimension_attributions_to_report_and_judge_output(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent
    first = report.case_results[0]
    first_dimension = next(iter(first.dimension_scores))
    judge_output = json.loads((run_dir / first.evidence["judge_output_path"]).read_text(encoding="utf-8"))
    report_json = json.loads(Path(report.artifacts["report_json"]).read_text(encoding="utf-8"))

    attribution = first.dimension_attributions[first_dimension]
    assert attribution["score"] == first.dimension_scores[first_dimension]
    assert attribution["status"] in {"pass", "fail"}
    assert attribution["rationale"]
    assert isinstance(attribution["evidence_refs"], list)
    assert attribution["suggestion"]
    assert judge_output["dimension_attributions"][first_dimension]["score"] == attribution["score"]
    assert report_json["case_results"][0]["dimension_attributions"][first_dimension]["rationale"] == attribution["rationale"]


def test_generate_cases_writes_metadata_and_case_types(tmp_path):
    eval_set = generate_eval_set(SAMPLE_SKILL, profile="smoke", count=8)
    output = write_eval_set(eval_set, tmp_path / "generated.json")

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["profile"] == "smoke"
    assert data["source_skill_hash"].startswith("sha256:")
    assert {case["type"] for case in data["cases"]} >= {"should-trigger", "should-not-trigger", "ambiguous", "safety"}
    assert all(case["tags"] for case in data["cases"])
    assert all(case["difficulty"] in {"easy", "medium", "hard"} for case in data["cases"])
    assert all(case["category"] for case in data["cases"])
    assert all(case["golden_behavior"] for case in data["cases"])
    assert all(case["anti_patterns"] for case in data["cases"])
    assert all(case["rubric_notes"] for case in data["cases"])


def test_eval_preserves_trusted_case_metadata_in_report_and_judge_input(tmp_path):
    eval_set = EvalSet(
        id="trusted-metadata-eval",
        cases=[
            EvalCase(
                id="trusted-safety-case",
                input="Evaluate approval boundaries before running commands.",
                type="safety",
                dimensions=["safety"],
                difficulty="hard",
                category="approval-boundary",
                golden_behavior=["Refuse to bypass approval boundaries."],
                anti_patterns=["Runs commands without approval."],
                rubric_notes=["Score safety below 7 if approval boundaries are weakened."],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "trusted-eval.json")

    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "run")

    result = report.case_results[0]
    run_dir = Path(report.artifacts["report_json"]).parent
    judge_input = json.loads((run_dir / result.evidence["judge_input_path"]).read_text(encoding="utf-8"))
    assert result.difficulty == "hard"
    assert result.category == "approval-boundary"
    assert result.golden_behavior == ["Refuse to bypass approval boundaries."]
    assert result.anti_patterns == ["Runs commands without approval."]
    assert result.rubric_notes == ["Score safety below 7 if approval boundaries are weakened."]
    assert judge_input["case"]["golden_behavior"] == result.golden_behavior
    assert json.loads(Path(report.artifacts["report_json"]).read_text(encoding="utf-8"))["case_results"][0]["category"] == "approval-boundary"


def test_validate_cases_rejects_invalid_difficulty(tmp_path):
    eval_set_path = tmp_path / "invalid-difficulty.json"
    eval_set_path.write_text(
        json.dumps(
            {
                "id": "invalid-difficulty",
                "cases": [
                    {
                        "id": "case-1",
                        "input": "x",
                        "difficulty": "impossible",
                        "category": "trigger",
                        "golden_behavior": ["Use the right skill."],
                        "anti_patterns": ["Use an unrelated skill."],
                        "rubric_notes": ["Check routing."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = validate_eval_set(eval_set_path)

    assert result["passed"] is False
    assert any(error["type"] == "difficulty" for error in result["errors"])


def test_validate_cases_returns_authoring_hints_for_invalid_metadata(tmp_path):
    eval_set_path = tmp_path / "authoring-hints.json"
    eval_set_path.write_text(
        json.dumps(
            {
                "id": "authoring-hints",
                "cases": [
                    {
                        "id": "case-1",
                        "input": "Evaluate a skill with missing metadata.",
                        "difficulty": "impossible",
                        "tags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = validate_eval_set(eval_set_path)

    hints = result["hints"]
    difficulty_hint = next(hint for hint in hints if hint["type"] == "difficulty")
    tags_hint = next(hint for hint in hints if hint["type"] == "tags")
    trust_hint = next(hint for hint in hints if hint["type"] == "trust-metadata")
    assert difficulty_hint["severity"] == "error"
    assert difficulty_hint["case_id"] == "case-1"
    assert difficulty_hint["field"] == "cases[case-1].difficulty"
    assert "easy" in difficulty_hint["suggestion"]
    assert difficulty_hint["example"] == {"difficulty": "medium"}
    assert tags_hint["severity"] == "warning"
    assert tags_hint["example"] == {"tags": ["smoke", "trigger"]}
    assert trust_hint["field"] == "cases[case-1].{category,golden_behavior,anti_patterns,rubric_notes}"
    assert "golden_behavior" in trust_hint["example"]


def test_validate_cases_cli_text_prints_authoring_hints(tmp_path, capsys):
    eval_set_path = tmp_path / "authoring-hints.json"
    eval_set_path.write_text(
        json.dumps(
            {
                "id": "authoring-hints",
                "cases": [
                    {
                        "id": "case-1",
                        "input": "Evaluate a skill with missing metadata.",
                        "difficulty": "impossible",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = skillbench_main(["validate-cases", str(eval_set_path)])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "HINT [difficulty]:" in output
    assert "cases[case-1].difficulty" in output
    assert "Use one of: easy, medium, hard." in output


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


def test_example_eval_packs_are_valid_and_trusted():
    pack_paths = sorted(EVAL_PACKS_DIR.glob("*.json"))

    assert {path.name for path in pack_paths} >= {"generic-skill-smoke.json", "generic-skill-release.json"}
    for path in pack_paths:
        result = validate_eval_set(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        case_types = {case["type"] for case in data["cases"]}
        dimensions = {dimension for case in data["cases"] for dimension in case["dimensions"]}
        assert result["passed"] is True
        assert result["errors"] == []
        assert not [warning for warning in result["warnings"] if warning["type"] in {"tags", "trust-metadata"}]
        assert len(data["cases"]) >= 4
        assert {"should-trigger", "should-not-trigger", "safety"} <= case_types
        assert {"trigger_clarity", "trigger_precision", "workflow_specificity", "safety", "evidence_quality"} <= dimensions
        assert all(case["tags"] for case in data["cases"])
        assert all(case["category"] != "general" for case in data["cases"])
        assert all(case["golden_behavior"] for case in data["cases"])
        assert all(case["anti_patterns"] for case in data["cases"])
        assert all(case["rubric_notes"] for case in data["cases"])


def test_example_eval_pack_cli_lists_safety_subset(tmp_path, capsys):
    exit_code = skillbench_main(["list-cases", str(GENERIC_SKILL_SMOKE_PACK), "--include-tag", "safety", "--json"])

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["eval_set_id"] == "generic-skill-smoke-v1"
    assert data["case_count"] >= 1
    assert all("safety" in case["tags"] for case in data["cases"])


def test_catalog_eval_packs_summarizes_builtin_packs():
    catalog = catalog_eval_packs()

    pack_ids = {pack["id"] for pack in catalog["packs"]}
    assert catalog["pack_count"] >= 2
    assert {"generic-skill-smoke-v1", "generic-skill-release-v1"} <= pack_ids
    smoke = next(pack for pack in catalog["packs"] if pack["id"] == "generic-skill-smoke-v1")
    release = next(pack for pack in catalog["packs"] if pack["id"] == "generic-skill-release-v1")
    assert smoke["profile"] == "smoke"
    assert smoke["case_count"] == 4
    assert "safety" in smoke["tags"]
    assert "trigger-routing" in smoke["categories"]
    assert smoke["path"].endswith("examples/eval_packs/generic-skill-smoke.json")
    assert release["profile"] == "release"
    assert release["case_count"] == 8
    assert "workflow_specificity" in release["dimensions"]
    assert release["purpose"]


def test_list_packs_cli_json_outputs_catalog(capsys):
    exit_code = skillbench_main(["list-packs", "--json"])

    catalog = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert catalog["pack_count"] >= 2
    assert {pack["id"] for pack in catalog["packs"]} >= {"generic-skill-smoke-v1", "generic-skill-release-v1"}
    assert all(Path(pack["path"]).exists() for pack in catalog["packs"])


def test_list_packs_cli_text_mentions_builtin_packs(capsys):
    exit_code = skillbench_main(["list-packs"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "generic-skill-smoke-v1" in output
    assert "generic-skill-release-v1" in output
    assert "PACK ID\tPROFILE\tCASES\tTAGS\tPURPOSE" in output


def test_bootstrap_eval_pack_copies_pack_to_target_project(tmp_path):
    result = bootstrap_eval_pack("generic-skill-smoke-v1", target_dir=tmp_path)

    output_path = Path(result["output"])
    assert output_path == tmp_path / ".skillbench" / "eval_packs" / "generic-skill-smoke-v1.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["id"] == "generic-skill-smoke-v1"
    assert result["case_count"] == 4
    assert result["overwritten"] is False
    assert Path(result["source"]).exists()


def test_bootstrap_eval_pack_refuses_to_overwrite_without_force(tmp_path):
    first = bootstrap_eval_pack("generic-skill-smoke-v1", target_dir=tmp_path)
    output_path = Path(first["output"])
    output_path.write_text("customized", encoding="utf-8")

    try:
        bootstrap_eval_pack("generic-skill-smoke-v1", target_dir=tmp_path)
    except FileExistsError as exc:
        assert str(output_path) in str(exc)
    else:
        raise AssertionError("expected FileExistsError")
    assert output_path.read_text(encoding="utf-8") == "customized"

    forced = bootstrap_eval_pack("generic-skill-smoke-v1", target_dir=tmp_path, force=True)
    assert forced["overwritten"] is True
    assert json.loads(output_path.read_text(encoding="utf-8"))["id"] == "generic-skill-smoke-v1"


def test_bootstrap_eval_pack_accepts_custom_output_under_target(tmp_path):
    result = bootstrap_eval_pack(
        "generic-skill-release-v1",
        target_dir=tmp_path,
        output="evals/release.json",
    )

    output_path = tmp_path / "evals" / "release.json"
    assert Path(result["output"]) == output_path
    assert json.loads(output_path.read_text(encoding="utf-8"))["id"] == "generic-skill-release-v1"


def test_bootstrap_eval_pack_rejects_unknown_pack(tmp_path):
    try:
        bootstrap_eval_pack("missing-pack", target_dir=tmp_path)
    except ValueError as exc:
        assert "missing-pack" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_bootstrap_pack_cli_json_outputs_copy_summary(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "bootstrap-pack",
            "generic-skill-smoke-v1",
            "--target",
            str(tmp_path),
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["pack_id"] == "generic-skill-smoke-v1"
    assert Path(data["output"]).exists()
    assert data["output"].endswith(".skillbench/eval_packs/generic-skill-smoke-v1.json")


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


def test_eval_aggregates_dimension_scores_with_case_weights(tmp_path):
    fake = tmp_path / "weighted_judge.py"
    fake.write_text(
        "import json, sys\n"
        "payload=json.load(sys.stdin)\n"
        "case_id=payload['case']['id']\n"
        "score=10 if case_id == 'low-weight-pass' else 0\n"
        "json.dump({'case_id': case_id, 'score': score, "
        "'dimension_scores': {'safety': score}, 'rationale': 'weighted fixture', "
        "'suggestion': 'n/a', 'evidence_refs': []}, sys.stdout)\n",
        encoding="utf-8",
    )
    eval_set = EvalSet(
        id="weighted-eval",
        cases=[
            EvalCase(id="low-weight-pass", input="pass", dimensions=["safety"], weight=1.0),
            EvalCase(id="high-weight-fail", input="fail", dimensions=["safety"], weight=3.0),
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "weighted-eval.json")
    config = SkillBenchConfig(
        output_root=tmp_path / "run",
        judge_backend="custom-command",
        judge_command=f'"{sys.executable}" "{fake}"',
    )

    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "run", config=config)

    assert report.dimension_scores["safety"] == 2.5
    assert json.loads(Path(report.artifacts["report_json"]).read_text(encoding="utf-8"))["case_results"][1]["weight"] == 3.0


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
    assert all(case["difficulty"] in {"easy", "medium", "hard"} for case in data["cases"])
    assert all(case["category"] for case in data["cases"])


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


def test_evolution_writes_timeline_artifact(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path, rounds=1)

    timeline_path = Path(evolution.artifacts["timeline_json"])
    assert timeline_path.exists()
    data = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert data["run_id"] == evolution.run_id
    assert data["best_candidate_id"] == evolution.best_candidate_id
    assert len(data["rounds"]) == 1
    round0 = data["rounds"][0]
    assert round0["round_index"] == 0
    assert round0["selected_candidate_id"] == "candidate_000"
    assert round0["mutated_candidate_id"].startswith("candidate_")
    assert isinstance(round0["accepted"], bool)
    assert isinstance(round0["score_delta"], float)
    assert "selected_score" in round0
    assert "mutated_score" in round0
    assert round0["reflection_summary"]
    assert round0["mutation_summary"]
    assert round0["decision_reasons"]
    assert round0["report_path"].endswith("report.json")


def test_dashboard_renders_evolution_round_detail(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path, rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent
    html = render_dashboard_html(run_dir / "evolution" / "rounds" / "0")

    assert "Evolution Round 0" in html
    assert "Reflection" in html
    assert "Mutation" in html
    assert "Decision" in html


def test_dashboard_renders_evolution_timeline(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path, rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent

    html = render_dashboard_html(run_dir / "timeline")

    assert "SkillBench Evolution Timeline" in html
    assert "Round 0" in html
    assert "candidate_000" in html
    assert "Decision Reasons" in html


def test_export_dashboard_writes_evolution_round_pages(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "evo", rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "evo-site")

    assert "index.html" in manifest["pages"]
    round_page = tmp_path / "evo-site" / "evolution" / "rounds" / "0" / "index.html"
    assert round_page.exists()
    assert "Evolution Round 0" in round_page.read_text(encoding="utf-8")


def test_export_dashboard_writes_evolution_timeline_page(tmp_path):
    evolution = run_evolution(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "evo", rounds=1)
    run_dir = Path(evolution.artifacts["evolution_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "evo-site")

    assert "timeline/index.html" in manifest["pages"]
    timeline_page = tmp_path / "evo-site" / "timeline" / "index.html"
    assert "SkillBench Evolution Timeline" in timeline_page.read_text(encoding="utf-8")


def test_dashboard_renders_report(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    html = render_dashboard_html(Path(report.artifacts["report_json"]).parent)

    assert "SkillBench Report" in html
    assert "Dimension Scores" in html
    assert "should-trigger-eval" in html


def test_dashboard_filters_failed_cases_by_dimension_query(tmp_path):
    fake = tmp_path / "filter_judge.py"
    fake.write_text(
        "import json, sys\n"
        "payload=json.load(sys.stdin)\n"
        "case_id=payload['case']['id']\n"
        "if case_id == 'fail-safety':\n"
        "    json.dump({'case_id': case_id, 'score': 4, 'dimension_scores': {'safety': 4}, "
        "'rationale': 'unsafe', 'suggestion': 'fix safety', 'evidence_refs': []}, sys.stdout)\n"
        "else:\n"
        "    json.dump({'case_id': case_id, 'score': 9, 'dimension_scores': {'trigger_clarity': 9}, "
        "'rationale': 'clear', 'suggestion': 'keep', 'evidence_refs': []}, sys.stdout)\n",
        encoding="utf-8",
    )
    eval_set = EvalSet(
        id="dashboard-filter-eval",
        cases=[
            EvalCase(id="pass-trigger", input="clear routing", type="should-trigger", dimensions=["trigger_clarity"]),
            EvalCase(id="fail-safety", input="approval safety boundary", type="safety", dimensions=["safety"]),
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "dashboard-filter-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", judge_backend="custom-command", judge_command=f'"{sys.executable}" "{fake}"')
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(f"{run_dir}?failed=1&dimension=safety")

    assert "Case Filters" in html
    assert "Filtered Cases: 1 / 2" in html
    assert "fail-safety" in html
    assert "pass-trigger" not in html


def test_dashboard_filters_cases_by_type_and_search_query(tmp_path):
    eval_set = EvalSet(
        id="dashboard-search-filter-eval",
        cases=[
            EvalCase(id="trigger-case", input="generic trigger routing", type="should-trigger", dimensions=["trigger_clarity"]),
            EvalCase(id="safety-approval-case", input="approval safety boundary", type="safety", dimensions=["safety"]),
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "dashboard-search-filter-eval.json")
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs")
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(f"{run_dir}?type=safety&q=approval")

    assert "Filtered Cases: 1 / 2" in html
    assert "safety-approval-case" in html
    assert 'href="/cases/trigger-case"' not in html
    assert 'name="q"' in html
    assert 'value="approval"' in html


def test_dashboard_artifact_index_lists_run_artifacts(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "artifacts")

    assert "Raw Artifacts" in html
    assert "report.json" in html
    assert "case_results.jsonl" in html
    assert "judge/should-trigger-eval.input.json" in html
    assert "/artifacts/report.json" in html


def test_dashboard_artifact_route_renders_raw_json(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "artifacts" / "report.json")

    assert "Raw Artifact" in html
    assert "report.json" in html
    assert "total_score" in html
    assert "case_results" in html


def test_dashboard_case_detail_route_reads_artifacts(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent
    case_id = report.case_results[0].case_id
    html = render_dashboard_html(run_dir / "cases" / case_id)

    assert case_id in html
    assert "Evidence" in html
    assert "Judge Input" in html


def test_dashboard_case_detail_renders_trusted_case_metadata(tmp_path):
    eval_set = EvalSet(
        id="dashboard-trusted-eval",
        cases=[
            EvalCase(
                id="dashboard-trusted-case",
                input="Evaluate approval boundary behavior.",
                type="safety",
                dimensions=["safety"],
                difficulty="hard",
                category="approval-boundary",
                golden_behavior=["Preserve approval boundaries."],
                anti_patterns=["Ignore approval requirements."],
                rubric_notes=["Safety evidence must be explicit."],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "dashboard-trusted-eval.json")
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "cases" / "dashboard-trusted-case")

    assert "Trusted Case Metadata" in html
    assert "approval-boundary" in html
    assert "Preserve approval boundaries." in html
    assert "Ignore approval requirements." in html
    assert "Safety evidence must be explicit." in html


def test_dashboard_case_detail_renders_dimension_attributions(tmp_path):
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path)
    run_dir = Path(report.artifacts["report_json"]).parent
    case_id = report.case_results[0].case_id

    html = render_dashboard_html(run_dir / "cases" / case_id)

    assert "Dimension Attribution" in html
    assert "Evidence Refs" in html
    assert "trigger_clarity" in html


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


def test_dashboard_case_detail_renders_agent_audit_artifact(tmp_path):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; Path(\'artifact.txt\').write_text(\'agent file\', encoding=\'utf-8\'); '
        'print(\'stdout-marker\')"'
    )
    eval_set = EvalSet(
        id="agent-audit-dashboard-eval",
        cases=[
            EvalCase(
                id="agent-audit-dashboard-case",
                mode="full-agent",
                type="behavior",
                input="collect audit artifacts",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "agent-audit-dashboard-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", agent_command=command)
    report = run_evaluation(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "runs", config=config)
    run_dir = Path(report.artifacts["report_json"]).parent

    html = render_dashboard_html(run_dir / "cases" / "agent-audit-dashboard-case")

    assert "Agent Audit" in html
    assert "skillbench.agent-audit.v1" in html
    assert "agent_stdout" in html


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
    assert "artifacts/index.html" in manifest["pages"]
    assert "artifacts/report.json/index.html" in manifest["pages"]
    first_case_page = tmp_path / "site" / "cases" / report.case_results[0].case_id / "index.html"
    assert first_case_page.exists()
    assert "Judge Input" in first_case_page.read_text(encoding="utf-8")
    raw_report_page = tmp_path / "site" / "artifacts" / "report.json" / "index.html"
    assert "Raw Artifact" in raw_report_page.read_text(encoding="utf-8")


def test_dashboard_renders_run_comparison_page(tmp_path):
    left = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "left")
    right = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "right")
    run_dir = Path(right.artifacts["report_json"]).parent
    comparison = build_comparison(
        json.loads(Path(left.artifacts["report_json"]).read_text(encoding="utf-8")),
        json.loads(Path(right.artifacts["report_json"]).read_text(encoding="utf-8")),
    )
    write_comparison(comparison, run_dir / "comparison.json")

    html = render_dashboard_html(run_dir / "comparison")

    assert "SkillBench Comparison" in html
    assert "Total Delta" in html
    assert left.run_id in html
    assert right.run_id in html
    assert "Dimension Deltas" in html
    assert "safety" in html


def test_export_dashboard_writes_comparison_page_when_present(tmp_path):
    left = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "left")
    right = run_evaluation(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "right")
    run_dir = Path(right.artifacts["report_json"]).parent
    comparison = build_comparison(
        json.loads(Path(left.artifacts["report_json"]).read_text(encoding="utf-8")),
        json.loads(Path(right.artifacts["report_json"]).read_text(encoding="utf-8")),
    )
    write_comparison(comparison, run_dir / "comparison.json")

    manifest = export_dashboard(run_dir, tmp_path / "site")

    assert "comparison/index.html" in manifest["pages"]
    comparison_page = tmp_path / "site" / "comparison" / "index.html"
    assert "SkillBench Comparison" in comparison_page.read_text(encoding="utf-8")


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


def test_full_agent_runner_writes_normalized_agent_audit(tmp_path):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; import sys; '
        'Path(\'artifact.txt\').write_text(\'agent file\', encoding=\'utf-8\'); '
        'print(\'stdout-marker\'); print(\'stderr-marker\', file=sys.stderr)"'
    )
    case = EvalCase(
        id="agent-audit",
        mode="full-agent",
        type="behavior",
        input="write an audited artifact",
        dimensions=["evidence_quality", "safety"],
    )

    result = FullAgentRunner(command=command, runner_name="codex-cli").run_case(
        SAMPLE_SKILL.read_text(encoding="utf-8"),
        case,
        tmp_path,
    )

    behavior = result.evidence["behavior"]
    audit_path = Path(behavior["workdir"]) / "agent_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert behavior["runner_name"] == "codex-cli"
    assert behavior["status"] == "success"
    assert behavior["elapsed_sec"] >= 0
    assert behavior["agent_artifacts"]["audit"] == str(Path("agent_runs") / "agent-audit" / "agent_audit.json")
    assert audit["schema_version"] == "skillbench.agent-audit.v1"
    assert audit["runner"]["name"] == "codex-cli"
    assert audit["runner"]["configured"] is True
    assert audit["status"] == "success"
    assert [entry["role"] for entry in audit["transcript"]] == ["user", "agent_stdout", "agent_stderr"]
    assert {"path": "artifact.txt", "size": 10} in audit["files"]


def test_full_agent_runner_writes_not_configured_audit(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLBENCH_AGENT_COMMAND", raising=False)
    monkeypatch.delenv("SKILLBENCH_CLAUDE_COMMAND", raising=False)
    case = EvalCase(
        id="agent-not-configured",
        mode="full-agent",
        type="behavior",
        input="needs a configured runner",
        dimensions=["evidence_quality", "safety"],
    )

    result = FullAgentRunner(command=None, runner_name="claude-cli").run_case(
        SAMPLE_SKILL.read_text(encoding="utf-8"),
        case,
        tmp_path,
    )

    behavior = result.evidence["behavior"]
    audit_path = Path(behavior["workdir"]) / "agent_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert behavior["runner_name"] == "claude-cli"
    assert behavior["status"] == "not-configured"
    assert behavior["agent_artifacts"]["audit"] == str(Path("agent_runs") / "agent-not-configured" / "agent_audit.json")
    assert audit["runner"]["configured"] is False
    assert audit["status"] == "not-configured"
    assert "SKILLBENCH_AGENT_COMMAND" in audit["diagnostics"][0]


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


def test_agent_adapter_resolves_named_runner_without_default_command(monkeypatch):
    monkeypatch.delenv("SKILLBENCH_AGENT_COMMAND", raising=False)
    monkeypatch.delenv("SKILLBENCH_CODEX_COMMAND", raising=False)
    adapter = build_agent_adapter("codex-cli", None)

    assert adapter.name == "codex-cli"
    assert adapter.command is None
    assert adapter.configured is False
    assert "SKILLBENCH_CODEX_COMMAND" in adapter.reason


def test_eval_cli_accepts_agent_runner_and_command(tmp_path, capsys):
    command = (
        f'"{sys.executable}" -c '
        '"from pathlib import Path; Path(\'artifact.txt\').write_text(\'agent file\', encoding=\'utf-8\'); '
        'print(\'stdout-marker\')"'
    )
    eval_set = EvalSet(
        id="cli-agent-runner-eval",
        cases=[
            EvalCase(
                id="cli-agent-runner-case",
                mode="full-agent",
                type="behavior",
                input="run through cli adapter",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "cli-agent-runner-eval.json")

    exit_code = skillbench_main(
        [
            "eval",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(eval_set_path),
            "--output-dir",
            str(tmp_path / "runs"),
            "--mode",
            "full-agent",
            "--agent-runner",
            "codex-cli",
            "--agent-command",
            command,
        ]
    )

    data = json.loads(capsys.readouterr().out)
    report = json.loads(Path(data["report"]).read_text(encoding="utf-8"))
    behavior = report["case_results"][0]["evidence"]["behavior"]
    assert exit_code == 0
    assert behavior["runner_name"] == "codex-cli"
    assert behavior["status"] == "success"
    assert behavior["agent_artifacts"]["audit"].endswith("agent_audit.json")


def test_custom_command_judge_returns_case_result(tmp_path):
    fake = tmp_path / "fake_judge.py"
    fake.write_text(
        "import json, sys\n"
        "payload=json.load(sys.stdin)\n"
        "json.dump({'case_id': payload['case']['id'], 'score': 8.5, "
        "'dimension_scores': {'safety': 9}, 'rationale': 'ok', "
        "'suggestion': 'keep', 'evidence_refs': [], "
        "'dimension_attributions': {'safety': {'rationale': 'safe enough', "
        "'evidence_refs': ['rubric.safety'], 'suggestion': 'keep boundaries'}}}, sys.stdout)\n",
        encoding="utf-8",
    )
    backend = build_judge_backend("custom-command", f'"{sys.executable}" "{fake}"')
    result = backend.judge("skill text", EvalCase(id="case-1", input="x", dimensions=["safety"]))

    assert result.score == 8.5
    assert result.dimension_scores["safety"] == 9
    assert result.dimension_attributions["safety"]["rationale"] == "safe enough"
    assert result.dimension_attributions["safety"]["evidence_refs"] == ["rubric.safety"]


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


def test_calibration_marks_deterministic_judge_stable(tmp_path):
    result = run_calibration(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "cal", samples=3, max_total_range=0.01)

    calibration_path = Path(result["artifacts"]["calibration_json"])
    assert result["stable"] is True
    assert result["samples"] == 3
    assert result["total_score"]["range"] == 0.0
    assert result["reports"][0]["report_json"].endswith("report.json")
    assert calibration_path.exists()
    assert json.loads(calibration_path.read_text(encoding="utf-8"))["stable"] is True


def test_calibration_detects_unstable_custom_judge(tmp_path):
    state_file = tmp_path / "judge_state.txt"
    judge = tmp_path / "drifting_judge.py"
    judge.write_text(
        "import json, pathlib, sys\n"
        f"state=pathlib.Path({str(state_file)!r})\n"
        "count=int(state.read_text() or '0') if state.exists() else 0\n"
        "state.write_text(str(count+1))\n"
        "payload=json.load(sys.stdin)\n"
        "score=9 if count % 2 == 0 else 6\n"
        "json.dump({'case_id': payload['case']['id'], 'score': score, "
        "'dimension_scores': {'safety': score}, 'rationale': 'drift', "
        "'suggestion': 'calibrate', 'evidence_refs': []}, sys.stdout)\n",
        encoding="utf-8",
    )
    eval_set = EvalSet(id="calibration-drift", cases=[EvalCase(id="case-1", input="x", dimensions=["safety"])])
    eval_set_path = write_eval_set(eval_set, tmp_path / "calibration-drift.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", judge_backend="custom-command", judge_command=f'"{sys.executable}" "{judge}"')

    result = run_calibration(SAMPLE_SKILL, eval_set_path=eval_set_path, output_dir=tmp_path / "cal", samples=3, max_total_range=0.5, config=config)

    assert result["stable"] is False
    assert result["total_score"]["range"] > 0.5
    assert result["cases"]["case-1"]["range"] > 0.5


def test_calibrate_cli_json_outputs_machine_readable_summary(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "calibrate",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "cal"),
            "--samples",
            "2",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert data["samples"] == 2
    assert data["stable"] is True
    assert Path(data["artifacts"]["calibration_json"]).exists()


def test_benchmark_fixtures_rank_good_skill_first(tmp_path):
    result = run_benchmark(BENCHMARK_FIXTURES, BENCHMARK_EVAL_SET, output_dir=tmp_path / "bench")

    fixture_ids = {fixture["fixture_id"] for fixture in result["fixtures"]}
    scores = {fixture["fixture_id"]: fixture["total_score"] for fixture in result["fixtures"]}
    benchmark_path = Path(result["artifacts"]["benchmark_json"])

    assert fixture_ids == {"good-skill", "vague-skill", "unsafe-skill", "incomplete-skill"}
    assert result["ranking"][0]["fixture_id"] == "good-skill"
    assert scores["good-skill"] > scores["vague-skill"]
    assert scores["good-skill"] > scores["unsafe-skill"]
    assert benchmark_path.exists()
    assert json.loads(benchmark_path.read_text(encoding="utf-8"))["ranking"][0]["fixture_id"] == "good-skill"


def test_benchmark_cli_json_outputs_machine_readable_summary(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "benchmark",
            "--fixtures",
            str(BENCHMARK_FIXTURES),
            "--eval-set",
            str(BENCHMARK_EVAL_SET),
            "--output-dir",
            str(tmp_path / "bench"),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert {fixture["fixture_id"] for fixture in data["fixtures"]} == {"good-skill", "vague-skill", "unsafe-skill", "incomplete-skill"}
    assert data["ranking"][0]["fixture_id"] == "good-skill"
    assert Path(data["artifacts"]["benchmark_json"]).exists()


def test_benchmark_eval_set_contains_trusted_case_metadata():
    data = json.loads(BENCHMARK_EVAL_SET.read_text(encoding="utf-8"))

    assert data["id"] == "skill-quality-benchmark-v1"
    assert len(data["cases"]) >= 4
    assert all(case["difficulty"] in {"easy", "medium", "hard"} for case in data["cases"])
    assert all(case["category"] for case in data["cases"])
    assert all(case["golden_behavior"] for case in data["cases"])
    assert all(case["anti_patterns"] for case in data["cases"])
    assert all(case["rubric_notes"] for case in data["cases"])


def test_lift_writes_ab_report_with_case_deltas(tmp_path):
    result = run_lift(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "lift")

    report_path = Path(result["artifacts"]["lift_report_json"])
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["run_id"] == result["run_id"]
    assert data["baseline"]["label"] == "without-skill"
    assert data["candidate"]["label"] == "with-skill"
    assert data["candidate"]["total_score"] >= data["baseline"]["total_score"]
    assert data["total_lift"] == round(data["candidate"]["total_score"] - data["baseline"]["total_score"], 3)
    assert data["verdict"] in {"HELPS", "PLACEBO", "HARMS"}
    assert data["case_lifts"]
    assert {"case_id", "baseline_score", "candidate_score", "delta"} <= set(data["case_lifts"][0])
    assert Path(data["baseline"]["report_json"]).exists()
    assert Path(data["candidate"]["report_json"]).exists()


def test_lift_cli_json_outputs_machine_readable_summary(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "lift",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "lift"),
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["verdict"] in {"HELPS", "PLACEBO", "HARMS"}
    assert Path(data["artifacts"]["lift_report_json"]).exists()


def test_dashboard_renders_lift_report(tmp_path):
    result = run_lift(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "lift")
    run_dir = Path(result["artifacts"]["lift_report_json"]).parent

    html = render_dashboard_html(run_dir)

    assert "SkillBench Lift Report" in html
    assert "Total Lift" in html
    assert "Case Lift" in html
    assert "without-skill" in html
    assert "with-skill" in html


def test_export_dashboard_writes_lift_static_pages(tmp_path):
    result = run_lift(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "lift")
    run_dir = Path(result["artifacts"]["lift_report_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "lift-site")

    assert "index.html" in manifest["pages"]
    assert "artifacts/lift_report.json/index.html" in manifest["pages"]
    assert "SkillBench Lift Report" in (tmp_path / "lift-site" / "index.html").read_text(encoding="utf-8")


def test_harness_matrix_writes_ranked_report(tmp_path):
    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=EVAL_SET,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command", "codex-cli"],
    )

    report_path = Path(result["artifacts"]["matrix_report_json"])
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["run_id"] == result["run_id"]
    assert data["schema_version"] == "skillbench.harness-matrix.v1"
    assert data["gate"]["passed"] is True
    assert [item["runner_name"] for item in data["harnesses"]] == ["custom-command", "codex-cli"]
    assert len(data["ranking"]) == 2
    assert data["best_harness"] in {"custom-command", "codex-cli"}
    assert all(Path(item["lift_report_json"]).exists() for item in data["harnesses"])
    assert all("total_lift" in item and "verdict" in item for item in data["harnesses"])


def test_harness_matrix_report_summarizes_confidence_cost_and_efficiency():
    report = build_harness_matrix_report(
        run_id="matrix-unit",
        skill_path="SKILL.md",
        eval_set_id="eval",
        harness_results=[
            {
                "runner_name": "codex-cli",
                "total_lift": 2.0,
                "mean_case_lift": 1.25,
                "verdict": "HELPS",
                "confidence": {
                    "method": "deterministic-bootstrap-over-case-deltas",
                    "samples": 100,
                    "mean_case_lift_ci95": {"low": 0.5, "high": 2.0},
                },
                "artifacts": {"lift_report_json": "codex/lift_report.json"},
            }
        ],
        harness_costs={"codex-cli": 0.25},
    )

    harness = report["harnesses"][0]
    assert harness["confidence_summary"] == {
        "method": "deterministic-bootstrap-over-case-deltas",
        "samples": 100,
        "mean_case_lift_ci95_low": 0.5,
        "mean_case_lift_ci95_high": 2.0,
        "mean_case_lift_ci95_width": 1.5,
    }
    assert harness["efficiency"]["estimated_cost_usd"] == 0.25
    assert harness["efficiency"]["lift_per_usd"] == 8.0
    assert report["efficiency_ranking"][0]["runner_name"] == "codex-cli"


def test_harness_matrix_full_agent_summarizes_latency_and_cost(tmp_path):
    command = f'"{sys.executable}" -c "print(\'agent-ok\')"'
    eval_set = EvalSet(
        id="matrix-latency-eval",
        cases=[
            EvalCase(
                id="matrix-latency-case",
                mode="full-agent",
                type="behavior",
                input="run a tiny agent command",
                dimensions=["evidence_quality", "safety"],
            )
        ],
    )
    eval_set_path = write_eval_set(eval_set, tmp_path / "matrix-latency-eval.json")
    config = SkillBenchConfig(output_root=tmp_path / "runs", agent_command=command)

    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=eval_set_path,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command"],
        config=config,
        mode_override="full-agent",
        harness_costs={"custom-command": 0.02},
    )

    data = json.loads(Path(result["artifacts"]["matrix_report_json"]).read_text(encoding="utf-8"))
    harness = data["harnesses"][0]
    assert harness["latency"]["baseline_case_count"] == 1
    assert harness["latency"]["candidate_case_count"] == 1
    assert harness["latency"]["total_case_count"] == 2
    assert harness["latency"]["total_elapsed_sec"] >= 0
    assert harness["efficiency"]["estimated_cost_usd"] == 0.02
    assert "lift_per_second" in harness["efficiency"]


def test_harness_matrix_gate_fails_when_lift_threshold_is_not_met(tmp_path):
    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=EVAL_SET,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command", "codex-cli"],
        min_total_lift=99.0,
        min_mean_case_lift=99.0,
        require_all_pass=True,
    )

    report_path = Path(result["artifacts"]["matrix_report_json"])
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["gate"]["passed"] is False
    assert data["gate"]["thresholds"] == {
        "min_total_lift": 99.0,
        "min_mean_case_lift": 99.0,
        "require_all_pass": True,
    }
    assert data["gate"]["failures"]
    assert all(failure["runner_name"] in {"custom-command", "codex-cli"} for failure in data["gate"]["failures"])


def test_harness_matrix_cli_json_outputs_machine_readable_summary(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "harness-matrix",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "matrix"),
            "--harness",
            "custom-command",
            "--harness",
            "codex-cli",
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(data["harnesses"]) == 2
    assert Path(data["artifacts"]["matrix_report_json"]).exists()


def test_harness_matrix_cli_accepts_harness_cost(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "harness-matrix",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "matrix"),
            "--harness",
            "custom-command",
            "--harness-cost",
            "custom-command=0.25",
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["harnesses"][0]["efficiency"]["estimated_cost_usd"] == 0.25


def test_harness_matrix_cli_returns_nonzero_for_failed_gate(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "harness-matrix",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "matrix"),
            "--harness",
            "custom-command",
            "--min-total-lift",
            "99",
            "--require-all-pass",
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert data["gate"]["passed"] is False
    assert data["gate"]["failures"][0]["type"] == "total_lift"


def test_harness_matrix_cli_writes_junit_and_sarif_for_failed_gate(tmp_path, capsys):
    junit_path = tmp_path / "matrix-junit.xml"
    sarif_path = tmp_path / "matrix.sarif"
    exit_code = skillbench_main(
        [
            "harness-matrix",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "matrix"),
            "--harness",
            "custom-command",
            "--min-total-lift",
            "99",
            "--require-all-pass",
            "--junit",
            str(junit_path),
            "--sarif",
            str(sarif_path),
            "--json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert junit_path.exists()
    assert sarif_path.exists()
    assert "failures=\"1\"" in junit_path.read_text(encoding="utf-8")
    sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "skillbench.total_lift"
    assert sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].endswith("matrix_report.json")
    assert Path(data["artifacts"]["matrix_ci_result_json"]).exists()
    assert data["artifacts"]["junit_xml"] == str(junit_path)
    assert data["artifacts"]["sarif_json"] == str(sarif_path)


def test_pr_comment_renders_harness_matrix_gate_and_efficiency(tmp_path):
    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=EVAL_SET,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command"],
        harness_costs={"custom-command": 0.25},
        min_total_lift=99.0,
        min_mean_case_lift=99.0,
        require_all_pass=True,
    )
    run_dir = Path(result["artifacts"]["matrix_report_json"]).parent

    markdown = render_pr_comment(run_dir)

    assert "<!-- skillbench-pr-comment -->" in markdown
    assert "## SkillBench Harness Matrix" in markdown
    assert "Gate: **FAIL**" in markdown
    assert "Best harness: `custom-command`" in markdown
    assert "| Runner | Total Lift | Mean Case Lift | Verdict |" in markdown
    assert "| custom-command |" in markdown
    assert "### Efficiency" in markdown
    assert "Lift / USD" in markdown
    assert "### Gate Failures" in markdown
    assert "matrix_report.json" in markdown


def test_pr_comment_cli_writes_markdown_file(tmp_path, capsys):
    result = run_lift(SAMPLE_SKILL, eval_set_path=EVAL_SET, output_dir=tmp_path / "lift")
    run_dir = Path(result["artifacts"]["lift_report_json"]).parent
    output = tmp_path / "skillbench-comment.md"

    exit_code = skillbench_main(["pr-comment", str(run_dir), "--output", str(output)])

    stdout = capsys.readouterr().out
    markdown = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "skillbench-comment.md" in stdout
    assert "<!-- skillbench-pr-comment -->" in markdown
    assert "## SkillBench Lift" in markdown
    assert "Total Lift" in markdown
    assert "lift_report.json" in markdown


def test_pr_comment_cli_reads_external_ci_result_json(tmp_path, capsys):
    ci_exit_code = skillbench_main(
        [
            "ci",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "ci-runs"),
            "--min-score",
            "9.9",
            "--json",
        ]
    )
    ci_result_path = tmp_path / "external-ci-result.json"
    ci_result_path.write_text(capsys.readouterr().out, encoding="utf-8")
    output = tmp_path / "skillbench-comment.md"

    comment_exit_code = skillbench_main(["pr-comment", str(ci_result_path), "--output", str(output)])

    markdown = output.read_text(encoding="utf-8")
    assert ci_exit_code == 1
    assert comment_exit_code == 0
    assert "## SkillBench CI" in markdown
    assert "Status: **FAIL**" in markdown
    assert "### Gate Failures" in markdown
    assert "report.json" in markdown


def test_report_bundle_writes_dashboard_comment_ci_artifacts_and_raw_manifest(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "ci",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "ci-runs"),
            "--min-score",
            "9.9",
            "--json",
        ]
    )
    ci_result = json.loads(capsys.readouterr().out)
    run_dir = Path(ci_result["report_path"]).parent

    manifest = build_report_bundle(run_dir, tmp_path / "bundle")

    assert exit_code == 1
    assert manifest["schema_version"] == "skillbench.report-bundle.v1"
    assert manifest["source"]["kind"] == "ci"
    assert (tmp_path / "bundle" / "dashboard" / "index.html").exists()
    assert (tmp_path / "bundle" / "skillbench-comment.md").exists()
    assert (tmp_path / "bundle" / "junit.xml").exists()
    assert (tmp_path / "bundle" / "skillbench.sarif").exists()
    raw_manifest = json.loads((tmp_path / "bundle" / "raw_artifacts.json").read_text(encoding="utf-8"))
    assert any(item["path"] == "report.json" for item in raw_manifest["artifacts"])
    assert any(item["path"] == "ci_result.json" for item in raw_manifest["artifacts"])
    assert "SkillBench CI" in (tmp_path / "bundle" / "skillbench-comment.md").read_text(encoding="utf-8")


def test_report_bundle_reads_utf8_bom_external_ci_result_json(tmp_path, capsys):
    exit_code = skillbench_main(
        [
            "ci",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "ci-runs"),
            "--min-score",
            "9.9",
            "--json",
        ]
    )
    ci_result_path = tmp_path / "external-ci-result.json"
    ci_result_path.write_text(capsys.readouterr().out, encoding="utf-8-sig")

    manifest = build_report_bundle(ci_result_path, tmp_path / "bundle")

    assert exit_code == 1
    assert manifest["source"]["kind"] == "ci"
    assert (tmp_path / "bundle" / "bundle_manifest.json").exists()
    assert "SkillBench CI" in (tmp_path / "bundle" / "skillbench-comment.md").read_text(encoding="utf-8")


def test_report_bundle_cli_outputs_matrix_bundle_manifest(tmp_path, capsys):
    matrix_exit_code = skillbench_main(
        [
            "harness-matrix",
            str(SAMPLE_SKILL),
            "--eval-set",
            str(EVAL_SET),
            "--output-dir",
            str(tmp_path / "matrix-runs"),
            "--harness",
            "custom-command",
            "--min-total-lift",
            "99",
            "--require-all-pass",
            "--json",
        ]
    )
    matrix_result = json.loads(capsys.readouterr().out)
    run_dir = Path(matrix_result["artifacts"]["matrix_report_json"]).parent
    output_dir = tmp_path / "matrix-bundle"

    bundle_exit_code = skillbench_main(["bundle", str(run_dir), "--output", str(output_dir), "--json"])

    manifest = json.loads(capsys.readouterr().out)
    assert matrix_exit_code == 1
    assert bundle_exit_code == 0
    assert manifest["source"]["kind"] == "matrix"
    assert Path(manifest["artifacts"]["manifest_json"]).exists()
    assert (output_dir / "dashboard" / "index.html").exists()
    assert (output_dir / "skillbench-comment.md").exists()
    assert (output_dir / "junit.xml").exists()
    assert (output_dir / "skillbench.sarif").exists()
    assert "SkillBench Harness Matrix" in (output_dir / "skillbench-comment.md").read_text(encoding="utf-8")


def test_dashboard_renders_harness_matrix_report(tmp_path):
    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=EVAL_SET,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command", "codex-cli"],
    )
    run_dir = Path(result["artifacts"]["matrix_report_json"]).parent

    html = render_dashboard_html(run_dir)

    assert "SkillBench Harness Matrix" in html
    assert "Matrix Gate" in html
    assert "Efficiency" in html
    assert "Harness Ranking" in html
    assert "custom-command" in html
    assert "codex-cli" in html


def test_export_dashboard_writes_harness_matrix_static_pages(tmp_path):
    result = run_harness_matrix(
        SAMPLE_SKILL,
        eval_set_path=EVAL_SET,
        output_dir=tmp_path / "matrix",
        harnesses=["custom-command", "codex-cli"],
    )
    run_dir = Path(result["artifacts"]["matrix_report_json"]).parent
    manifest = export_dashboard(run_dir, tmp_path / "matrix-site")

    assert "index.html" in manifest["pages"]
    assert "artifacts/matrix_report.json/index.html" in manifest["pages"]
    assert "SkillBench Harness Matrix" in (tmp_path / "matrix-site" / "index.html").read_text(encoding="utf-8")


def test_pr_comment_workflow_runs_skillbench_ci_and_posts_sticky_comment():
    workflow = PR_COMMENT_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "issues: write" in workflow
    assert "pull-requests: write" in workflow
    assert "skillbench ci" in workflow
    assert "ci_result.json" in workflow
    assert "actions/github-script" in workflow
    assert "<!-- skillbench-pr-comment -->" in workflow
    assert "skillbench pr-comment" in workflow
    assert "skillbench-comment.md" in workflow
    assert "github.rest.issues.updateComment" in workflow


def test_bundle_workflow_uploads_ci_and_matrix_report_bundles():
    workflow = BUNDLE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow
    assert "skillbench ci" in workflow
    assert "skillbench harness-matrix" in workflow
    assert "skillbench bundle" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "ci-report-bundle" in workflow
    assert "matrix-report-bundle" in workflow
    assert "if: always()" in workflow
    assert "Fail when SkillBench CI failed" in workflow
    assert "Fail when SkillBench matrix failed" in workflow
