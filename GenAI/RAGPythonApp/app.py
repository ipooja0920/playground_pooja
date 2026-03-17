import os
import tempfile

import streamlit as st

from doc_processor import load_and_chunk_pdf
from vector_db import get_embed_model, get_qdrant_client, index_chunks, retrieve, hash_file
from llm_client import get_answer

st.set_page_config(page_title="RAG PDF Chat", page_icon="📄", layout="wide")


# ── Cached resources (initialised once per session) ────────────────────────

@st.cache_resource
def load_embed_model():
    return get_embed_model()


@st.cache_resource
def load_qdrant_client():
    return get_qdrant_client()


embed_model = load_embed_model()
qdrant_client = load_qdrant_client()


# ── Session state ───────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "processed_hashes" not in st.session_state:
    st.session_state.processed_hashes = set()

if "processed_files" not in st.session_state:
    st.session_state.processed_files = []


# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📄 Documents")

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type="pdf",
        accept_multiple_files=True,
    )

    if st.button("Process Documents", disabled=not uploaded_files, type="primary"):
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            file_hash = hash_file(file_bytes)

            if file_hash in st.session_state.processed_hashes:
                st.info(f"Already indexed: **{uploaded_file.name}**")
                continue

            with st.status(f"Processing {uploaded_file.name}…") as status:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name

                    nodes = load_and_chunk_pdf(tmp_path)

                    # Replace temp path with the real upload filename
                    for node in nodes:
                        node.metadata["filename"] = uploaded_file.name

                    index_chunks(nodes, embed_model, qdrant_client)

                    st.session_state.processed_hashes.add(file_hash)
                    st.session_state.processed_files.append(uploaded_file.name)
                    status.update(label=f"✅ {uploaded_file.name}", state="complete")

                except ValueError as e:
                    status.update(label=f"❌ {uploaded_file.name}", state="error")
                    st.error(str(e))

                except Exception as e:
                    status.update(label=f"❌ {uploaded_file.name}", state="error")
                    st.error(f"Unexpected error processing {uploaded_file.name}: {e}")

                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

    if st.session_state.processed_files:
        st.divider()
        st.subheader("Indexed Documents")
        for name in st.session_state.processed_files:
            st.markdown(f"- {name}")


# ── Main chat area ──────────────────────────────────────────────────────────

st.title("Chat with your PDFs")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

has_docs = len(st.session_state.processed_files) > 0
placeholder = (
    "Ask a question about your documents…"
    if has_docs
    else "Upload and process documents first."
)

if question := st.chat_input(placeholder, disabled=not has_docs):
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                hits = retrieve(question, embed_model, qdrant_client)

                if not hits:
                    full_response = (
                        "I couldn't find any relevant information in the uploaded documents."
                    )
                else:
                    context_chunks = [text for text, _, _ in hits]
                    answer = get_answer(question, context_chunks)

                    # Build deduplicated citations
                    seen: set = set()
                    citation_parts = []
                    for _, filename, page_label in hits:
                        key = (filename, page_label)
                        if key not in seen:
                            seen.add(key)
                            citation_parts.append(f"**{filename}**, p. {page_label}")

                    citations = "\n\n---\n📎 *Sources: " + " | ".join(citation_parts) + "*"
                    full_response = answer + citations

                st.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

            except RuntimeError as e:
                st.error(str(e))

            except Exception as e:
                st.error(f"Unexpected error: {e}")
