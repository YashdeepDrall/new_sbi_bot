from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import BASE_DIR, BANKS_DIR, SBI_BANK_ID, SBI_BANK_NAME
from app.db.mongodb import chat_logs_collection, documents_collection, cases_collection, fs
from app.ml.vector_store import generate_embedding, search_vector
from app.services.auth_service import verify_user, verify_user_credentials
from app.services.fraud_service import detect_fraud
import datetime
import uuid
from bson import ObjectId
import os
import re

router = APIRouter()

# ------------------------------
# Chat Utilities
# ------------------------------

def get_last_chat(userId, session_id):
    last_chat = chat_logs_collection.find_one(
        {"userId": userId, "sessionId": session_id},
        sort=[("timestamp", -1)]
    )
    return last_chat


def save_chat_log(userId, bank_id, session_id, user_input, bot_output, step, analysis, case_query):
    chat_logs_collection.insert_one({
        "userId": userId,
        "bankId": bank_id,
        "sessionId": session_id,
        "user_input": user_input,
        "bot_output": bot_output,
        "step": step,
        "analysis": analysis,
        "case_query": case_query,
        "timestamp": datetime.datetime.utcnow()
    })


# ------------------------------
# SOP Analysis
# ------------------------------

def get_top_sop_match(query, bank_id):
    query_emb = generate_embedding(query)
    top_docs = search_vector(query_emb, bank_id, top_k=1)

    if not top_docs:
        return None, None

    top_doc = top_docs[0]

    similarity = None
    doc = None

    if isinstance(top_doc, tuple) and len(top_doc) == 2:
        similarity, doc = top_doc
    elif isinstance(top_doc, dict):
        doc = top_doc

    if not isinstance(doc, dict):
        return None, None

    return similarity, doc


def is_relevant_sop_match(query, similarity, doc):
    if not isinstance(doc, dict):
        return False

    query_terms = re.findall(r"[a-zA-Z]{3,}", query.lower())
    stop_words = {
        "the", "and", "for", "with", "this", "that", "clear", "hello",
        "help", "please", "need", "want", "case", "details", "anything"
    }
    query_terms = [term for term in query_terms if term not in stop_words]

    if not query_terms:
        return False

    doc_text = f"{doc.get('text', '')} {doc.get('fileName', '')}".lower()
    term_overlap = any(term in doc_text for term in query_terms)

    if term_overlap:
        return True

    if isinstance(similarity, (int, float)) and similarity >= 0.5:
        return True

    return False


def sop_based_analysis(query, bank_id):
    similarity, doc = get_top_sop_match(query, bank_id)

    if not is_relevant_sop_match(query, similarity, doc):
        return None

    text = doc.get("text", "").strip()
    file_name = doc.get("fileName", "").strip()

    header = "SOP Analysis:"
    source_line = ""

    if file_name:
        if isinstance(similarity, (int, float)):
            source_line = f"Source: {file_name} (score: {similarity:.3f})"
        else:
            source_line = f"Source: {file_name}"

    if text:
        lines = [ln.rstrip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln.strip() not in {"|", "I"}]
        text = " ".join(lines)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace(" â— ", "\nâ— ")
        text = re.sub(r"\.\s+", ".\n", text)
        text = re.sub(r"\n\d+\.\s*\n?", "\n", text)
        text = re.sub(r"\s+\.", ".", text)
        text = re.sub(r"\s+\)", ")", text)
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+,", ",", text)
        text = re.sub(r"\s+:", ":", text)
        text = re.sub(r"(?i)\bAUTOMATED ANNEXURE(S)?\b.*$", "", text).strip()
        text = re.sub(r"\nâ— ", "\n\nâ— ", text).strip()
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        filtered = []
        for ln in lines:
            lower_ln = ln.lower()
            stripped = lower_ln.strip("â— ").strip()
            if stripped in {"automated annexure", "automated annexures", "for"}:
                continue
            if stripped.startswith("automated annexure"):
                continue
            if stripped == "for" or stripped.startswith("for "):
                continue
            filtered.append(ln)
        text = "\n".join(filtered).strip()

        text = re.sub(r"\n(?=Phase \d+:)", "\n\n", text)
        text = re.sub(r"\n(?=ESCALATION & AUTHORITY LEVELS)", "\n\n", text)

    if source_line and text:
        return f"{header}\n{text}"
    if text:
        return f"{header}\n{text}"
    return None


def format_analysis(analysis):
    if not isinstance(analysis, dict):
        return str(analysis)

    fraud_category = analysis.get("fraud_category", "N/A")
    fraud_classification = analysis.get("fraud_classification", "N/A")
    risk_level = analysis.get("risk_level", "N/A")
    suspicious_indicators = analysis.get("suspicious_indicators", [])
    relevant_information = analysis.get("relevant_information", "N/A")
    recommended_action = analysis.get("recommended_action", "N/A")

    indicators_text = ", ".join(s.strip() for s in suspicious_indicators if s.strip()) or "N/A"

    return (
        "Fraud Detection Result:\n"
        f"- Fraud Category: {fraud_category}\n"
        f"- Fraud Classification: {fraud_classification}\n"
        f"- Risk Level: {risk_level}\n"
        f"- Suspicious Indicators: {indicators_text}\n"
        f"- Relevant Information: {relevant_information}\n"
        f"- Recommended Action: {recommended_action}"
    )


# ------------------------------
# Documents
# ------------------------------

def fetch_relevant_documents(bank_id):
    if bank_id != SBI_BANK_ID:
        return []

    docs = list(documents_collection.find({
        "bankId": bank_id,
        "$or": [
            {"filePath": {"$exists": True}},
            {"isPDF": True},
            {"documentType": "SOP"}
        ]
    }))

    results = []

    for doc in docs:
        file_name = doc.get("fileName", "")
        file_path = doc.get("filePath", "")
        file_id = doc.get("fileId", "")

        # Normalize existing file path to absolute
        if file_path and not os.path.isabs(file_path):
            file_path = os.path.abspath(os.path.join(BASE_DIR, file_path))

        # Backfill file path from local banks folder
        if not file_path and file_name:
            candidate_path = os.path.join(BANKS_DIR, bank_id, file_name)
            if os.path.exists(candidate_path):
                file_path = candidate_path

        # Backfill fileId from GridFS
        if not file_id and file_name:
            grid_file = fs.find_one({"filename": file_name, "bankId": bank_id})
            if grid_file:
                file_id = str(grid_file._id)

        results.append({
            "name": file_name,
            "path": file_path,
            "fileId": file_id
        })

    return results


@router.get("/documents/{file_id}")
def download_document(file_id: str):
    try:
        grid_out = fs.get(ObjectId(file_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = grid_out.filename or "document.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(grid_out, media_type="application/pdf", headers=headers)


# ------------------------------
# Historical Cases
# ------------------------------

def fetch_historical_docs():

    docs = list(cases_collection.find({}))

    return [
        {
            "name": doc.get("fileName"),
            "path": doc.get("filePath", "")
        }
        for doc in docs
    ]


# ------------------------------
# Fraud Chat API
# ------------------------------

@router.get("/fraud")
def fraud_chat(userId: str, query: str, sessionId: str | None = None):

    bank_id = verify_user(userId)

    if not sessionId:
        sessionId = f"{userId}_{uuid.uuid4().hex}"

    last_chat = get_last_chat(userId, sessionId)
    step = last_chat["step"] if last_chat else None
    response = ""
    next_step = None
    analysis = last_chat.get("analysis") if last_chat else None
    case_query = last_chat.get("case_query") if last_chat else None
    documents = []

    yes_set = {"yes", "y", "yeah", "yep", "sure", "ok", "okay"}
    no_set = {"no", "n", "nope", "nah", "nothing"}

    def normalize_choice(text):
        text = (text or "").strip().lower()
        if not text:
            return None
        head = text.split()[0]
        if head in yes_set:
            return "yes"
        if head in no_set:
            return "no"
        return None

    choice = normalize_choice(query)

    followup_steps = {"fetch_documentation", "generate_report", "historical_docs", "final_assistance"}

    # If the user types a new case during a follow-up step, restart flow.
    if step in followup_steps and choice is None:
        step = None
        analysis = None
        case_query = None


    # ------------------------------
    # STEP 1 â†’ New Fraud Analysis
    # ------------------------------

    if not step or step == "conversation_end":

        sop_analysis = sop_based_analysis(query, bank_id)

        if not sop_analysis:
            response = (
                f"The content you asked for is not available in the {SBI_BANK_NAME} SOP. "
                "Please ask a relevant fraud-related query."
            )
            next_step = "conversation_end"
            analysis = {}
            case_query = None
        else:
            analysis = detect_fraud(query, bank_id)
            case_query = query

            analysis_text = format_analysis(analysis)

            response = f"""
{analysis_text}

{sop_analysis}

Do you want the relevant documentation for this fraud case? (Yes/No)
"""

            next_step = "fetch_documentation"


    # ------------------------------
    # STEP 2 â†’ Documents
    # ------------------------------

    elif step == "fetch_documentation":

        if choice == "yes":

            docs = fetch_relevant_documents(bank_id)
            documents = docs

            doc_names = ", ".join([d.get("name", "Document") for d in docs]) or "None found"

            response = f"""
Relevant SOP Documents:

{doc_names}

Do you want an automated investigation report generated? (Yes/No)
"""

            next_step = "generate_report"

        elif choice == "no":

            response = """
Skipping documents.

Do you want an automated investigation report generated? (Yes/No)
"""
            next_step = "generate_report"
        else:
            response = """
I did not get a clear Yes/No. Please reply Yes or No.
"""
            next_step = "fetch_documentation"


    # ------------------------------
    # STEP 3 â†’ Report
    # ------------------------------

    elif step == "generate_report":

        if choice == "yes":

            report = f"""
AUTOMATED FRAUD REPORT

Case Query:
{case_query or ""}

Fraud Analysis:
{format_analysis(analysis)}
"""

            response = f"""
Generated Investigation Report:

{report}

Do you want historical fraud case references? (Yes/No)
"""
            next_step = "historical_docs"

        elif choice == "no":

            response = """
Skipping report generation.

Do you want historical fraud case references? (Yes/No)
"""
            next_step = "historical_docs"
        else:
            response = """
I did not get a clear Yes/No. Please reply Yes or No.
"""
            next_step = "generate_report"


    # ------------------------------
    # STEP 4 â†’ Historical Docs
    # ------------------------------

    elif step == "historical_docs":

        if choice == "yes":

            hist_docs = fetch_historical_docs()

            response = f"""
Historical Fraud Case References:

{hist_docs}

Is there anything else I can help you with?
"""
            next_step = "final_assistance"

        elif choice == "no":

            response = """
Skipping historical documents.

Is there anything else I can help you with?
"""
            next_step = "final_assistance"
        else:
            response = """
I did not get a clear Yes/No. Please reply Yes or No.
"""
            next_step = "historical_docs"


    # ------------------------------
    # STEP 5 â†’ End
    # ------------------------------

    elif step == "final_assistance":

        if choice == "yes":

            response = "Okay. Please provide details about the case."
            next_step = "conversation_end"

        elif choice == "no":

            response = (
                "Thank you for using the SBI Fraud Investigation Assistant. "
                "If you need help again, just type the case details anytime and I will be ready to assist."
            )
            next_step = "conversation_end"

        else:

            response = "I did not get a clear Yes/No. Please reply Yes or No."
            next_step = "final_assistance"


    save_chat_log(userId, bank_id, sessionId, query, response, next_step, analysis, case_query)

    fraud_category = analysis.get("fraud_category") if isinstance(analysis, dict) else ""

    return {
        "user": userId,
        "bank": bank_id,
        "query": query,
        "fraud_analysis": analysis,
        "chatbot_response": response,
        "next_step": next_step,
        "sessionId": sessionId,
        "fraud_category": fraud_category,
        "documents": documents
    }
# ------------------------------
# Login
# ------------------------------

@router.post("/login")
def login(request: dict):
    user_id = request.get("userId", "").strip()
    password = request.get("password", "").strip()

    if not user_id or not password:
        raise HTTPException(status_code=400, detail="userId and password are required")

    try:
        bank_id = verify_user_credentials(user_id, password)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid userId or password")

    return {"userId": user_id, "bankId": bank_id}

