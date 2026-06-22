from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ..observability.logging_io import ensure_dir


def build_junit_xml(ci_result: dict[str, Any]) -> str:
    failures = ci_result.get("failures", [])
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": "skillbench-ci",
            "tests": str(max(1, len(failures))),
            "failures": str(len(failures)),
        },
    )
    if failures:
        for index, failure in enumerate(failures, start=1):
            case = ElementTree.SubElement(
                suite,
                "testcase",
                {
                    "classname": "skillbench.ci",
                    "name": f"{failure.get('type', 'failure')}-{index}",
                },
            )
            failure_node = ElementTree.SubElement(case, "failure", {"message": str(failure.get("message", ""))})
            failure_node.text = str(failure)
    else:
        ElementTree.SubElement(suite, "testcase", {"classname": "skillbench.ci", "name": "thresholds"})
    return ElementTree.tostring(suite, encoding="unicode")


def write_junit_xml(ci_result: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(build_junit_xml(ci_result) + "\n", encoding="utf-8")
    return target

