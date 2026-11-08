"""Tests für den Wächter (ohne Internet):  python3 -m pytest watch/"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_rules as w  # noqa: E402

RULES = """III. BANDS: 160, 80, 40, 20, 15 and 10 meter bands only.
IV. EXCHANGE: SSB: RS report plus CQ Zone number.
V. POINTS: Contacts between stations on different continents count three (3) points.
"""


def test_line_breaks_do_not_matter():
    rewrapped = RULES.replace(" plus ", "\nplus ").replace("count three", "count\n   three")
    assert w.fingerprint(w.tidy(rewrapped)) == w.fingerprint(w.tidy(RULES))


def test_changed_number_is_found():
    changed = RULES.replace("three (3)", "four (4)")
    assert w.fingerprint(changed) != w.fingerprint(RULES)
    gone, added = w.word_changes(w.tokens({}, RULES), w.tokens({}, changed))
    assert gone == ["3", "three"] and added == ["4", "four"]


def test_html_text_and_footer():
    page = ("<html><head><script>var x=1;</script><style>p{}</style></head><body>"
            "<nav>Menu</nav><main><h1>Rules</h1><p>Points: 3&nbsp;per QSO</p></main>"
            "<p>Copyright © 2008-2026 WWROF</p></body></html>")
    t = w.tidy(w.html_text(page))
    assert t == "Rules\nPoints: 3 per QSO\n"
    page2 = page.replace("<main>", "<div>").replace("</main>", "</div>")
    assert "2026" not in w.tidy(w.html_text(page2)) and "Menu" not in w.html_text(page2)


def test_pdf_links():
    page = ('<a href="/rules/rules_2026.pdf">x</a> <a href="http://other.org/a.PDF?x=1">y</a>'
            '<a href="/rules/">z</a>')
    assert w.pdf_links(page, "https://www.cq160.com/rules/").split("\n") == [
        "https://other.org/a.PDF", "https://www.cq160.com/rules/rules_2026.pdf"]


def test_check_and_issue(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "SNAP_DIR", tmp_path)
    doc = {"id": "cqww", "url": "https://example.org/rules", "contests": ["cqww-ssb", "cqww-cw"],
           "checked": "2026-11-03"}
    w.snapshot_path(doc).write_text(w.counts_text(w.tokens(doc, w.tidy(RULES))), encoding="utf-8")
    same = w.check([doc], fetch_text=lambda d: w.tidy(RULES.replace(" plus", "\nplus")))
    assert same[0]["status"] == "same" and w.issue_for(same[0]) is None
    new = w.tidy(RULES.replace("three (3)", "four (4)"))
    res = w.check([doc], fetch_text=lambda d: new)[0]
    assert res["status"] == "changed"
    title, body = w.issue_for(res)
    assert title == "Wächter: Ausschreibung geändert – CQ WW DX SSB, CQ WW DX CW"
    assert "**Neu:** 4 four" in body and "**Weggefallen:** 3 three" in body
    assert "V. POINTS: Contacts between stations on different continents count four (4) points." in body
    assert "III. BANDS" not in body                 # nur Zeilen mit neuen Wörtern

    def boom(d):
        raise RuntimeError("HTTPError: 404")
    err = w.check([doc], fetch_text=boom)[0]
    assert err["status"] == "error"
    assert w.issue_for(err)[0].startswith("Wächter: Ausschreibung nicht erreichbar")
    missing = w.check([dict(doc, id="neu")], fetch_text=lambda d: new)[0]
    assert missing["status"] == "new" and w.issue_for(missing) is None


def test_hyphenation_does_not_matter():
    a = "Use of any non-amateur means. Sub-category CW-only."
    b = "Use of any non-\namateur means. Sub­category CW-\n only."
    c = "Use of any nonamateur means. Subcategory CWonly."
    assert w.fingerprint(a) == w.fingerprint(b) == w.fingerprint(c)


def test_open_issues_no_duplicates(tmp_path, monkeypatch):
    """Meldungen: keine doppelten, unveränderte Dokumente erzeugen keine."""
    import json
    monkeypatch.setattr(w, "SNAP_DIR", tmp_path)
    calls = []

    def fake_gh(*args):
        calls.append(args)
        if args[:2] == ("issue", "list"):
            return json.dumps([{"title": "Wächter: Ausschreibung nicht erreichbar – iaru-x"}])
        return ""
    monkeypatch.setattr(w, "gh", fake_gh)
    d1 = {"id": "a", "url": "u1", "contests": ["cqww-ssb"]}
    d2 = {"id": "b", "url": "u2", "contests": ["iaru-x"]}
    d3 = {"id": "c", "url": "u3", "contests": ["cqww-cw"]}
    for d in (d1, d3):
        w.snapshot_path(d).write_text(w.counts_text(w.tokens(d, w.tidy(RULES))), encoding="utf-8")

    def fetch(d):
        if d["id"] == "b":
            raise RuntimeError("timeout")
        return w.tidy(RULES.replace("three", "four")) if d["id"] == "a" else w.tidy(RULES)
    w.open_issues(w.check([d1, d2, d3], fetch_text=fetch))
    created = [c for c in calls if c[:2] == ("issue", "create")]
    assert len(created) == 1
    assert created[0][3] == "Wächter: Ausschreibung geändert – CQ WW DX SSB"


def test_snapshot_is_word_list_only(tmp_path, monkeypatch):
    """Vergleichsstand enthält keinen lesbaren Text der Ausschreibung, nur Wörter mit Anzahl."""
    monkeypatch.setattr(w, "SNAP_DIR", tmp_path)
    monkeypatch.setattr(w, "DOCS", tmp_path / "documents.json")
    doc = {"id": "x", "url": "u", "contests": ["cqww-ssb"]}
    data = {"documents": [doc]}
    w.update(w.check([doc], fetch_text=lambda d: w.tidy(RULES)), data)
    snap = (tmp_path / "x.words").read_text(encoding="utf-8")
    assert "RS report plus" not in snap and "three\t1\n" in snap
    assert w.read_counts(tmp_path / "x.words") == w.tokens(doc, RULES)
    assert data["documents"][0]["checked"] and data["documents"][0]["fingerprint"]


def test_pdf_links_issue(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "SNAP_DIR", tmp_path)
    doc = {"id": "l", "url": "https://www.cq160.com/rules/", "watch": "pdf_links",
           "contests": ["cq160-cw"]}
    old = "https://www.cq160.com/rules/rules_cq160_2026.pdf\n"
    w.snapshot_path(doc).write_text(w.counts_text(w.tokens(doc, old)), encoding="utf-8")
    res = w.check([doc], fetch_text=lambda d: "https://www.cq160.com/rules/rules_cq160_2027.pdf\n")[0]
    title, body = w.issue_for(res)
    assert "neue Ausschreibung" in body and "rules_cq160_2027.pdf" in body
    assert "**Weggefallen:**\nhttps://www.cq160.com/rules/rules_cq160_2026.pdf" in body


def test_license_page_issue(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "SNAP_DIR", tmp_path)
    doc = {"id": "gnu", "kind": "license", "name": "GNU-Lizenzen (GPL)",
           "url": "https://example.org/licenses", "watch": "text", "contests": []}
    old = "The GNU General Public License version 3"
    w.snapshot_path(doc).write_text(w.counts_text(w.tokens(doc, old)), encoding="utf-8")
    res = w.check([doc], fetch_text=lambda d: old + " and version 4")[0]
    assert res["status"] == "changed"
    title, body = w.issue_for(res)
    assert title == "Wächter: Lizenzseite geändert – GNU-Lizenzen (GPL)"
    assert "GPL-3.0-only" in body and "4" in body
    same = w.check([doc], fetch_text=lambda d: old)[0]
    assert w.issue_for(same) is None
    err = w.issue_for({"doc": doc, "status": "error", "error": "HTTP 404"})
    assert err[0] == "Wächter: Lizenzseite nicht erreichbar – GNU-Lizenzen (GPL)"
