from __future__ import annotations

from app.database import EvalCase
from app.rag import answer_question


def run_eval_case(case: EvalCase, top_k: int = 5) -> dict:
    try:
        result = answer_question(
            question=case.question,
            namespace=case.namespace,
            category=case.category or None,
            top_k=top_k,
        )
    except Exception as exc:
        return {
            "case": case,
            "passed": False,
            "error": str(exc),
            "answer": "",
            "matches": [],
            "source_found": False,
            "terms_found": [],
            "terms_missing": [],
        }

    matches = result["matches"]
    answer = result["answer"]

    expected_source = case.expected_source.lower()
    source_found = any(
        expected_source in (m["metadata"].get("source_file", "") or "").lower()
        or expected_source in (m["metadata"].get("title", "") or "").lower()
        for m in matches
    )

    expected_terms = [t for t in (case.expected_terms or "").splitlines() if t.strip()]
    answer_lower = answer.lower()
    terms_found = [t for t in expected_terms if t.strip().lower() in answer_lower]
    terms_missing = [t for t in expected_terms if t.strip().lower() not in answer_lower]

    passed = source_found and (not expected_terms or not terms_missing)

    return {
        "case": case,
        "passed": passed,
        "error": None,
        "answer": answer,
        "matches": matches,
        "source_found": source_found,
        "terms_found": terms_found,
        "terms_missing": terms_missing,
    }
