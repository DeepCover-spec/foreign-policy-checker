import streamlit as st

from treaty_checker.db import build_db, connect
from treaty_checker.display import paragraphs_for_display
from treaty_checker.embeddings import HybridRetriever
from treaty_checker.llm import load_config
from treaty_checker.loader import load_clauses
from treaty_checker.pipeline import check, check_llm
from treaty_checker.ratifications import bound_by, coverage, load_ratifications
from treaty_checker.reservations import split_reservations

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
bound_list, not_bound_list = coverage(country, ratifications)
st.caption(
    f"Treaties checked: {', '.join(bound_list) or 'none'} (bound). "
    + (f"Not bound or signed only: {', '.join(not_bound_list)}. " if not_bound_list else "")
    + "Treaties not in the dataset are not checked at all."
)

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
        st.text(paragraphs_for_display(c.text))  # always the stored text, never model output
        if not c.verified:
            st.caption("Not yet checked against the official source.")
        if f.reasoning:
            st.markdown(f"**Model's note ({f.confidence} confidence):** {f.reasoning}")
            st.caption("Written by an AI model. Check it against the provision text above.")
        st.markdown(f"**{country}:** {r.status} on {r.date} "
                    f"(data retrieved {r.retrieved_on}) · [source]({c.source_url})")

        if f.parent:
            with st.expander(f"Context: {f.parent.citation}"):
                st.text(paragraphs_for_display(f.parent.text))
        if r.reservations:
            relevant, others = split_reservations(r.reservations, int(c.article))
            if relevant:
                st.warning(
                    f"{country} made {len(relevant)} reservation(s) or declaration(s) that mention "
                    f"article {c.article} of the {c.treaty}. They may limit the obligation here. "
                    "Read them before relying on this result."
                )
                with st.expander(f"Reservations mentioning article {c.article} ({len(relevant)})", expanded=True):
                    for res in relevant:
                        st.text(res)
            if others:
                with st.expander(f"Other reservations and declarations by {country} ({len(others)})"):
                    st.caption("These do not name this article, but may still affect it. Check each against it.")
                    for res in others:
                        st.text(res)

st.caption(f"Ratification data last retrieved: {max(r.retrieved_on for r in ratifications)}")