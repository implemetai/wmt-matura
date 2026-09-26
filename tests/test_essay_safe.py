"""ESSAY_SAFE=1 tests: the stricter date verification (harness/cke_essay.py, synthetic sentences and passages),
the best-of-two topic choice, and the proof that with ESSAY_SAFE off the essay output and every prompt are
byte-identical to the code before the safe mode (golden fixture tests/fixtures/essay_off_golden.json, recorded
from the pre-ESSAY_SAFE code by tests/essay_fakes.py). ESSAY_SAFE=2 (years only + argued paragraphs): the
deterministic month/day removal (cke_essay.years_only) and the proof that ESSAY_SAFE=1 is byte-identical to the
code before level 2 (tests/fixtures/essay_safe1_golden.json, recorded from the pre-level-2 code; the timing fields
latency_s / elapsed_s are not compared).

All texts are our own wording (no CKE text).
Run:  python -m unittest tests.test_essay_safe -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import cke_essay  # noqa: E402
from harness.config import Settings  # noqa: E402

try:
    import httpx  # noqa: F401
    HAVE_HTTPX = True
except ImportError:  # the flows import harness.llm (httpx); the checker does not
    HAVE_HTTPX = False

PASSAGES = [
    "Kryzys berliński: 27 listopada 1958 Chruszczow wystosował ultimatum wobec mocarstw zachodnich w sprawie "
    "Berlina Zachodniego.",
    "Wojna koreańska rozpoczęła się 25 czerwca 1950 atakiem Korei Północnej na Koreę Południową.",
    "Józef Stalin zmarł w marcu 1953 roku w Moskwie.",
    "Rada Regencyjna 11 listopada 1918 przekazała Józefowi Piłsudskiemu naczelne dowództwo.",
    # the year and the entity in one passage, but far apart (> SAFE_WINDOW characters)
    "Traktat w Rydze podpisano w 1921 roku. " + "Kolejne lata przyniosły spokojny rozwój gospodarki i szkolnictwa. " * 6 +
    "Powstanie śląskie wybuchło później.",
]


def V(sent: str, passages=PASSAGES, fr=None):
    return cke_essay.verify_sentence_safe(sent, cke_essay.safe_index(passages), fr)


class SafeMonths(unittest.TestCase):
    def test_wrong_month_dropped_year_kept(self):
        out, issues, drop = V("W czerwcu 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual(out, "W 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual([i["kind"] for i in issues], ["month"])
        self.assertFalse(drop)

    def test_right_month_kept(self):
        s = "W listopadzie 1958 roku Chruszczow postawił ultimatum w sprawie Berlina."
        self.assertEqual(V(s), (s, [], False))

    def test_wrong_day_dropped_month_kept(self):
        out, issues, _ = V("25 listopada 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual(out, "W listopadzie 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual([i["kind"] for i in issues], ["day"])
        out, _, _ = V("Wojsko ruszyło. 27 czerwca 1950 roku Korea Północna zaatakowała Koreę Południową.")
        self.assertIn("Wojsko ruszyło. W czerwcu 1950 roku Korea", out)  # capitalised after a sentence end

    def test_roman_months(self):
        s = "11 XI 1918 roku Piłsudski przejął dowództwo."
        self.assertEqual(V(s)[1], [])
        out, issues, _ = V("Dnia 11 XII 1918 roku Piłsudski przejął dowództwo.")
        self.assertEqual(out, "W 1918 roku Piłsudski przejął dowództwo.")
        self.assertEqual(issues[0]["kind"], "month")
        out, _, _ = V("Piłsudski w XII 1918 roku przejął dowództwo.")
        self.assertEqual(out, "Piłsudski w 1918 roku przejął dowództwo.")
        # a ruler's ordinal is not a month
        self.assertEqual(cke_essay._date_mentions("Władca Jan III 1683 roku ruszył pod Wiedeń."), [])

    def test_month_elsewhere_in_passage_does_not_count(self):
        far = ["W 1958 roku zaostrzył się spór o Berlin. " + "Rozmowy trwały bardzo długo i nie przyniosły wyniku. " * 6
               + "W czerwcu odbył się zjazd partii."]
        out, issues, _ = V("W czerwcu 1958 roku zaostrzył się spór o Berlin.", far)
        self.assertEqual(out, "W 1958 roku zaostrzył się spór o Berlin.")
        self.assertEqual(issues[0]["kind"], "month")

    def test_event_name_month_is_not_a_date(self):
        self.assertEqual(cke_essay._date_mentions("Marzec 1968 pokazał słabość władzy."), [])


class SafeYears(unittest.TestCase):
    def test_year_near_entity_supported(self):
        s = "W 1950 roku Korea Północna zaatakowała Koreę Południową."
        self.assertEqual(V(s), (s, [], False))

    def test_year_of_another_event_removed(self):
        # 1953 is in the passages, but only next to Stalin's death, not next to 'powstanie'
        out, issues, drop = V("W 1953 roku wybuchło powstanie węgierskie.")
        self.assertEqual(out, "Wybuchło powstanie węgierskie.")
        self.assertEqual(issues, [{"kind": "year", "year": "1953"}])
        self.assertFalse(drop)  # still concrete: an event noun is left

    def test_year_far_from_entity_unsupported(self):
        out, issues, _ = V("Powstanie śląskie wybuchło w 1921 roku.")
        self.assertEqual(out, "Powstanie śląskie wybuchło.")
        self.assertEqual(issues[0]["kind"], "year")
        self.assertTrue(cke_essay.year_supported("1921", [r"\btrakta"], cke_essay.safe_index(PASSAGES)))

    def test_nothing_concrete_left_is_dropped(self):
        out, issues, drop = V("W 1957 roku sytuacja się zmieniła.")
        self.assertTrue(drop)
        self.assertEqual(issues[0]["kind"], "year")

    def test_numbers_that_are_not_years(self):
        self.assertEqual(cke_essay._years_in("Armia liczyła 300 tysięcy żołnierzy w 1950 roku."), ["1950"])

    def test_sentence_initial_name_counts_only_when_proper(self):
        idx = cke_essay.safe_index(PASSAGES)
        self.assertTrue(any("chrusz" in k for k in cke_essay.content_keys("Chruszczow postawił ultimatum.", idx)))
        self.assertFalse(cke_essay.content_keys("Kolejnym krokiem była nauka.", idx))


class SafeParagraph(unittest.TestCase):
    PAR = ("Kryzys berliński potwierdza tezę. W czerwcu 1958 roku Chruszczow postawił ultimatum w sprawie Berlina. "
           "W 1957 roku sytuacja się zmieniła. W 1950 roku Korea Północna zaatakowała Koreę Południową. "
           "Mocarstwa zachodnie nie ustąpiły. To pokazuje, że zimna wojna była groźna.")

    def test_paragraph_rewrites_drops_and_counts(self):
        idx = cke_essay.safe_index(PASSAGES)
        out, log, n = cke_essay.verify_paragraph_safe(self.PAR, idx)
        self.assertIn("W 1958 roku Chruszczow postawił ultimatum", out)
        self.assertNotIn("1957", out)
        self.assertNotIn("sytuacja się zmieniła", out)
        self.assertIn("W 1950 roku Korea Północna", out)
        self.assertEqual(n, 2)  # one month + one year
        self.assertEqual(sum(1 for x in log if "removed" in x), 1)

    def test_no_drop_mode_and_first_sentence(self):
        idx = cke_essay.safe_index(PASSAGES)
        out, log, n = cke_essay.verify_paragraph_safe("W 1957 roku sytuacja się zmieniła. Zgadzam się z tezą.", idx,
                                                     allow_drop=False)
        self.assertEqual(out, "Sytuacja się zmieniła. Zgadzam się z tezą.")
        self.assertEqual(n, 1)
        # the first sentence is never dropped, only its unsupported year goes
        out, _, _ = cke_essay.verify_paragraph_safe("W 1957 roku sytuacja się zmieniła. A. B. C. D.", idx)
        self.assertTrue(out.startswith("Sytuacja się zmieniła."))

    def test_count_unsupported_offline(self):
        text = "WYPRACOWANIE na temat nr 1\n\n" + self.PAR + "\n\nZgadzam się z tezą."
        st = cke_essay.count_unsupported(text, PASSAGES)
        self.assertEqual(st["unsupported"], 2)
        self.assertEqual(st["kinds"], {"month": 1, "year": 1})
        self.assertEqual(st["words"], cke_essay.body_words(text))

    def test_pick_candidate(self):
        pick = cke_essay.pick_candidate
        self.assertEqual(pick([{"words": 500, "unsupported": 10}, {"words": 480, "unsupported": 4}]), 1)
        self.assertEqual(pick([{"words": 500, "unsupported": 4}, {"words": 500, "unsupported": 4}]), 0)  # tie -> 1st
        self.assertEqual(pick([{"words": 420, "unsupported": 0}, {"words": 600, "unsupported": 9}]), 1)  # < 450 out
        self.assertEqual(pick([{"words": 420, "unsupported": 0}, {"words": 380, "unsupported": 0}]), 0)  # longer
        self.assertEqual(pick([{"words": 500, "unsupported": 3}]), 0)

    def test_old_verifier_untouched(self):
        blob = "Bitwa pod Grunwaldem 1410. Pokój toruński 1411. Unia w Krewie 1385."
        out, log = cke_essay.verify_paragraph("Jagiełło umocnił państwo w 1385 roku. Zwyciężył pod Grunwaldem w 1410 "
                                              "roku. W 1411 roku zawarto pokój. W 1432 roku wydał wymyślony przywilej. "
                                              "To potwierdza tezę.", blob)
        self.assertNotIn("1432", out)
        self.assertEqual(len(log), 1)


class SafeYearsOnly(unittest.TestCase):
    """ESSAY_SAFE=2: every month and day goes, plain years stay, event names stay (synthetic sentences)."""
    CASES = [
        ("Władze ogłosiły to w listopadzie 1958 r. w Berlinie.", "Władze ogłosiły to w 1958 r. w Berlinie."),
        ("13 grudnia 1981 roku wprowadzono stan wojenny.", "W 1981 roku wprowadzono stan wojenny."),
        ("Władze 13 grudnia 1981 roku wprowadziły stan wojenny.", "Władze w 1981 roku wprowadziły stan wojenny."),
        ("W sierpniu 1942 roku rozpoczęła się bitwa.", "W 1942 roku rozpoczęła się bitwa."),
        ("Bitwa skończyła się klęską w sierpniu 1942 roku, co zmieniło wojnę.",
         "Bitwa skończyła się klęską w 1942 roku, co zmieniło wojnę."),
        ("Akt, podpisany 6 marca 1454 roku, umocnił państwo.", "Akt, podpisany w 1454 roku, umocnił państwo."),
        ("Okupacja trwała od listopada 1942 roku.", "Okupacja trwała od 1942 roku."),
        ("Wojna trwała od września 1939 do maja 1945 roku.", "Wojna trwała od 1939 do 1945 roku."),
        ("Kampania trwała od 1 września do 6 października 1939 roku.", "Kampania trwała w 1939 roku."),
        ("W nocy z 12 na 13 grudnia 1981 roku wprowadzono stan wojenny.", "W 1981 roku wprowadzono stan wojenny."),
        ("Na przełomie września i października 1939 roku upadła obrona.", "W 1939 roku upadła obrona."),
        ("Pod koniec sierpnia 1939 roku podpisano pakt.", "W 1939 roku podpisano pakt."),
        ("Przed 1 września 1939 roku zawarto sojusz.", "Przed 1939 rokiem zawarto sojusz."),
        ("Wydarzenia października 1956 przyniosły zmianę ekipy.", "Wydarzenia 1956 roku przyniosły zmianę ekipy."),
        ("W dniach 28–30 czerwca 1956 robotnicy protestowali.", "W 1956 robotnicy protestowali."),
        ("Dnia 11 XI 1918 roku Piłsudski przejął dowództwo.", "W 1918 roku Piłsudski przejął dowództwo."),
        ("Porozumienie podpisano 31.08.1980 w stoczni.", "Porozumienie podpisano w 1980 w stoczni."),
        ("17 września Armia Czerwona wkroczyła do kraju.", "Armia Czerwona wkroczyła do kraju."),
        ("Wojsko 17 września wkroczyło, a w listopadzie tego samego roku utworzono rząd.",
         "Wojsko wkroczyło, a w tym samym roku utworzono rząd."),
        ("W maju następnego roku doszło do przewrotu.", "W następnym roku doszło do przewrotu."),
    ]
    KEEP = [
        "Marzec 1968 pokazał słabość władzy, a Czerwiec 1956 był pierwszym buntem.",
        "Grudzień 1970 i Sierpień 1980 zmusiły władzę do ustępstw.",
        "Po Grudniu 1970 i po Sierpniu 1980 władza musiała ustąpić; Poznański Czerwiec zaczął odwilż.",
        "Konstytucja 3 maja 1791 roku była pierwszą w Europie. Święto 11 listopada obchodzimy co roku.",
        "Jan III 1683 roku ruszył pod Wiedeń.",
        "Luty to krótki miesiąc, a marzec 1968 był przełomem.",
        "Maja pisała o tym w 1990 roku.",
        "W 1956 roku Gomułka wrócił do władzy.",
    ]

    def test_rewrites(self):
        for src, want in self.CASES:
            self.assertEqual(cke_essay.years_only(src), want, src)
            self.assertEqual(cke_essay.years_only(want), want, "not idempotent: " + want)
            self.assertEqual(cke_essay.month_day_left(want), [], want)
            self.assertTrue(cke_essay.month_day_left(src), src)

    def test_event_names_and_plain_years_stay(self):
        for s in self.KEEP:
            self.assertEqual(cke_essay.years_only(s), s)
            self.assertEqual(cke_essay.month_day_left(s), [])

    def test_paragraphs_and_sentence_starts(self):
        text = ("WYPRACOWANIE na temat nr 2\n\nAkapit pierwszy. 23 października 1956 roku wybuchło powstanie.\n\n"
                "25 października wojsko weszło do miasta.")
        self.assertEqual(cke_essay.years_only(text),
                         "WYPRACOWANIE na temat nr 2\n\nAkapit pierwszy. W 1956 roku wybuchło powstanie.\n\n"
                         "Wojsko weszło do miasta.")
        self.assertEqual(cke_essay.month_day_left(text), ["23 października 1956 roku", "25 października"])
        self.assertEqual(cke_essay.years_only(""), "")


class SafeDeepHelpers(unittest.TestCase):
    """ESSAY_SAFE=2 paragraph helpers: part labels removed, a closing tie to the stance, trimming that keeps it."""

    def test_strip_labels(self):
        self.assertEqual(cke_essay.strip_labels("Król potwierdza tezę. Kontekst i przyczyny: król zwołał sejm. "
                                                "Skutki i znaczenie: szlachta zyskała, np. przywileje."),
                         "Król potwierdza tezę. Król zwołał sejm. Szlachta zyskała, np. przywileje.")
        s = "Kontekst polityczny był trudny, np. dla króla. Skutki wojny trwały długo."
        self.assertEqual(cke_essay.strip_labels(s), s)

    def test_ensure_tie(self):
        par = "Pierwsze zdanie. Wojna skończyła się pokojem."
        out, added = cke_essay.ensure_tie(par, 0)
        self.assertTrue(added)
        self.assertEqual(out, par + " Ten przykład uzasadnia więc stanowisko przyjęte we wstępie.")
        self.assertIn("aspekt", cke_essay.ensure_tie(par, 1, aspect=True)[0])
        self.assertNotEqual(cke_essay.ensure_tie(par, 0)[0], cke_essay.ensure_tie(par, 1)[0])
        tied = "Pierwsze zdanie. To wydarzenie wyraźnie potwierdza tezę."
        self.assertEqual(cke_essay.ensure_tie(tied, 0), (tied, False))

    def test_trim_keep_last(self):
        pars = ["Wstęp krótki.", "Jeden raz. Dwa razy. Trzy razy. Cztery razy. To potwierdza tezę.", "Koniec."]
        self.assertEqual(cke_essay.trim_to_words(pars, 10, {0, 2}, keep_last=True)[1],
                         "Jeden raz. Dwa razy. Trzy razy. To potwierdza tezę.")
        self.assertEqual(cke_essay.trim_to_words(pars, 10, {0, 2})[1], "Jeden raz. Dwa razy. Trzy razy. Cztery razy.")


class SafeDefaults(unittest.TestCase):
    def test_off_by_default(self):
        old = os.environ.pop("ESSAY_SAFE", None)
        try:
            self.assertFalse(Settings().essay_safe)
            for v, want in (("1", 1), ("2", 2), ("0", 0), ("true", 1), ("on", 1), ("false", 0), ("", 0)):
                os.environ["ESSAY_SAFE"] = v
                self.assertEqual(Settings().essay_safe, want, v)
        finally:
            os.environ.pop("ESSAY_SAFE", None)
            if old is not None:
                os.environ["ESSAY_SAFE"] = old


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (flows import harness.llm)")
class SafeFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import essay_fakes
        cls.ef = essay_fakes
        cls._env = dict(os.environ)
        essay_fakes.clean_env()

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env)

    def test_off_is_byte_identical_to_pre_safe_code(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "essay_off_golden.json"), encoding="utf-8") as f:
            golden = json.load(f)
        for extra in ({}, {"essay_safe": False}, {"essay_safe": 0}):
            now = json.loads(json.dumps(self.ef.record(extra), ensure_ascii=False))
            for name in golden:
                for key in ("answer", "essay_meta", "calls", "retrieval"):
                    self.assertEqual(now[name][key], golden[name][key], f"{name}/{key} changed with ESSAY_SAFE off")

    @staticmethod
    def _no_timing(meta):
        meta = json.loads(json.dumps(meta, ensure_ascii=False))
        safe = (meta or {}).get("safe") or {}
        safe.pop("elapsed_s", None)
        for c in safe.get("candidates", []):
            c.pop("latency_s", None)
        return meta

    def test_safe1_is_byte_identical_to_pre_level2_code(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "essay_safe1_golden.json"), encoding="utf-8") as f:
            golden = json.load(f)
        for extra in ({"essay_safe": True}, {"essay_safe": 1}):
            now = json.loads(json.dumps(self.ef.record(extra), ensure_ascii=False))
            for name in golden:
                for key in ("answer", "calls", "retrieval"):
                    self.assertEqual(now[name][key], golden[name][key], f"{name}/{key} changed with ESSAY_SAFE=1")
                self.assertEqual(self._no_timing(now[name]["essay_meta"]), self._no_timing(golden[name]["essay_meta"]),
                                 f"{name}/essay_meta changed with ESSAY_SAFE=1")

    def test_safe2_years_only_and_argued_prompts(self):
        res, llm, _ = self.ef.run_essay({"essay_safe": 2})
        m = res.parsed["essay"]
        cands = m["safe"]["candidates"]
        self.assertEqual(len(cands), 2)  # best of two stays
        self.assertEqual(m["safe"]["chosen"], cke_essay.pick_candidate(cands, Settings().essay_safe_min_words))
        users = [c["messages"][1]["content"] for c in llm.calls]
        bodies = [u for u in users if "Napisz akapit rozwinięcia" in u]
        self.assertTrue(bodies)
        for u in bodies:
            for bit in ("(7–9 zdań)", "wyłącznie ten jeden element", "kontekst i przyczyny", "skutki i znaczenie",
                        "potwierdza albo osłabia stanowisko", "nigdy miesięcy ani dni", "pytań retorycznych",
                        "wyłącznie fakty zawarte w powyższych fragmentach"):
                self.assertIn(bit, u)
        self.assertTrue(all(c["max_tokens"] == 640 for c in llm.calls
                            if "Napisz akapit rozwinięcia" in c["messages"][1]["content"]))
        intros = [u for u in users if "Napisz wstęp" in u]
        self.assertTrue(intros and all("w jednym jasnym zdaniu zajmij stanowisko" in u and "omawiając kolejno:" in u
                                       for u in intros))
        ends = [u for u in users if "Napisz zakończenie" in u]
        self.assertTrue(ends and all("powtórz stanowisko" in u and "Nie dodawaj nowych faktów" in u for u in ends))
        # the fake writes 'W czerwcu 1956', '23 października 1956', 'W marcu 1953', ...: all become plain years
        self.assertEqual(cke_essay.month_day_left(res.answer), [])
        self.assertNotIn("października", res.answer)
        self.assertIn("W 1956 roku robotnicy Poznania", res.answer)
        self.assertGreater(m["n_years_only"], 0)
        self.assertIn("tie_added", m)
        self.assertEqual(m["safe"]["years_only_final"], 0)  # nothing left for the final safety net
        # ESSAY_SAFE=1 still keeps a month the passages support (the level-2 rewrite is level-2 only)
        res1, _, _ = self.ef.run_essay({"essay_safe": 1})
        self.assertTrue(cke_essay.month_day_left(res1.answer))

    def test_safe_best_of_two(self):
        res, llm, _ = self.ef.run_essay({"essay_safe": True})
        m = res.parsed["essay"]
        cands = m["safe"]["candidates"]
        self.assertEqual(len(cands), 2)
        self.assertNotEqual(cands[0]["topic"], cands[1]["topic"])
        self.assertEqual(m["safe"]["chosen"], cke_essay.pick_candidate(cands, Settings().essay_safe_min_words))
        self.assertEqual(m["topic"], m["safe"]["chosen_topic"])
        self.assertTrue(all(isinstance(c["unsupported"], int) for c in cands))
        self.assertEqual(res.llm_calls, sum(c["llm_calls"] for c in cands))
        bodies = [c for c in llm.calls if "Napisz akapit rozwinięcia" in c["messages"][-1]["content"] or
                  "Napisz akapit rozwinięcia" in c["messages"][1]["content"]]
        self.assertTrue(bodies)
        self.assertTrue(all("nigdy miesięcy ani dni" in c["messages"][1]["content"] for c in bodies))
        # the fake writes 'W listopadzie 1956 ... Gomułka' (passages: październik) and 'W 1957 roku ...' (no passage)
        self.assertNotIn("listopadzie 1956", res.answer)
        self.assertNotIn("1957", res.answer)

    def test_safe_forced_topic_single_candidate(self):
        res, _, _ = self.ef.run_essay({"essay_safe": True, "essay_topic": 3})
        m = res.parsed["essay"]
        self.assertEqual([c["topic"] for c in m["safe"]["candidates"]], ["3"])
        self.assertEqual(m["topic"], "3")


if __name__ == "__main__":
    unittest.main()
