# Treaty Clause Checker

Paste a clause, pick a country, and see which provisions of the ICCPR and the Convention against Torture (CAT) it may conflict with, shown verbatim, with that country's ratification status and reservations.

**This tool flags provisions for human review. It is not legal advice and does not decide whether a conflict exists.** It does not assess domestic effect (e.g. dualist systems), interpretation, customary law or jus cogens.

## How it works

1. **Data**: ICCPR Articles 1-27 and CAT Articles 1-16 are parsed from the official PDFs into 159 clauses (109 + 50) with IDs like `ICCPR-14-3-b` or `CAT-5-1-a`. Every clause is checked to be verbatim in the source.
2. **Ratifications**: kept in a separate file (Sri Lanka, UK, US, Cuba) with reservations and declarations from the UN Treaty Collection. Only treaties a country is *bound* by (ratified/acceded/succeeded, not signed-only) are checked. For example, Cuba only signed the ICCPR, so it is checked against CAT only.
3. **Retrieval**: BM25 (with stemming) and sentence embeddings (`all-MiniLM-L6-v2`) each propose candidates.
4. **LLM (optional)**: an LLM chooses from the candidates and explains why. It may only return clause IDs. Every ID is validated against the candidate list, and all quoted text comes from the database, never from the model.
5. **Fallback**: if the LLM is unavailable, retrieval results are shown with a note.

## Evaluation

30 test clauses with known expected provisions (Sri Lanka): 26 synthetic and 4 taken from real legislation (Prevention of Terrorism Act s.9(1); Online Safety Act ss.11(c), 12, 16), plus 8 no-match clauses.

| Method | Top-1 | Top-5 | Found |
|---|---|---|---|
| BM25 | 15/30 | 22/30 | 27/30 |
| Embeddings | 14/30 | 23/30 | 27/30 |
| Hybrid (RRF) | 17/30 | 26/30 | 28/30 |
| LLM (`openai/gpt-oss-20b` on Groq free tier) | 25/29 | 29/29 | 29/29 |

LLM: no-match cases passed 8/8; on average 3.0 results returned per clause (retrieval blocks return 20). One call returned no valid JSON and is excluded from the LLM score (hence 29, not 30); a retry for that case has since been added.

### Limitations of this evaluation

- Small test set written by me. The synthetic cases are paraphrases, not real law.
- The LLM prompt was tightened after I saw it flag two compliant clauses, so the no-match score is optimistic.
- When CAT was added, I widened `expected` for three cases (`CAT-2-2`, `CAT-16-1`, `CAT-15`) after reading the CAT text, and fixed one expectation (`ICCPR-19-3` is a parent clause that can never be returned; replaced with `ICCPR-19-3-b`).
- The emergency case passes via `CAT-2-2`; the model still does not return `ICCPR-4-2`. For the Online Safety Act s.12 case it returns `19-3-b` (the limitation clause) but not `19-2`.
- Results vary slightly between runs even at temperature 0.
- Only a few clauses are marked `verified` (checked by hand against the PDF).
- The retrieval blocks and the LLM block were run on the same final test set but not on the same day, and the LLM block ran once.

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

Evaluate:

    python tests\evaluate.py              retrieval only (free)
    python tests\evaluate.py --only-llm   LLM block only
    python tests\evaluate.py --llm        everything

The free Groq tier has a daily token limit (about 200,000), so run the LLM block once a day.

## Add a treaty

    python src\treaty_checker\extract.py data\raw\<treaty>.pdf
    python src\treaty_checker\parse_treaty.py <TREATY> data/raw/<treaty>.txt <LAST_ARTICLE> <SOURCE_URL>

Then add ratification entries to `data\ratifications.json`. Parsing a treaty merges into `data\clauses.json` and keeps other treaties and `verified` flags. Mark clauses as verified with `python src\treaty_checker\verify.py <ID> ...`.

## Data sources

- ICCPR text: https://www.ohchr.org/sites/default/files/ccpr.pdf
- CAT text: https://www.ohchr.org/sites/default/files/cat.pdf
- Ratification status and reservations: UN Treaty Collection (retrieved 2026-10-22 for CAT, 2026-10-11 for ICCPR)