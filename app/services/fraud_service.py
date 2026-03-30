from app.services.rag_service import retrieve_context
import re


def detect_fraud(query, bank_id):

    context, reference_files = retrieve_context(query, bank_id)

    fraud_category = ""
    fraud_classification = ""
    suspicious_indicators = []
    relevant_text = ""
    risk_level = "Low"

    # -------------------------
    # Fraud Category Detection
    # -------------------------
    category_match = re.search(r'([A-Z]{1,3}-\d{2})', context)

    if category_match:
        fraud_category = category_match.group(1)

    # -------------------------
    # Fraud Classification
    # -------------------------
    classification_match = re.search(r'[A-Z]{1,3}-\d{2}\s+([A-Za-z /&-]+)', context)

    if classification_match:
        fraud_classification = classification_match.group(1).strip()

    # -------------------------
    # Extract Relevant Line
    # -------------------------
    lines = context.split("\n")

    for line in lines:

        if query.lower() in line.lower():

            relevant_text = line.strip()
            break

        if fraud_category and fraud_category in line:

            relevant_text = line.strip()

    # -------------------------
    # Risk Level
    # -------------------------
    query_lower = query.lower()

    if any(word in query_lower for word in [
        "forged", "fake", "fraud", "phishing",
        "deepfake", "unauthorized", "kyc"
    ]):
        risk_level = "High"

    elif any(word in query_lower for word in [
        "review", "verify", "check"
    ]):
        risk_level = "Medium"

    # -------------------------
    # Suspicious Indicators
    # -------------------------
    indicators = re.findall(
        r'([A-Za-z ]+(?:logs|records|report|documents))',
        context
    )

    if indicators:
        suspicious_indicators = list(set(indicators[:4]))

    # -------------------------
    # Recommended Action
    # -------------------------
    if fraud_category:

        recommended_action = (
            f"Investigate case under fraud category {fraud_category}. "
            "Collect KYC documents, CCTV footage, system logs and follow SOP procedure."
        )

    else:

        recommended_action = (
            "Review SOP guidelines and verify KYC documents."
        )

    analysis = {
        "fraud_category": fraud_category,
        "fraud_classification": fraud_classification,
        "risk_level": risk_level,
        "suspicious_indicators": suspicious_indicators,
        "relevant_information": relevant_text,
        "recommended_action": recommended_action
    }

    return analysis
