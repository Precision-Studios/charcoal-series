# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from build import build, originals, simplify, fetch
from unittest.mock import patch
from subprocess import CompletedProcess


class BundleTest(unittest.TestCase):
    def test_permanent_http_error_fails_even_with_cached_input(self):
        source = dict(id="example", group="example", url="https://example.com/list")
        previous = build([source], None, lambda _: "||example.org^")
        for code in ("403", "404"):
            with self.subTest(code=code), patch("build.subprocess.run", return_value=CompletedProcess([], 0, stderr=code)) as run:
                with self.assertRaisesRegex(RuntimeError, f"example: HTTP {code} at https://example.com/list"):
                    build([source], previous, fetch)
                run.assert_called_once()
                args = run.call_args.args[0]
                self.assertLessEqual(float(args[args.index("--max-time") + 1]), 30)

    def test_directives_and_attribution_survive_repetition(self):
        raw = "#Copyright\n#Copyright\n!#if\tenv_firefox\nr\nr\n!#else\nr\n!#endif comment\nr\nr"
        text, removed = simplify(raw, {}, 0)
        self.assertEqual(raw.removesuffix("\nr"), text)
        self.assertEqual(1, len(removed))

    def test_scopes_recovery_and_unchanged_publication(self):
        ids = ["ublock-filters", "ublock-privacy", "ublock-url-tracking", "fanboy-social"]
        sources = [dict(id=i, group="fanboy" if i.startswith("fanboy") else "ublock",
                        url="https://example.com/"+i, title=i) for i in ids]
        rule = "||same.example^"
        protected = "!#if env_firefox\n"+rule+"\n!#endif\nmulti \\\n"+rule
        texts = [rule, rule+"\n"+protected, rule, rule]
        fetch = lambda s: texts[ids.index(s["id"])]
        first = build(sources, None, fetch, now=1)
        rows = first["sources"]
        self.assertEqual([rule, protected, rule, rule], ["".join(r["chunks"]) for r in rows])
        self.assertEqual(texts, [v[0] for v in originals(first).values()])
        self.assertEqual(first, build(sources, first, fetch, now=999))
        def outage(source):
            if source["id"] == ids[1]:
                raise OSError("timeout")
            return "||changed.example^" if source["id"] == ids[0] else fetch(source)
        reports = []
        next_bundle = build(sources, first, outage, now=86401, report=reports.append)
        self.assertIn("24 hours", reports[0])
        self.assertEqual(texts[1], "".join(next_bundle["sources"][1]["chunks"]))
        with self.assertRaises(RuntimeError):
            build(sources, None, outage)
        damaged = copy.deepcopy(first)
        damaged["sources"][0]["chunks"] = ["tampered"]
        with self.assertRaises(ValueError):
            originals(damaged)
