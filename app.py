import streamlit as st

from treaty_checker.db import build_db, connect
from treaty_checker.embeddings import HybridRetriever
from treaty_checker.llm import load_config
from treaty_checker.loader import load_clauses
from treaty_checker.pipeline import check, check_llm
from treaty_checker.ratifications import bound_by, load_ratifications

st.set_page_config(page_title="Treaty Clause Checker")


@st.cache_resource
def setup():
    build_db()
    return HybridRetriever(load_clauses("data/clauses.json")), load_ratifications()


retriever, ratifications = setup()
countries = sorted({r.country for r in ratifications})
llm_ready = load_config() is not None

st.title("Treaty Clause Checker")
st.warning(
    "This tool flags provisions that may relate to a pasted clause, for human review. "
    "It is not legal advice and does not decide whether a conflict exists. It does not "
    "assess domestic effect (for example in dualist systems), interpretation, "
    "customary law or jus cogens."
)

country = st.selectbox("Country", countries)
text = st.text_area("Paste a clause", height=150)
use_llm = st.checkbox(
    "Use LLM analysis (chooses and explains the relevant provisions)",
    value=llm_ready,
    disabled=not llm_ready,
    help="Needs LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in the .env file. "
         "Your pasted clause is sent to that provider.",
)

if st.button("Check") and text.strip():
    if not bound_by(country, ratifications):
        st.info(f"No instruments in the dataset that {country} is bound by.")
        st.stop()

    conn = connect()
    note = None
    if use_llm:
        with st.spinner("Asking the model..."):
            findings, note = check_llm(text, country, retriever, conn, ratifications)
    else:
        findings = check(text, country, retriever, conn, ratifications)
    conn.close()

    if note:
        st.warning(note)
    if not findings:
        if use_llm and not note:
            st.info("The model found no relevant provisions among the candidates. "
                    "This does not show that no conflict exists.")
        else:
            st.info("No candidate provisions found.")

    for i, f in enumerate(findings, start=1):
        c, r = f.clause, f.ratification
        st.subheader(c.citation)
        st.caption(f"Result {i} of {len(findings)}")
        st.text(c.text)  # always the stored text, never model output
        if not c.verified:
            st.caption("Not yet checked against the official source.")
        if f.reasoning:
            st.markdown(f"**Model's note ({f.confidence} confidence):** {f.reasoning}")
            st.caption("Written by an AI model. Check it against the provision text above.")
        st.markdown(f"**{country}:** {r.status} on {r.date} "
                    f"(data retrieved {r.retrieved_on}) · [source]({c.source_url})")

        if f.parent:
            with st.expander(f"Context: {f.parent.citation}"):
                st.text(f.parent.text)
        if r.reservations:
            with st.expander(f"Reservations and declarations by {country} ({len(r.reservations)})"):
                st.caption("These may or may not affect this provision. Check each against it.")
                for res in r.reservations:
                    st.text(res)

st.caption(f"Ratification data last retrieved: {max(r.retrieved_on for r in ratifications)}")