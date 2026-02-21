"""
PDF RAG Assistant — Streamlit Application
Run: streamlit run app.py
"""

import os
import tempfile
import hashlib
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF RAG Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── User store (username → hashed password, role, display name) ──────────────
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

USERS = {
    "admin":  {"hash": _hash("admin123"),  "name": "Admin",       "role": "admin"},
    "user1":  {"hash": _hash("user123"),   "name": "User One",    "role": "user"},
    "demo":   {"hash": _hash("demo"),      "name": "Demo User",   "role": "user"},
}

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Login */
.login-wrapper {
    max-width:420px; margin:60px auto;
    background:linear-gradient(135deg,#1e3a5f 0%,#0d6efd 100%);
    border-radius:20px; padding:3px;
    box-shadow:0 20px 60px rgba(13,110,253,.35);
}
.login-card { background:#fff; border-radius:18px; padding:2.5rem 2.2rem 2rem; }
.login-logo  { text-align:center; font-size:3.5rem; margin-bottom:.3rem; }
.login-title { text-align:center; font-size:1.6rem; font-weight:700; color:#1e3a5f; }
.login-sub   { text-align:center; font-size:.9rem; color:#6c757d; margin-bottom:1.6rem; }
/* Sidebar */
[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#0f2444 0%,#1a3a6b 100%) !important;
}
[data-testid="stSidebar"] * { color:#e8edf4 !important; }
[data-testid="stSidebar"] .stButton>button {
    background:rgba(255,255,255,.12) !important;
    border:1px solid rgba(255,255,255,.25) !important;
    color:#fff !important; border-radius:8px !important;
}
[data-testid="stSidebar"] .stButton>button:hover { background:rgba(255,255,255,.22) !important; }
[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.15) !important; }
/* Header */
.app-header {
    background:linear-gradient(90deg,#0d6efd 0%,#0a58ca 100%);
    border-radius:14px; padding:1.4rem 2rem; margin-bottom:1.5rem;
    display:flex; align-items:center; gap:1.2rem;
}
.app-header-icon  { font-size:2.8rem; }
.app-header-title { color:#fff; font-size:1.9rem; font-weight:700; margin:0; }
.app-header-sub   { color:rgba(255,255,255,.8); font-size:.95rem; margin:0; }
/* Stat cards */
.stat-card { background:linear-gradient(135deg,#f8f9ff,#eef2ff);
             border:1px solid #d0d8ff; border-radius:12px;
             padding:1rem 1.2rem; text-align:center; }
.stat-number { font-size:1.8rem; font-weight:700; color:#0d6efd; }
.stat-label  { font-size:.8rem; color:#6c757d; margin-top:.2rem; }
/* Source cards */
.source-card { border:1px solid #dee2e6; border-radius:10px;
               padding:.8rem 1rem; margin-bottom:.6rem; font-size:.88rem; }
.source-card b { color:#0d6efd; }
/* Confidence badges */
.badge-high   { background:#d1fae5; color:#065f46; padding:3px 12px;
                border-radius:20px; font-size:.8rem; font-weight:600; }
.badge-medium { background:#fef9c3; color:#713f12; padding:3px 12px;
                border-radius:20px; font-size:.8rem; font-weight:600; }
.badge-low    { background:#fee2e2; color:#991b1b; padding:3px 12px;
                border-radius:20px; font-size:.8rem; font-weight:600; }
/* Welcome */
.welcome-card { border:2px dashed #93c5fd; border-radius:16px; padding:3rem 2rem;
                text-align:center; background:#eff6ff; margin-top:2rem; }
.welcome-card h3 { color:#1e40af; } .welcome-card p { color:#3b82f6; }
/* User pill */
.user-pill { background:rgba(255,255,255,.15); border-radius:20px;
             padding:4px 12px; font-size:.85rem; display:inline-block; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════

def authenticate(username: str, password: str):
    u = USERS.get(username.strip().lower())
    if u and u["hash"] == _hash(password):
        return u
    return None


def show_login():
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="login-wrapper"><div class="login-card">
          <div class="login-logo">📄</div>
          <div class="login-title">PDF RAG Assistant</div>
          <div class="login-sub">Sign in to continue</div>
        </div></div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("login_form"):
            username  = st.text_input("👤 Username", placeholder="Enter username")
            password  = st.text_input("🔒 Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")
        st.markdown("---")
        st.caption("**Demo credentials** — username: `demo` / password: `demo`")


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "chat_history"  not in st.session_state: st.session_state.chat_history  = []
if "indexed_files" not in st.session_state: st.session_state.indexed_files = []

if not st.session_state.authenticated:
    show_login()
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="⚙️ Loading AI models — please wait…")
def load_backend():
    from rag_backend import EmbeddingManager, VectorStore, RAGRetriever, CrossEncoderReranker
    em        = EmbeddingManager()
    vs        = VectorStore(collection_name="pdf_documents", persist_directory="../data/vector_store")
    retriever = RAGRetriever(vs, em)
    reranker  = CrossEncoderReranker()
    return em, vs, retriever, reranker


def get_llm(model_name, temperature):
    from rag_backend import build_llm
    return build_llm(model_name=model_name, temperature=temperature)


def confidence_badge(score: float) -> str:
    pct = f"{score:.0%}"
    if score >= 0.6: return f'<span class="badge-high">✅ High confidence · {pct}</span>'
    if score >= 0.3: return f'<span class="badge-medium">⚡ Medium confidence · {pct}</span>'
    return f'<span class="badge-low">⚠️ Low confidence · {pct}</span>'


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

em, vs, retriever, reranker = load_backend()

with st.sidebar:
    user = st.session_state.user
    st.markdown(f"""
    <div style="text-align:center;margin-bottom:1rem;">
      <div style="font-size:2.5rem;">{"🛡️" if user["role"]=="admin" else "👤"}</div>
      <div style="font-weight:700;font-size:1rem;">{user["name"]}</div>
      <div class="user-pill">{user["role"].upper()}</div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    st.markdown("### 📂 Upload PDFs")
    uploaded_files = st.file_uploader("PDFs", type=["pdf"],
                                      accept_multiple_files=True,
                                      label_visibility="collapsed")
    if uploaded_files:
        if st.button("⚡ Index PDFs", use_container_width=True):
            from rag_backend import process_pdfs, split_documents
            with st.spinner("Processing…"):
                tmp_paths = []
                for uf in uploaded_files:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    tmp.write(uf.read()); tmp.close()
                    tmp_paths.append(tmp.name)
                docs   = process_pdfs(tmp_paths)
                chunks = split_documents(docs)
                embeds = em.embed([c.page_content for c in chunks])
                vs.add_documents(chunks, embeds)
                for tp in tmp_paths: os.unlink(tp)
                st.session_state.indexed_files += [f.name for f in uploaded_files]
            st.success(f"✅ Indexed {len(chunks)} chunks!")

    st.divider()
    st.markdown("### 🤖 Model")
    model_choice = st.selectbox("Model",
        ["llama-3.1-8b-instant","llama-3.1-70b-versatile",
         "llama3-8b-8192","mixtral-8x7b-32768"],
        index=0, label_visibility="collapsed")
    temperature = st.slider("🌡️ Temperature", 0.0, 1.0, 0.5, 0.05)

    st.markdown("### 🔍 Retrieval")
    top_k     = st.slider("📚 Top-K chunks",         1, 10, 7)
    min_score = st.slider("🎯 Min similarity score", 0.0, 1.0, 0.05, 0.05)
    st.caption("💡 Lower = broader retrieval")

    st.divider()
    doc_count = vs.count()
    st.markdown("### 📊 Stats")
    st.metric("Chunks indexed", doc_count)
    st.metric("PDFs uploaded",  len(st.session_state.indexed_files))
    if st.session_state.indexed_files:
        with st.expander("📁 Files"):
            for f in st.session_state.indexed_files:
                st.caption(f"• {f}")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.chat_history = []; st.rerun()
    with c2:
        if st.button("🚪 Logout", use_container_width=True):
            for k in ["authenticated","user","chat_history","indexed_files"]:
                st.session_state.pop(k, None)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="app-header">
  <div class="app-header-icon">📄</div>
  <div>
    <p class="app-header-title">PDF RAG Assistant</p>
    <p class="app-header-sub">Grounded AI answers · Logged in as <b>{user["name"]}</b></p>
  </div>
</div>""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
q_count = len([m for m in st.session_state.chat_history if m["role"] == "user"])
for col, num, label in [(c1, doc_count, "Chunks indexed"),
                        (c2, len(st.session_state.indexed_files), "PDFs uploaded"),
                        (c3, q_count, "Questions asked")]:
    with col:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{num}</div>'
                    f'<div class="stat-label">{label}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if doc_count == 0:
    st.markdown("""
    <div class="welcome-card">
      <div style="font-size:3rem;">📂</div>
      <h3>No documents indexed yet</h3>
      <p>Upload PDFs from the sidebar, then click <b>⚡ Index PDFs</b>.</p>
    </div>""", unsafe_allow_html=True)

# Chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant":
            meta = msg.get("meta")
            if meta:
                st.markdown(confidence_badge(meta["confidence"]), unsafe_allow_html=True)
                if meta.get("sources"):
                    with st.expander("📎 Source documents"):
                        for s in meta["sources"]:
                            st.markdown(
                                f'<div class="source-card"><b>📄 {s["source"]}</b>'
                                f' · Page <b>{s["page"]}</b> · Score <b>{s["score"]:.2f}</b>'
                                f'<br><span style="color:#555">{s["preview"]}</span></div>',
                                unsafe_allow_html=True)

# Input
query = st.chat_input("Ask a question about your documents…" if doc_count > 0
                      else "Upload and index a PDF first…")

if query:
    if doc_count == 0:
        st.warning("⚠️ No documents indexed. Upload PDFs from the sidebar first.")
    else:
        with st.chat_message("user"):
            st.write(query)
        st.session_state.chat_history.append({"role": "user", "content": query})

        with st.chat_message("assistant"):
            with st.spinner("🔍 Searching and generating answer…"):
                from rag_backend import rag_enhanced
                llm    = get_llm(model_choice, temperature)
                result = rag_enhanced(query, retriever, llm,
                                      top_k=top_k, min_score=min_score,
                                      reranker=reranker)
            st.write(result["answer"])
            st.markdown(confidence_badge(result["confidence"]), unsafe_allow_html=True)
            if result["sources"]:
                with st.expander("📎 Source documents"):
                    for s in result["sources"]:
                        st.markdown(
                            f'<div class="source-card"><b>📄 {s["source"]}</b>'
                            f' · Page <b>{s["page"]}</b> · Score <b>{s["score"]:.2f}</b>'
                            f'<br><span style="color:#555">{s["preview"]}</span></div>',
                            unsafe_allow_html=True)

        st.session_state.chat_history.append(
            {"role": "assistant", "content": result["answer"], "meta": result})
