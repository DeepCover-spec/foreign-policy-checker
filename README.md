# Treaty Clause Checker

Paste a clause, pick a country, and see which provisions of the ICCPR, the Convention against Torture (CAT) and the ICESCR it may conflict with, shown verbatim, with that country's ratification status and reservations.

**This tool flags provisions for human review. It is not legal advice and does not decide whether a conflict exists.** It does not assess domestic effect (e.g. dualist systems), interpretation, customary law or jus cogens.

## How it works

1. **Data**: ICCPR Articles 1-27, CAT Articles 1-16 and ICESCR Articles 1-15 are parsed from the official PDFs into 223 clauses (109 + 50 + 64) with IDs like `ICCPR-14-3-b` or `CAT-5-1-a`. Every clause is checked to be verbatim in the source.
2. **Ratifications**: kept in a separate file, imported from the UN Treaty Collection for every party, with reservations and declarations. Only treaties a country is *bound* by (ratified/acceded/succeeded, not signed-only) are checked. For example, Cuba only signed the ICCPR and ICESCR, so it is checked against CAT only. The app shows which treaties are checked for the chosen country. Treaties not in the dataset are not checked at all, so an empty result never shows that a country is not bound.
3. **Retrieval**: BM25 (with stemming) and sentence embeddings (`all-MiniLM-L6-v2`) each propose candidates.
4. **LLM (optional)**: an LLM chooses from the candidates and explains why. It may only return clause IDs. Every ID is validated against the candidate list, and all quoted text comes from the database, never from the model.
5. **Fallback**: if the LLM is unavailable, retrieval results are shown with a note. If the primary model's daily limit is reached, fallback models are tried and the app says so.
6. **Reservations**: reservations that mention the matched article are shown first, in a warning. The others are collapsed. Whether a reservation actually limits a provision is for a person to decide.

## Evaluation

30 test clauses with known expected provisions (Sri Lanka): 26 synthetic and 4 taken from real legislation (Prevention of Terrorism Act s.9(1); Online Safety Act ss.11(c), 12, 16), plus 8 no-match clauses.

| Method | Top-1 | Top-5 | Found |
|---|---|---|---|
| BM25 | 15/30 | 22/30 | 27/30 |
| Embeddings | 13/30 | 23/30 | 27/30 |
| Hybrid (RRF) | 17/30 | 25/30 | 27/30 |
| LLM (`openai/gpt-oss-20b` on Groq free tier) | 25/30 | 28/30 | 28/30 |

LLM: no-match cases passed 7/8; on average 3.2 results returned per clause (retrieval blocks return 20). All numbers are from one run after ICESCR was added to the index.

### Limitations of this evaluation

- Small test set written by me. The synthetic cases are paraphrases, not real law.
- The LLM prompt was tightened after I saw it flag two compliant clauses, so the no-match score is optimistic. The one remaining failure is "Public libraries shall be open from nine…", which the model matches to freedom of information (ICCPR-19-2, 19-3-b). That is arguable, but it counts as a failure.
- When CAT was added, I widened `expected` for three cases (`CAT-2-2`, `CAT-16-1`, `CAT-15`) after reading the CAT text, and fixed one expectation (`ICCPR-19-3` is a parent clause that can never be returned; replaced with `ICCPR-19-3-b`).
- The two LLM misses: a clause denying women the right to give evidence in court is matched to fair-trial provisions rather than the equality provisions (`ICCPR-3`, `ICCPR-26`), and for the Online Safety Act s.12 case it returns `ICCPR-12-3` and `22-2` instead of `19-2`.
- The emergency case passes via `CAT-2-2`; the model still does not return `ICCPR-4-2`.
- Results vary slightly between runs even at temperature 0.
- Only a few clauses are marked `verified` (checked by hand against the PDF). The four real-law test clauses were assembled from fragments and still need checking against the official texts.
- Statuses "accepted" and "approved" are not yet counted as binding.

## Run it

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e .
    streamlit run app.py

For the LLM step, create `.env` (never committed):

    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_API_KEY=your-key
    LLM_MODEL=openai/gpt-oss-20b
    LLM_FALLBACK_MODELS=openai/gpt-oss-120b,qwen/qwen3.8-27b

Any OpenAI-compatible endpoint works. Your pasted clause is sent to that provider. Replies are cached in `.cache/` (set `LLM_CACHE=off` to disable).

Evaluate:

    python tests\evaluate.py              retrieval only (free)
    python tests\evaluate.py --only-llm   LLM block only
    python tests\evaluate.py --llm        everything

The free Groq tier has daily and per-minute token limits (about 200,000 a day and 8,000 a minute for the model above), so run the LLM block once a day. Calls that fail are excluded from the score, and replies already received are cached, so a re-run only repeats the failed ones.

## Add a treaty

    python src\treaty_checker\extract.py data\raw\<treaty>.pdf data\raw\<treaty>.txt
    python src\treaty_checker\parse_treaty.py <TREATY> data/raw/<treaty>.txt <LAST_ARTICLE> <SOURCE_URL>

Parsing a treaty merges into `data\clauses.json` and keeps other treaties and `verified` flags. Mark clauses as verified with `python src\treaty_checker\verify.py <ID> ...`.

Then import the ratifications. On the treaty's page in the UN Treaty Collection, save the page as "Webpage, HTML only" into `data\raw\untc\`, and run:

    python src\treaty_checker\import_untc.py <TREATY> data/raw/untc/<treaty>.html "<PAGE URL>"

The importer reads the saved file and makes no requests to the UN. It replaces that treaty's entries and keeps the others, and compares any entries you already had by hand.

## Data sources

- ICCPR text: https://www.ohchr.org/sites/default/files/ccpr.pdf
- CAT text: https://www.ohchr.org/sites/default/files/cat.pdf
- ICESCR text: https://www.ohchr.org/sites/default/files/cescr.pdf
- Ratification status and reservations: UN Treaty Collection, https://treaties.un.org (status as at 2026-10-24 for CAT and ICCPR, 2026-10-25 for ICESCR)

`data/ratifications.json` is not committed, because the UN's terms limit reuse and redistribution of its content. To recreate it, save the pages and run the importer as above.