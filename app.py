import streamlit as st

from treaty_checker.db import build_db, connect
from treaty_checker.loader import load_clauses
from treaty_checker.pipeline import check
from treaty_checker.ratifications import bound_by, load_ratifications
from treaty_checker.retrieval import Retriever

st.set_page_config(page_title="Treaty Clause Checker")


@st.cache_resource
def setup():
    build_db()
    return Retriever(load_clauses("data/seed_clauses.json")), load_ratifications()


retriever, ratifications = setup()
countries = sorted({r.country for r in ratifications})

st.title("Treaty Clause Checker")
st.warning(
    "This tool flags provisions that may relate to a pasted clause, for human review. "
    "It is not legal advice and does not decide whether a conflict exists. It does not "
    "assess domestic effect (for example in dualist systems), interpretation, "
    "customary law or jus cogens."
)

country = st.selectbox("Country", countries)
text = st.text_area("Paste a clause", height=150)

if st.button("Check") and text.strip():
    if not bound_by(country, ratifications):
        st.info(f"No instruments in the dataset that {country} is bound by.")
        st.stop()

    conn = connect()
    findings = check(text, country, retriever, conn, ratifications)
    conn.close()

    if not findings:
        st.info("No candidate provisions found.")

    for f in findings:
        c, r = f.clause, f.ratification
        st.subheader(c.citation)
        st.text(c.text)
        if not c.verified:
            st.caption("Not yet checked against the official source.")
        st.markdown(f"**{country}:** {r.status} on {r.date} "
                    f"(data retrieved {r.retrieved_on}) · [source]({c.source_url})")
        st.caption(f"Match score {f.score:.2f}")

        if f.parent:
            with st.expander(f"Context: {f.parent.citation}"):
                st.text(f.parent.text)
        if r.reservations:
            with st.expander(f"Reservations and declarations by {country} ({len(r.reservations)})"):
                st.caption("These may or may not affect this provision. Check each against it.")
                for res in r.reservations:
                    st.text(res)

st.caption(f"Ratification data last retrieved: {max(r.retrieved_on for r in ratifications)}")