from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict
from extractor.config import load_config
from extractor.pdf_extract import extract_keys, Extract
from extractor.db import init_db, insert_document, insert_extractions, fetch_latest
from datetime import datetime

st.set_page_config(page_title="PDF Key-Value Extractor", layout="wide")
st.title("PDF Key-Value Extractor")

CFG_PATH = Path(__file__).resolve().parents[1] / "configs" / "fields.yaml"
DB_PATH = Path(__file__).resolve().parents[1] / "app_data.sqlite"

@st.cache_resource
def _init():
    init_db(DB_PATH)
    return load_config(CFG_PATH)

cfg = _init()

with st.sidebar:
    st.header("Config")
    st.code(CFG_PATH.read_text(), language="yaml")
    if st.button("Refresh config"):
        st.cache_resource.clear()
        cfg = _init()
        st.success("Reloaded.")

uploaded = st.file_uploader("Upload a PDF form", type=["pdf"])

col1, col2 = st.columns([2,1])

with col1:
    if uploaded is not None:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            pdf_path = Path(tmp.name)

        st.caption(f"Working on **{uploaded.name}** ...")
        try:
            results: Dict[str, Extract] = extract_keys(pdf_path, cfg)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            results = {}

        if results:
            st.subheader("Results (editable)")
            form = st.form("results_form")
            edited = {}
            for k, (v, conf, method, notes) in results.items():
                with st.expander(f"{k}  ·  conf={conf:.2f} · {method}"):
                    edited[k] = form.text_input("value", value=v, key=f"val_{k}")
                    form.caption(notes)
            submitted = form.form_submit_button("Save to DB")
            if submitted:
                doc_id = insert_document(DB_PATH, uploaded.name)
                rows = [(k, edited[k], results[k][1], results[k][2], "") for k in edited]
                insert_extractions(DB_PATH, doc_id, rows)
                st.success(f"Saved {len(rows)} keys for document #{doc_id}.")
        else:
            st.info("No keys found by current config. Try adjusting patterns in `configs/fields.yaml`.")

with col2:
    st.subheader("Recent saves")
    rows = fetch_latest(DB_PATH, limit=100)
    if rows:
        for (doc_id, fname, uploaded_at, key, value, conf, method) in rows:
            st.markdown(f"**{fname}**  \n{doc_id}  \n_{uploaded_at}_")
            st.code(f"{key}: {value}  (conf={conf}, method={method})")
    else:
        st.caption("No saved extractions yet.")
