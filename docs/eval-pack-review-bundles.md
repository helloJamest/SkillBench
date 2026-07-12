# Eval Pack Review Bundles

`eval-pack-review-bundle` is the uploadable evidence package produced by the example eval pack review workflow. It is designed for pull requests that change reusable eval packs, where reviewers need one place to inspect validation status, coverage drift, gate failures, rendered comments, and raw machine-readable artifacts.

## Build In CI

The bundled workflow in `.github/workflows/skillbench-pack-checklists.yml` already builds and uploads this artifact:

```bash
skillbench bundle .skillbench/pack-checklists \
  --output .skillbench/pack-review-bundle \
  --json | tee .skillbench/pack-review-bundle-manifest.json
```

The workflow uploads two complementary artifacts:

- `eval-pack-checklists`: raw checklist, validation, comparison, JUnit, SARIF, and pack review CI files.
- `eval-pack-review-bundle`: a reviewer-friendly package with dashboard HTML, PR comment Markdown, copied raw artifacts, and generated CI formats.

## Download From GitHub Actions

Use the GitHub UI artifact download button, or add a follow-up job with `actions/download-artifact`:

```yaml
- name: Download eval pack review bundle
  uses: actions/download-artifact@v4
  with:
    name: eval-pack-review-bundle
    path: downloaded/eval-pack-review-bundle
```

Open `downloaded/eval-pack-review-bundle/dashboard/index.html` in a browser to review the same evidence without running a local server.

## Bundle Layout

An eval pack review bundle contains:

- `dashboard/index.html`: visual summary for validation status, coverage drift, policy sources, and gate failures.
- `dashboard/artifacts/index.html`: browsable raw artifact index.
- `skillbench-comment.md`: reusable PR summary text rendered from the same evidence.
- `junit.xml`: CI test-style failures for eval pack validation and coverage drift gates.
- `skillbench.sarif`: code scanning compatible findings for failed gates.
- `raw/`: copied source artifacts from the review directory.
- `raw_artifacts.json`: manifest of copied raw artifacts and bundle-relative paths.
- `bundle_manifest.json`: top-level manifest with source kind, dashboard pages, raw artifact counts, and generated artifact paths.

The most important raw file is `raw/pack_review_ci_result.json`. It records the overall pass/fail status, validation artifacts, comparison artifacts, failures, and the original `pack_review_ci_result.json` path.

## Review Workflow

Start with `dashboard/index.html`. If the status is `FAIL`, inspect the `Gate Failures` table first. Each row points back to the relevant validation or comparison artifact.

For schema or authoring issues, open the linked `*.validation.json` file and check `errors`, `warnings`, and `hints`.

For coverage drift issues, open the linked `*comparison.json` file and inspect:

- `case_delta`
- `coverage_delta`
- `gate.policy_sources`
- `gate.violations`

Policy sources explain whether the gate came from right-hand eval pack metadata, a policy JSON file, or CLI flags. Violations explain which dimensions, tags, categories, types, or modes were removed.

## Local Reproduction

To reproduce the CI evidence locally:

```bash
skillbench pack-review-smoke examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json \
  --review-dir .skillbench/pack-review-smoke \
  --bundle-output .skillbench/pack-review-bundle \
  --clean
```

The smoke command prints a compact summary with validation and comparison counts, top gate failures, and artifact hints for the dashboard, raw manifest, and pack review CI result. Its `--json` output is documented by `docs/schemas/pack-review-smoke-result.schema.json`. Use `--clean` for repeated local runs so stale validation, comparison, JUnit, SARIF, or dashboard files do not survive from earlier smoke checks. The command above is equivalent to the expanded workflow below:

For a copyable GitHub Actions example that validates the smoke JSON against that schema and uploads the generated bundle, see `.github/workflows/skillbench-pack-review-smoke.yml`.

```bash
mkdir -p .skillbench/pack-checklists
skillbench validate-cases examples/eval_packs/generic-skill-smoke.json \
  --json > .skillbench/pack-checklists/generic-skill-smoke.validation.json
skillbench pack-compare examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json \
  --json > .skillbench/pack-checklists/generic-skill-smoke-to-release-comparison.json
skillbench pack-review-artifacts .skillbench/pack-checklists \
  --junit .skillbench/pack-checklists/pack-review-junit.xml \
  --sarif .skillbench/pack-checklists/pack-review.sarif
skillbench bundle .skillbench/pack-checklists \
  --output .skillbench/pack-review-bundle
```

Then open `.skillbench/pack-review-bundle/dashboard/index.html`.
