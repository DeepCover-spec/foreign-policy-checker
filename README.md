# Treaty Clause Checker

Paste a clause, pick a country, and see which provisions of the ICCPR it may conflict with, shown verbatim, with that country's ratification status and reservations.

**This tool flags provisions for human review. It is not legal advice and does not decide whether a conflict exists.** It does not assess domestic effect (e.g. dualist systems), interpretation, customary law or jus cogens.

## How it works

1. **Data**: ICCPR Articles 1-27 are parsed from the official PDF into 109 clauses with IDs like `ICCPR-14-3-b`. Every clause is checked to be verbatim in the source.
2. **Ratifications**: kept in a separate file (Sri Lanka, UK, US, Cuba). Only countries *bound* (ratified/acceded/succeeded, not signed-only) are checked.
3. **Retrieval**: BM25 (with stemming) and sentence embeddings (`all-MiniLM-L6-v2`) each propose candidates.
4. **LLM (optional)**: an LLM chooses from the candidates and explains why. It may only return clause IDs. Every ID is validated against the candidate list, and all quoted text comes from the database, never from the model.
5. **Fallback**: if the LLM is unavailable, retrieval results are shown with a note.

## Evaluation

26 test clauses with known expected provisions (Sri Lanka) plus 9 no-match cases:

| Method | Top-1 | Top-5 | Found |
|---|---|---|---|
| BM25 | 14/26 | 19/26 | 23/26 |
| Embeddings | 12/26 | 22/26 | 23/26 |
| Hybrid (RRF) | 14/26 | 22/26 | 24/26 |
| LLM (`openai/gpt-oss-20b` on Groq free tier) | 24/26 | 25/26 | 25/26 |

LLM no-match cases passed: 9/9, average 2.8 results per clause.

Limitations: small test set written by me; the LLM prompt was tuned after seeing the no-match failures, so the 9/9 is optimistic; results vary slightly between runs even at temperature 0; all clauses are still marked `verified: false` pending manual checks against the PDF.

## Run it

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e .
    streamlit run app.py

For the LLM step, create `.env` (never committed):

    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_API_KEY=your-key
    LLM_MODEL=openai/gpt-oss-20b

Any OpenAI-compatible endpoint works. Your pasted clause is sent to that provider.

Evaluate: `python tests\evaluate.py` (add `--llm` for the LLM block).
Rebuild clauses from the PDF: `python src\treaty_checker\parse_iccpr.py`.

## Data sources

- ICCPR text: https://www.ohchr.org/sites/default/files/ccpr.pdf
- Ratification status and reservations: UN Treaty Collection