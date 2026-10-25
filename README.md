# Treaty Clause Checker

Paste a clause, pick a country, and see which provisions of nine legally binding human-rights and humanitarian treaties it may conflict with, shown verbatim, with that country's ratification status and reservations.

**This tool flags provisions for human review. It is not legal advice and does not decide whether a conflict exists.** It does not assess domestic effect (e.g. dualist systems), interpretation, customary law or jus cogens.

## How it works

1. **Data**: treaty articles are parsed from the official texts into 771 clauses with IDs like `ICCPR-14-3-b` or `CAT-5-1-a`. Every clause is checked to be verbatim in the source text it was parsed from.
2. **Ratifications**: kept in a separate file, imported from the UN Treaty Collection for every party, with reservations, declarations and the UN's own footnotes. Only treaties a country is *bound* by (ratified, acceded, succeeded, accepted, approved or confirmed; not signed-only) are checked. For example, Cuba only signed the ICCPR and ICESCR, so it is checked against the others only. The app shows which treaties are checked for the chosen country. Treaties not in the dataset are not checked at all, so an empty result never shows that a country is not bound.
3. **Retrieval**: BM25 (with stemming) and sentence embeddings (`all-MiniLM-L6-v2`) each propose candidates, combined by reciprocal rank fusion.
4. **LLM (optional)**: an LLM chooses from the candidates and explains why. It may only return clause IDs. Every ID is validated against the candidate list, and all quoted text comes from the database, never from the model. The number of tokens per check does not grow with the number of treaties: the model sees at most 30 candidates.
5. **Fallback**: if the LLM is unavailable, retrieval results are shown with a note. If the primary model's daily limit is reached, fallback models are tried and the app says so.
6. **Reservations**: reservations that mention the matched article are shown first, in a warning. The others are collapsed. Whether a reservation actually limits a provision is for a person to decide.

## Treaties covered

| Treaty | Clauses | Articles | Text source |
|---|---|---|---|
| ICCPR | 109 | 1-27 | OHCHR (PDF) |
| ICESCR | 64 | 1-15 | OHCHR (PDF) |
| CAT | 50 | 1-16 | OHCHR (PDF) |
| CERD | 27 | 1-7 | OHCHR (PDF) |
| CEDAW | 77 | 1-16 | OHCHR (PDF) |
| CRC | 156 | 1-41 | OHCHR (PDF) |
| CRPD | 190 | 1-30 | UN (PDF) |
| Genocide Convention | 18 | 1-8 | OHCHR web page, copied by hand |
| Refugee Convention (1951) | 80 | 1-34 | OHCHR web page, copied by hand |

Only the substantive articles are indexed. Committee, procedure and final-clause articles are left out. Only legally binding instruments are in scope (no UDHR or other declarations).

## Evaluation

30 test clauses with known expected provisions (Sri Lanka): 26 synthetic and 4 taken from real legislation (Prevention of Terrorism Act s.9(1); Online Safety Act ss.11(c), 12, 16), plus 8 no-match clauses. The cases are about civil and political rights, so they test the ICCPR and CAT.

| Method | Top-1 | Top-5 | Found |
|---|---|---|---|
| BM25 | 15/30 | 22/30 | 27/30 |
| Embeddings | 13/30 | 23/30 | 27/30 |
| Hybrid (RRF) | 17/30 | 25/30 | 27/30 |
| LLM (`openai/gpt-oss-20b` on Groq free tier) | 25/30 | 28/30 | 28/30 |

LLM: no-match cases passed 7/8; on average 3.2 results returned per clause (retrieval blocks return 20).

**These numbers were measured with three treaties in the index (ICCPR, CAT, ICESCR: 223 clauses). They have not been re-run since the other six treaties were added**, so they may have changed.

### Limitations of this evaluation

- Small test set written by me. The synthetic cases are paraphrases, not real law.
- The test set only covers civil and political rights, so it says nothing about how well the later treaties (CRC, CRPD, CEDAW, the Refugee Convention and others) are found.
- The LLM prompt was tightened after I saw it flag two compliant clauses, so the no-match score is optimistic. The one remaining failure is "Public libraries shall be open from nine…", which the model matches to freedom of information (ICCPR-19-2, 19-3-b). That is arguable, but it counts as a failure.
- When CAT was added, I widened `expected` for three cases (`CAT-2-2`, `CAT-16-1`, `CAT-15`) after reading the CAT text, and fixed one expectation (`ICCPR-19-3` is a parent clause that can never be returned; replaced with `ICCPR-19-3-b`).
- The two LLM misses: a clause denying women the right to give evidence in court is matched to fair-trial provisions rather than the equality provisions (`ICCPR-3`, `ICCPR-26`), and for the Online Safety Act s.12 case it returns `ICCPR-12-3` and `22-2` instead of `19-2`.
- The emergency case passes via `CAT-2-2`; the model still does not return `ICCPR-4-2`.
- Results vary slightly between runs even at temperature 0.

## Limitations

- **Unverified text.** Clauses are parsed from the official texts and checked by code, but only a few have been compared with the source by hand (`verify.py`). The app marks unverified clauses. The Genocide and Refugee Convention texts were copied from a web page, not a PDF. The four real-law test clauses were assembled from fragments and still need checking against the official texts.
- **Refugee Convention:** states bound only through the 1967 Protocol (for example the United States) are not yet recorded as bound by the Convention's Articles 2-34, so they currently get no refugee-law results.
- **Refugee Convention Article 1** (the definition) is stored as one clause, because its A-F sections cannot be split reliably.
- **Reservations** are shown as stored. Whether a reservation limits a provision is for a person to decide.
- **Not covered:** the Geneva Conventions, the Rome Statute, Security Council resolutions, treaties outside the nine above, and domestic law.

## Run it

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e .
    streamlit run app.py

Restart Streamlit after changing the data: it loads the clauses and ratifications once.

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

1. Get the text. For a PDF, extract it with either extractor (try the second if words come out split, for example "discri mination"):

        python src\treaty_checker\extract.py data\raw\<treaty>.pdf data\raw\<treaty>.txt
        python src\treaty_checker\extract_mupdf.py data\raw\<treaty>.pdf data\raw\<treaty>.txt

   The second one needs `pip install pymupdf`. A short treaty can also be copied from a web page into a UTF-8 text file.

2. Parse it:

        python src\treaty_checker\parse_treaty.py <TREATY> data/raw/<treaty>.txt <LAST_ARTICLE> <SOURCE_URL> [--whole=1,5]

   It replaces that treaty's clauses and keeps other treaties and `verified` flags. It drops page numbers, reads Roman-numeral headings ("Article IV"), headings with titles, and chapter lines. `--whole=` keeps the listed articles as one clause. Check the printed paragraph and item counts against the real treaty.

3. Import the ratifications. On the treaty's page in the UN Treaty Collection, save the page as "Webpage, HTML only" into `data\raw\untc\`, and run:

        python src\treaty_checker\import_untc.py <TREATY> data/raw/untc/<treaty>.html "<PAGE URL>"

   The importer reads the saved file and makes no requests to the UN. It replaces that treaty's entries, keeps the others, and compares any entries you already had by hand.

4. Spot-check clauses with `python src\treaty_checker\verify.py <ID> ...`.

## Data sources and terms

- Treaty texts: OHCHR (https://www.ohchr.org) and the UN, as listed in the table above. Each clause stores its source URL.
- Ratification status, reservations and declarations: UN Treaty Collection, https://treaties.un.org, status as at 2026-10-24 and 2026-10-25, imported from pages saved by hand.
- `data/ratifications.json` is not committed to the repository, because the UN's terms limit reuse and redistribution of its content. To recreate it, save the pages and run the importer as above.