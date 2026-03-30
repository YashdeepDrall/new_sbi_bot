import streamlit as st
import os
import time
from urllib.parse import urljoin

import requests

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
API_URL = f"{API_BASE}/fraud"
LOGIN_URL = f"{API_BASE}/login"
API_REQUEST_TIMEOUT_SECONDS = float(os.getenv("API_REQUEST_TIMEOUT_SECONDS", "75"))
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
API_RETRY_BACKOFF_SECONDS = float(os.getenv("API_RETRY_BACKOFF_SECONDS", "2"))
TRANSIENT_STATUS_CODES = {429, 502, 503, 504}

st.set_page_config(page_title="SBI Fraud Investigation Assistant", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Space+Grotesk:wght@400;600;700&display=swap');

html, body, [class*="css"]  {
  font-family: "Manrope", "Space Grotesk", sans-serif;
}

.stApp {
  background: radial-gradient(1200px 800px at 10% 10%, #e6f7f2 0%, #f7fbff 45%, #ffffff 100%);
}

.app-title { font-size: 36px; font-weight: 800; letter-spacing: 0.2px; margin-bottom: 6px; color: #0f2a3a; }
.app-subtitle { font-size: 15px; color: #4b6b7a; margin-bottom: 18px; }
.section-title { font-size: 20px; font-weight: 700; margin-top: 16px; color: #143347; }
.section-title { margin-bottom: 6px; }

.glass-card {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(15, 42, 58, 0.08);
  box-shadow: 0 12px 30px rgba(15, 42, 58, 0.08);
  border-radius: 16px;
  padding: 22px;
  backdrop-filter: blur(8px);
}

.login-card {
  padding: 22px;
  border: 1px solid rgba(15, 42, 58, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  box-shadow: 0 18px 40px rgba(15, 42, 58, 0.12);
}

.center-wrap { display: flex; justify-content: center; }
.center-card { width: 100%; max-width: 420px; }

@keyframes floatIn {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}

.fade-in { animation: floatIn 0.6s ease-out; }

div.stButton > button {
  background: linear-gradient(90deg, #2457c5 0%, #2e7be8 100%);
  color: #ffffff;
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

div.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(36, 87, 197, 0.25);
}

div.stDownloadButton > button {
  background: linear-gradient(90deg, #0b5cab 0%, #2a7de1 100%);
  color: #ffffff;
  border: none;
  border-radius: 10px;
  padding: 8px 14px;
  font-weight: 700;
}

div.stTextInput > div > div > input {
  border-radius: 10px;
  border: 1px solid rgba(15, 42, 58, 0.15);
  padding: 10px 12px;
  background: #ffffff;
}

div[data-testid="stTextInput"] small {
  display: none;
}

div[data-testid="InputInstructions"] {
  display: none;
}

div[data-testid="stTextInput"] [data-testid="InputInstructions"] {
  display: none;
}

div[data-testid="stInfo"] {
  border-radius: 12px;
  border: 1px solid rgba(11, 92, 171, 0.15);
  background: rgba(219, 236, 255, 0.7);
}

.topbar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 10px;
}

.chat-row {
  display: flex;
  margin: 8px 0;
}

.chat-tight {
  margin-top: 2px;
}

.chat-left {
  justify-content: flex-start;
}

.chat-right {
  justify-content: flex-end;
}

.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 16px;
  line-height: 1.4;
  font-size: 15px;
  box-shadow: 0 8px 20px rgba(15, 42, 58, 0.08);
}

.bubble-ai {
  background: #ffffff;
  border: 1px solid rgba(15, 42, 58, 0.08);
  color: #0f2a3a;
}

.bubble-prompt {
  background: rgba(219, 236, 255, 0.7);
  border: 1px solid rgba(11, 92, 171, 0.15);
  color: #0f2a3a;
}

.bubble-user {
  background: #e8f1ff;
  border: 1px solid rgba(36, 87, 197, 0.18);
  color: #173255;
}

.input-wrap {
  display: none;
}

.chat-space {
  padding-top: 0;
  padding-bottom: 2px;
  margin-top: 0px;
}
</style>
""",
    unsafe_allow_html=True
)

st.markdown('<div class="app-title fade-in">SBI Fraud Investigation Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle fade-in">Secure, guided fraud investigation for State Bank of India</div>', unsafe_allow_html=True)

# -------------------------
# SESSION STATE
# -------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "fraud_category" not in st.session_state:
    st.session_state.fraud_category = ""

if "session_id" not in st.session_state:
    st.session_state.session_id = ""

if "latest_documents" not in st.session_state:
    st.session_state.latest_documents = []

if "next_prompt" not in st.session_state:
    st.session_state.next_prompt = ""

if "documents_followup_prompt" not in st.session_state:
    st.session_state.documents_followup_prompt = ""

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "login_error" not in st.session_state:
    st.session_state.login_error = ""

# -------------------------
# HELPERS
# -------------------------

def request_backend(method, url, **kwargs):
    last_response = None
    last_error = None

    for attempt in range(API_MAX_RETRIES):
        try:
            response = requests.request(
                method,
                url,
                timeout=API_REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt == API_MAX_RETRIES - 1:
                raise
        else:
            if response.status_code not in TRANSIENT_STATUS_CODES:
                return response

            last_response = response
            if attempt == API_MAX_RETRIES - 1:
                return response

        time.sleep(API_RETRY_BACKOFF_SECONDS * (attempt + 1))

    if last_response is not None:
        return last_response

    if last_error is not None:
        raise last_error

    raise RuntimeError("Backend request failed without a response.")


def call_fraud_api(user_id, query, session_id):
    try:
        params = {
            "userId": user_id,
            "query": query
        }
        if session_id:
            params["sessionId"] = session_id

        response = request_backend("get", API_URL, params=params)

        if response.ok:
            return response.json()

        if response.status_code in TRANSIENT_STATUS_CODES:
            return {
                "chatbot_response": (
                    f"Backend temporarily returned {response.status_code}. "
                    "On Render free tier this usually means the API is waking up or a transient routing issue happened. "
                    "Please retry in a few seconds."
                )
            }

        try:
            payload = response.json()
            detail = payload.get("detail", "")
        except Exception:
            detail = response.text.strip()

        return {"chatbot_response": detail or f"Backend returned status {response.status_code}."}
    except Exception as e:
        return {
            "chatbot_response": (
                "API Error: "
                f"{str(e)}. If you are on Render free tier, the backend may still be waking up. Please retry."
            )
        }


def extract_prompt(text):
    if not text:
        return "", ""

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    prompt = ""

    for ln in reversed(lines):
        lower_ln = ln.lower()
        if (
            "(Yes/No)" in ln
            or ln.endswith("?")
            or "provide details about the case" in lower_ln
            or "describe the new fraud case" in lower_ln
            or "thank you for using the sbi fraud investigation assistant" in lower_ln
        ):
            prompt = ln
            break

    if prompt:
        cleaned = text.replace(prompt, "").strip()
        return cleaned, prompt

    return text, ""

# -------------------------
# LOGIN
# -------------------------

if not st.session_state.logged_in:
    col_left, col_mid, col_right = st.columns([2, 3, 2])
    with col_mid:
        st.markdown('<div class="section-title">Login</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            user_id_input = st.text_input("User ID", value=st.session_state.user_id, placeholder="Enter your user ID")
            password_input = st.text_input("Password", value="", type="password", placeholder="Enter your password")
            submit_login = st.form_submit_button("Continue")
        st.markdown("</div>", unsafe_allow_html=True)

        if submit_login:
            user_id_input = user_id_input.strip()
            password_input = password_input.strip()
            if not user_id_input or not password_input:
                st.session_state.login_error = "User ID and password are required."
            else:
                try:
                    resp = request_backend(
                        "post",
                        LOGIN_URL,
                        json={"userId": user_id_input, "password": password_input},
                    )
                except Exception as exc:
                    st.session_state.login_error = (
                        f"Unable to reach backend: {exc}. "
                        "If this is on Render free tier, wait for the backend cold start and try again."
                    )
                else:
                    if resp.status_code == 200:
                        st.session_state.user_id = user_id_input
                        st.session_state.logged_in = True
                        st.session_state.login_error = ""
                        st.rerun()
                    elif resp.status_code == 401:
                        st.session_state.login_error = "Invalid user ID or password."
                    elif resp.status_code in TRANSIENT_STATUS_CODES:
                        st.session_state.login_error = (
                            f"Backend temporarily returned {resp.status_code}. "
                            "On Render free tier this usually means the API is waking up or a transient routing issue happened. "
                            "Please wait a few seconds and try again."
                        )
                    else:
                        try:
                            detail = resp.json().get("detail", "")
                        except Exception:
                            detail = ""
                        st.session_state.login_error = detail or f"Backend returned status {resp.status_code}."

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

    st.stop()

# Seed initial assistant prompt on first load
if st.session_state.logged_in and not st.session_state.chat_history:
    st.session_state.next_prompt = "Hello😊 Please provide details about SBI fraud case."

# -------------------------
# DISPLAY CHAT HISTORY
# -------------------------

col_spacer, col_reset, col_logout = st.columns([6, 1, 1])
with col_reset:
    if st.button("Reset Conversation"):
        st.session_state.chat_history = []
        st.session_state.fraud_category = ""
        st.session_state.session_id = ""
        st.session_state.latest_documents = []
        st.session_state.next_prompt = ""
        st.session_state.documents_followup_prompt = ""
        st.rerun()
with col_logout:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.chat_history = []
        st.session_state.fraud_category = ""
        st.session_state.session_id = ""
        st.session_state.latest_documents = []
        st.session_state.next_prompt = ""
        st.session_state.documents_followup_prompt = ""
        st.rerun()

st.markdown('<div class="section-title fade-in">SBI Fraud Investigation Chat</div>', unsafe_allow_html=True)
st.markdown('<div class="chat-space">', unsafe_allow_html=True)

if st.session_state.next_prompt:
    last_item = st.session_state.chat_history[-1] if st.session_state.chat_history else None
    if not last_item or last_item.get("role") != "prompt" or last_item.get("content") != st.session_state.next_prompt:
        st.session_state.chat_history.append({
            "role": "prompt",
            "content": st.session_state.next_prompt
        })
    st.session_state.next_prompt = ""

for idx, chat in enumerate(st.session_state.chat_history):
    if chat["role"] == "user":
        user_text = str(chat["content"]).replace("\n", "<br>")
        st.markdown(
            f'<div class="chat-row chat-right"><div class="bubble bubble-user">{user_text}</div></div>',
            unsafe_allow_html=True
        )
    elif chat["role"] == "documents":
        extra_class = " chat-tight" if idx == 0 else ""
        st.markdown(
            f'<div class="chat-row chat-left{extra_class}"><div class="bubble bubble-ai">Relevant SOP Documents</div></div>',
            unsafe_allow_html=True
        )
        for doc in chat.get("items", []):
            doc_name = doc.get("name", "Document")
            doc_path = doc.get("path", "")
            file_id = doc.get("fileId", "")
            file_name = os.path.basename(doc_path) if doc_path else f"{doc_name}.pdf"

            st.markdown(f"**{doc_name}**")

            if doc_path and os.path.exists(doc_path):
                with open(doc_path, "rb") as f:
                    st.download_button(
                        label=f"Download {doc_name}",
                        data=f.read(),
                        file_name=file_name,
                        mime="application/pdf",
                        key=f"download_{idx}_{doc_name}"
                    )
            elif file_id:
                resp = request_backend(
                    "get",
                    urljoin(f"{API_BASE}/", f"documents/{file_id}"),
                )
                if resp.status_code == 200:
                    st.download_button(
                        label=f"Download {doc_name}",
                        data=resp.content,
                        file_name=file_name,
                        mime="application/pdf",
                        key=f"download_{idx}_{doc_name}"
                    )
                else:
                    st.warning(f"Unable to fetch document: {doc_name}")
            else:
                st.warning(f"Missing file path and fileId for: {doc_name}")
    elif chat["role"] == "prompt":
        prompt_text = str(chat["content"]).replace("\n", "<br>")
        extra_class = " chat-tight" if idx == 0 else ""
        st.markdown(
            f'<div class="chat-row chat-left{extra_class}"><div class="bubble bubble-prompt">{prompt_text}</div></div>',
            unsafe_allow_html=True
        )
    else:
        bot_text = str(chat["content"]).replace("\n", "<br>")
        extra_class = " chat-tight" if idx == 0 else ""
        st.markdown(
            f'<div class="chat-row chat-left{extra_class}"><div class="bubble bubble-ai">{bot_text}</div></div>',
            unsafe_allow_html=True
        )
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# USER INPUT
# -------------------------

user_query = st.chat_input("Describe the fraud case or reply Yes / No when asked")

# -------------------------
# HANDLE USER QUERY
# -------------------------

if user_query:
    normalized_query = user_query.strip().lower()
    followup_answers = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "no", "n", "nope", "nah", "nothing"}

    if normalized_query not in followup_answers:
        st.session_state.latest_documents = []
        st.session_state.documents_followup_prompt = ""

    st.session_state.chat_history.append({
        "role": "user",
        "content": user_query
    })

    data = call_fraud_api(st.session_state.user_id, user_query, st.session_state.session_id)

    chatbot_response = data.get("chatbot_response", "")
    fraud_category = data.get("fraud_category", "")
    returned_session_id = data.get("sessionId", "")
    documents = data.get("documents", [])

    st.session_state.next_prompt = ""

    if fraud_category:
        st.session_state.fraud_category = fraud_category

    if returned_session_id:
        st.session_state.session_id = returned_session_id

    if documents:
        st.session_state.latest_documents = documents
        st.session_state.chat_history.append({
            "role": "documents",
            "items": documents
        })

    cleaned, prompt = extract_prompt(chatbot_response)
    if prompt:
        st.session_state.next_prompt = prompt

    full_response = cleaned or chatbot_response

    if prompt and full_response.strip() == prompt.strip():
        full_response = ""

    if documents:
        full_response = full_response.replace("Relevant SOP Documents:", "").strip()
        for doc in documents:
            doc_name = doc.get("name", "")
            if doc_name:
                full_response = full_response.replace(doc_name, "").strip()

    cleaned_response = full_response.strip()
    if cleaned_response:
        st.session_state.chat_history.append({
            "role": "bot",
            "content": cleaned_response
        })

    st.rerun()

