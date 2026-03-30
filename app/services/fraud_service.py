from app.services.llm_service import GeminiServiceError, generate_text, parse_json_response
from app.services.rag_service import retrieve_context


def _normalize_text(value, default=""):
    if value is None:
        return default
    return str(value).strip() or default


def _normalize_risk_level(value):
    normalized = _normalize_text(value, "Medium").lower()

    if normalized == "high":
        return "High"
    if normalized == "low":
        return "Low"
    return "Medium"


def _normalize_list(value):
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items[:5]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _excerpt(text, limit=420):
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _build_prompt(query, ranked_chunks):
    formatted_chunks = []

    for index, chunk in enumerate(ranked_chunks, start=1):
        formatted_chunks.append(
            (
                f"[Chunk {index} | Source: {chunk['file_name']} | Similarity: {chunk['score']:.3f}]\n"
                f"{chunk['text']}"
            )
        )

    joined_context = "\n\n".join(formatted_chunks)

    return f"""
You are an SBI fraud investigation assistant.
Use only the retrieved SOP context below. Do not use outside knowledge.

If the retrieved SOP context is not relevant enough to answer the user query, respond with JSON where:
- "supported" is false
- "reason" briefly explains why

If the context is relevant, respond with JSON only using this schema:
{{
  "supported": true,
  "fraud_category": "short category code or Unknown",
  "fraud_classification": "short classification",
  "risk_level": "Low | Medium | High",
  "suspicious_indicators": ["2 to 5 short items"],
  "relevant_information": "short grounded explanation",
  "recommended_action": "clear SOP-grounded next step",
  "sop_summary": "2 to 4 sentence answer grounded in the retrieved SOP context",
  "reason": ""
}}

User query:
{query}

Retrieved SOP context:
{joined_context}
""".strip()


def _fallback_analysis(raw_response, reference_files, context):
    relevant_excerpt = _excerpt(context)

    return {
        "supported": True,
        "fraud_category": "Unknown",
        "fraud_classification": "Manual review required",
        "risk_level": "Medium",
        "suspicious_indicators": [],
        "relevant_information": relevant_excerpt,
        "recommended_action": "Review the retrieved SOP context manually and continue with investigator validation.",
        "sop_summary": _normalize_text(raw_response, relevant_excerpt),
        "reason": "",
        "references": reference_files,
    }


def detect_fraud(query, bank_id):
    try:
        context, reference_files, ranked_chunks = retrieve_context(query, bank_id)
    except GeminiServiceError as exc:
        return {
            "supported": False,
            "reason": str(exc),
        }

    if not context.strip():
        return {
            "supported": False,
            "reason": "No relevant SOP context was retrieved for this query yet.",
        }

    prompt = _build_prompt(query, ranked_chunks)

    try:
        raw_response = generate_text(prompt)
    except GeminiServiceError as exc:
        return {
            "supported": False,
            "reason": str(exc),
        }

    try:
        parsed = parse_json_response(raw_response)
    except Exception:
        return _fallback_analysis(raw_response, reference_files, context)

    supported = bool(parsed.get("supported", True))

    analysis = {
        "supported": supported,
        "fraud_category": _normalize_text(parsed.get("fraud_category"), "Unknown"),
        "fraud_classification": _normalize_text(parsed.get("fraud_classification"), "Manual review required"),
        "risk_level": _normalize_risk_level(parsed.get("risk_level")),
        "suspicious_indicators": _normalize_list(parsed.get("suspicious_indicators")),
        "relevant_information": _normalize_text(parsed.get("relevant_information"), _excerpt(context)),
        "recommended_action": _normalize_text(
            parsed.get("recommended_action"),
            "Review the retrieved SOP context and continue with investigator validation.",
        ),
        "sop_summary": _normalize_text(parsed.get("sop_summary"), _excerpt(context)),
        "reason": _normalize_text(parsed.get("reason")),
        "references": reference_files,
    }

    if not analysis["supported"] and not analysis["reason"]:
        analysis["reason"] = "The retrieved SOP context does not clearly cover this query."

    return analysis
