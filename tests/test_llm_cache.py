import json
import os
import tempfile

from treaty_checker import llm
from treaty_checker.llm import DailyLimitError, LLMConfig, LLMError, LLMResult
from treaty_checker.pipeline import check_llm

llm.time.sleep = lambda s: None
tmp = tempfile.mkdtemp()
os.environ["LLM_CACHE"] = os.path.join(tmp, "c", "cache.json")


class C:
    def __init__(self, i): self.id, self.citation, self.text = i, i, "t"


cands = [C("A-1"), C("A-2")]
GOOD = '{"matches":[{"id":"A-1","reasoning":"r","confidence":"high"}]}'
cfg = LLMConfig("u", "k", "main", 5, ("backup1", "backup2"))

calls = []
def fake_chat(script):
    it = iter(script)
    def f(config, system, user):
        calls.append(config.model)
        item = next(it)
        if isinstance(item, Exception): raise item
        return item
    return f

# 1. normal call, then identical call is served from the cache
llm.chat = fake_chat([GOOD]); calls.clear()
r = llm.analyze("x", cands, cfg)
assert [m.id for m in r.matches] == ["A-1"] and r.model == "main" and not r.used_fallback and calls == ["main"]
llm.chat = fake_chat([]); calls.clear()                 # any real call would raise StopIteration
r = llm.analyze("x", cands, cfg); assert calls == [] and r.matches[0].id == "A-1"
assert os.path.exists(os.environ["LLM_CACHE"])

# 2. a different clause is not served from the cache
llm.chat = fake_chat([GOOD]); calls.clear(); llm.analyze("y", cands, cfg); assert calls == ["main"]

# 3. daily limit on the main model -> falls back, flags it
llm.chat = fake_chat([DailyLimitError("tpd"), GOOD]); calls.clear()
r = llm.analyze("z", cands, cfg)
assert calls == ["main", "backup1"] and r.model == "backup1" and r.used_fallback

# 4. fallback answer is cached under its own model; main is still asked first next time
llm.chat = fake_chat([DailyLimitError("tpd")]); calls.clear()
r = llm.analyze("z", cands, cfg)
assert calls == ["main"] and r.model == "backup1" and r.used_fallback    # main limited again, backup1 from cache

# 5. every model limited -> DailyLimitError
llm.chat = fake_chat([DailyLimitError("a"), DailyLimitError("b"), DailyLimitError("c")]); calls.clear()
try: llm.analyze("never-seen", cands, cfg); raise SystemExit("should fail")
except DailyLimitError: assert calls == ["main", "backup1", "backup2"]

# 6. bad JSON: asked a second time; bad replies are not cached
llm.chat = fake_chat(["", GOOD]); calls.clear(); r = llm.analyze("w", cands, cfg); assert calls == ["main", "main"]
llm.chat = fake_chat(["bad", "bad"]); calls.clear()
try: llm.analyze("v", cands, cfg); raise SystemExit("should fail")
except LLMError: pass
cache = json.load(open(os.environ["LLM_CACHE"]))
assert all("matches" in v for v in cache.values())

# 7. a corrupt cache entry is ignored and re-asked
key = llm._cache_key("main", llm.SYSTEM_PROMPT, llm.build_user_prompt("corrupt", cands))
cache[key] = "garbage"; json.dump(cache, open(os.environ["LLM_CACHE"], "w"))
llm.chat = fake_chat([GOOD]); calls.clear(); llm.analyze("corrupt", cands, cfg); assert calls == ["main"]

# 8. a different primary model does not reuse another model's cached answer
llm.chat = fake_chat([GOOD]); calls.clear()
llm.analyze("x", cands, LLMConfig("u", "k", "other-model", 5)); assert calls == ["other-model"]

# 9. cache off
os.environ["LLM_CACHE"] = "off"
llm.chat = fake_chat([GOOD, GOOD]); calls.clear(); llm.analyze("x", cands, cfg); llm.analyze("x", cands, cfg); assert len(calls) == 2
os.environ["LLM_CACHE"] = os.path.join(tmp, "c", "cache.json")

# 10. pipeline shows a note when a fallback model answered
from treaty_checker.db import build_db, connect
from treaty_checker.loader import load_clauses
from treaty_checker.ratifications import load_ratifications
from treaty_checker.retrieval import Retriever
build_db(); conn = connect(); clauses = load_clauses("data/clauses.json"); rat = load_ratifications()
class Fake(Retriever):
    def candidates(self, text, treaties, bm25_n=10, emb_n=20):
        return [c for c in self.clauses if c.id in ("ICCPR-19-2", "ICCPR-9-2")]
ret = Fake(clauses)
fb = lambda t, c: LLMResult(llm.parse_and_validate('{"matches":[{"id":"ICCPR-19-2","reasoning":"r","confidence":"low"}]}', {"ICCPR-19-2"}).matches, [], "backup1", True)
f, note = check_llm("x", "Sri Lanka", ret, conn, rat, fb)
assert [x.clause.id for x in f] == ["ICCPR-19-2"] and "backup1" in note and "daily limit" in note
f, note = check_llm("x", "Sri Lanka", ret, conn, rat, lambda t, c: LLMResult([], []))
assert note is None
print("llm cache/fallback: ok")