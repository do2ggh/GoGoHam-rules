#!/usr/bin/env python3
"""Wächter: prüft, ob sich offizielle Contest-Ausschreibungen geändert haben.

Watchdog: checks whether official contest rules have changed.

    python3 watch/watch_rules.py            prüfen, Bericht ausgeben (ändert nichts)
    python3 watch/watch_rules.py --update   aktuellen Stand als neuen Vergleichsstand speichern
                                            (nach dem Anpassen der Regel-Dateien)
    python3 watch/watch_rules.py --issues   prüfen und bei Änderungen eine GitHub-Meldung
                                            (Issue) anlegen – so läuft es in GitHub Actions

Die Liste der Dokumente steht in watch/documents.json, der zuletzt geprüfte Stand je
Dokument in watch/snapshots/ – nur als Wortliste mit Anzahl, nicht als lesbarer Text
(die Ausschreibungen gehören den Veranstaltern). Verglichen werden die Wörter und Zahlen, nicht die Zeilen –
ein anderer Zeilenumbruch (andere pdftotext-Version) löst also keinen Alarm aus.

Arten („watch“):
  text       – der ganze Text des Dokuments (HTML-Seite oder PDF)
  pdf_links  – nur die Liste der verlinkten PDF-Dateien einer Übersichtsseite
               (für Ausschreibungen, die jedes Jahr als neues PDF erscheinen)

Lizenzseiten („kind“: „license“, mit „name“, ohne Contests): Übersichtsseiten von GNU und
Creative Commons – meldet sich, wenn dort z. B. eine neue Version der GPL oder von CC BY
erscheint. GoGoHam bleibt bei GPL-3.0-only und CC BY 4.0, bis über eine Umstellung
entschieden ist.

Nur Python-Standardbibliothek; für PDFs wird pdftotext (poppler) gebraucht.

© 2026 Franz, DO2GGH · gogoham@bluemailx.com · Lizenz: GPL-3.0
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DOCS = HERE / "documents.json"
SNAP_DIR = HERE / "snapshots"
USER_AGENT = "GoGoHam-rules-watch/1.0 (+https://github.com/do2ggh/GoGoHam-rules)"
LABEL = "wächter"
MAX_LINES = 40          # Zeilen mit neuen Wörtern in der Meldung
MAX_WORDS = 80


# ------------------------------------------------------------------ Text gewinnen
def fetch(url: str, tries: int = 3, timeout: int = 40) -> tuple[bytes, str]:
    """Dokument laden (mit Wiederholung). Ergebnis: (Inhalt, Content-Type)."""
    last: Exception | None = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except Exception as e:          # noqa: BLE001 – jede Art Fehler: nochmal versuchen
            last = e
            if n + 1 < tries:
                time.sleep(10 * (n + 1))
    raise RuntimeError(f"{type(last).__name__}: {last}")


def is_pdf(data: bytes, ctype: str) -> bool:
    return data[:5] == b"%PDF-" or "pdf" in ctype.lower()


def pdf_text(data: bytes) -> str:
    r = subprocess.run(["pdftotext", "-enc", "UTF-8", "-", "-"], input=data,
                       capture_output=True, check=True)
    return r.stdout.decode("utf-8", "replace")


_DROP = re.compile(r"<(script|style|noscript|svg|nav|header|footer|form)\b.*?</\1\s*>",
                   re.S | re.I)
_BLOCK = re.compile(r"<(br|p|div|li|tr|h[1-6]|table|ul|ol|section|article)\b[^>]*>", re.I)


def html_text(raw: str) -> str:
    """Lesbarer Text einer Webseite – ohne Skripte, Menüs, Kopf- und Fußzeile."""
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    m = re.search(r"<(main|article)\b.*?</\1\s*>", raw, re.S | re.I)
    if m:
        raw = m.group(0)
    raw = _DROP.sub(" ", raw)
    raw = _BLOCK.sub("\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(raw)
    # Fußzeile („Copyright © 2008-2026 …“) weglassen – sie ändert sich jeden Januar
    return re.split(r"\bCopyright\s*(?:©|\(c\))", text, maxsplit=1, flags=re.I)[0]


def pdf_links(raw: str, base: str) -> str:
    """Alle verlinkten PDF-Dateien einer Seite, sortiert, eine je Zeile."""
    links = set()
    for href in re.findall(r"""href\s*=\s*["']([^"']+\.pdf)(?:[?#][^"']*)?["']""", raw, re.I):
        links.add(urllib.parse.urljoin(base, html.unescape(href)).replace("http://", "https://"))
    return "\n".join(sorted(links))


def tidy(text: str) -> str:
    """Zeilen säubern (für Schnappschuss und Unterschiede)."""
    text = text.replace("­", "").replace(" ", " ").replace("\r", "\n")
    lines = (re.sub(r"[ \t\f\v]+", " ", ln).strip() for ln in text.split("\n"))
    return "\n".join(ln for ln in lines if ln) + "\n"


def words(text: str) -> list[str]:
    """Wörter und Zahlen – unabhängig von Zeilenumbrüchen und Silbentrennung.

    Bindestriche verbinden: „non-amateur“, „non-⏎amateur“ und „nonamateur“ sind dasselbe
    Wort (je nach pdftotext-Version kommt es verschieden heraus)."""
    t = text.lower().replace("\u00ad", "")
    t = re.sub(r"[-\u2010\u2011]\s*\n\s*", "", t)          # Trennung am Zeilenende
    t = re.sub(r"(?<=\w)[-\u2010\u2011](?=\w)", "", t)      # Bindestrich im Wort
    return re.findall(r"\w+(?:[.,:/]\w+)*", t)


def tokens(doc: dict, text: str) -> Counter:
    """Was verglichen wird: Wörter mit Anzahl – bei „pdf_links“ die einzelnen Links."""
    if doc.get("watch") == "pdf_links":
        return Counter(ln for ln in text.splitlines() if ln.strip())
    return Counter(words(text))


def counts_text(c: Counter) -> str:
    """Vergleichsstand als Datei: je Zeile „Wort<Tab>Anzahl“, sortiert.

    Bewusst nur eine Wortliste und kein lesbarer Text – die Ausschreibungen gehören den
    Veranstaltern und werden hier nicht weiterveröffentlicht."""
    return "".join(f"{w}\t{n}\n" for w, n in sorted(c.items()))


def read_counts(path: Path) -> Counter:
    c: Counter = Counter()
    for ln in path.read_text(encoding="utf-8").splitlines():
        w, _, n = ln.rpartition("\t")
        if w:
            c[w] = int(n)
    return c


def fingerprint(text: str, doc: dict | None = None) -> str:
    """Prüfsumme über die Wörter (als Menge mit Anzahl – auch unabhängig von der
    Reihenfolge, falls pdftotext Spalten anders liest)."""
    return hashlib.sha256(counts_text(tokens(doc or {}, text)).encode("utf-8")).hexdigest()


def current_text(doc: dict) -> str:
    data, ctype = fetch(doc["url"])
    kind = doc.get("watch", "text")
    if kind == "pdf_links":
        return tidy(pdf_links(data.decode("utf-8", "replace"), doc["url"]))
    if is_pdf(data, ctype):
        return tidy(pdf_text(data))
    return tidy(html_text(data.decode("utf-8", "replace")))


# ------------------------------------------------------------------ Vergleich
def snapshot_path(doc: dict) -> Path:
    return SNAP_DIR / f"{doc['id']}.words"


def word_changes(old: Counter, new: Counter) -> tuple[list[str], list[str]]:
    return sorted((old - new).elements()), sorted((new - old).elements())


def context_lines(doc: dict, text: str, added: list[str]) -> list[str]:
    """Zeilen der neuen Ausschreibung, in denen neue Wörter vorkommen."""
    want = set(added)
    out = [ln for ln in text.splitlines() if want & set(tokens(doc, ln))]
    if len(out) > MAX_LINES:
        out = out[:MAX_LINES] + [f"… ({len(out) - MAX_LINES} weitere Zeilen)"]
    return out


def contest_names(ids: list[str]) -> str:
    names = []
    for cid in ids:
        try:
            names.append(json.loads((REPO / f"{cid}.json").read_text(encoding="utf-8"))["name"])
        except (OSError, ValueError, KeyError):
            names.append(cid)
    return ", ".join(names)


def check(docs: list[dict], fetch_text=current_text) -> list[dict]:
    """Ergebnis je Dokument: {"doc", "status": same|changed|new|error, …}."""
    out = []
    for doc in docs:
        res = {"doc": doc}
        try:
            text = fetch_text(doc)
        except Exception as e:          # noqa: BLE001
            res.update(status="error", error=str(e))
            out.append(res)
            continue
        res["text"] = text
        snap = snapshot_path(doc)
        if not snap.is_file():
            res["status"] = "new"
        else:
            old = read_counts(snap)
            res["status"] = "same" if old == tokens(doc, text) else "changed"
            res["old"] = old
        out.append(res)
    return out


# ------------------------------------------------------------------ Bericht / Meldung
def issue_for(res: dict) -> tuple[str, str] | None:
    doc = res["doc"]
    if doc.get("kind") == "license":
        return license_issue(res)
    names = contest_names(doc["contests"])
    if res["status"] == "error":
        title = f"Wächter: Ausschreibung nicht erreichbar – {names}"
        body = (f"Das Dokument **{doc['url']}** ließ sich auch nach drei Versuchen nicht laden:\n\n"
                f"```\n{res['error']}\n```\n\n"
                "Vielleicht ist die Seite nur kurz gestört – oder die Ausschreibung ist umgezogen. "
                "Bitte im Browser nachsehen und ggf. den Link in `watch/documents.json` anpassen.")
        return title, body
    if res["status"] != "changed":
        return None
    gone, added = word_changes(res["old"], tokens(doc, res["text"]))
    title = f"Wächter: Ausschreibung geändert – {names}"
    links = doc.get("watch") == "pdf_links"
    what = ("Die Liste der verlinkten PDF-Dateien hat sich geändert – vermutlich ist eine "
            "neue Ausschreibung (z. B. für das nächste Jahr) erschienen." if links else
            "Der Text der Ausschreibung hat sich geändert.")
    sep = "\n" if links else " "
    ctx = "\n".join(context_lines(doc, res["text"], added))
    body = (f"{what}\n\n**Dokument:** {doc['url']}\n**Betrifft:** {names} "
            f"(`{'`, `'.join(doc['contests'])}`)\n**Zuletzt geprüft:** {doc.get('checked', '?')}\n\n"
            f"**Weggefallen:**{sep}{sep.join(gone[:MAX_WORDS]) or '–'}\n\n"
            f"**Neu:**{sep}{sep.join(added[:MAX_WORDS]) or '–'}\n\n")
    if ctx and not links:
        body += (f"<details><summary>Zeilen der neuen Fassung mit neuen Wörtern</summary>\n\n"
                 f"```\n{ctx}\n```\n</details>\n\n")
    body += ("**Was tun?** Ausschreibung lesen, Regel-Datei(en) bei Bedarf anpassen (Revision +1, "
             "`rules_checked`), dann `python3 watch/watch_rules.py --update` ausführen und alles "
             "hochladen. Danach diese Meldung schließen.")
    return title, body


def license_issue(res: dict) -> tuple[str, str] | None:
    """Meldung für eine überwachte Lizenzseite (GNU, Creative Commons)."""
    doc = res["doc"]
    name = doc.get("name", doc["id"])
    if res["status"] == "error":
        return (f"Wächter: Lizenzseite nicht erreichbar – {name}",
                f"Die Seite **{doc['url']}** ließ sich auch nach drei Versuchen nicht laden:\n\n"
                f"```\n{res['error']}\n```\n\nBitte im Browser nachsehen und ggf. den Link in "
                "`watch/documents.json` anpassen.")
    if res["status"] != "changed":
        return None
    gone, added = word_changes(res["old"], tokens(doc, res["text"]))
    ctx = "\n".join(context_lines(doc, res["text"], added))
    body = (f"Die Lizenzseite **{name}** hat sich geändert – vielleicht gibt es eine neue "
            f"Lizenzversion, vielleicht nur eine kleine Textänderung.\n\n**Seite:** {doc['url']}\n"
            f"**Zuletzt geprüft:** {doc.get('checked', '?')}\n\n"
            f"**Weggefallen:** {' '.join(gone[:MAX_WORDS]) or '–'}\n\n"
            f"**Neu:** {' '.join(added[:MAX_WORDS]) or '–'}\n\n")
    if ctx:
        body += (f"<details><summary>Zeilen mit neuen Wörtern</summary>\n\n"
                 f"```\n{ctx}\n```\n</details>\n\n")
    body += ("**Was tun?** Nachsehen, ob eine neue Version der GPL bzw. von CC BY erschienen ist. "
             "GoGoHam steht unter **GPL-3.0-only**, die Regel-Dateien unter **CC BY 4.0** – das "
             "bleibt so, bis entschieden ist, ob umgestellt wird. Danach "
             "`python3 watch/watch_rules.py --update` ausführen, hochladen und diese Meldung schließen.")
    return f"Wächter: Lizenzseite geändert – {name}", body


def report(results: list[dict]) -> str:
    sym = {"same": "✓ unverändert", "changed": "✗ GEÄNDERT", "new": "• neu (noch kein Vergleichsstand)",
           "error": "! nicht erreichbar"}
    lines = []
    for r in results:
        d = r["doc"]
        extra = f" – {r['error']}" if r["status"] == "error" else ""
        lines.append(f"{sym[r['status']]:<36} {d['id']:<16} {d['url']}{extra}")
    return "\n".join(lines)


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def open_issues(results: list[dict]) -> None:
    gh("label", "create", LABEL, "--color", "e08a00", "--force",
       "--description", "Ausschreibung geändert oder nicht erreichbar")
    existing = {i["title"] for i in json.loads(
        gh("issue", "list", "--state", "open", "--label", LABEL, "--limit", "200",
           "--json", "title"))}
    for r in results:
        it = issue_for(r)
        if it is None:
            continue
        title, body = it
        if title in existing:
            print(f"Meldung gibt es schon: {title}")
            continue
        gh("issue", "create", "--title", title, "--body", body, "--label", LABEL)
        print(f"Meldung angelegt: {title}")


def update(results: list[dict], docs_data: dict) -> None:
    SNAP_DIR.mkdir(exist_ok=True)
    today = _dt.date.today().isoformat()
    for r in results:
        if r["status"] == "error":
            print(f"übersprungen (nicht erreichbar): {r['doc']['id']}")
            continue
        counts = tokens(r["doc"], r["text"])
        snapshot_path(r["doc"]).write_text(counts_text(counts), encoding="utf-8")
        r["doc"]["checked"] = today
        r["doc"]["fingerprint"] = hashlib.sha256(counts_text(counts).encode()).hexdigest()
    DOCS.write_text(json.dumps(docs_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--update", action="store_true", help="Vergleichsstand neu speichern")
    ap.add_argument("--issues", action="store_true", help="GitHub-Meldungen anlegen")
    ap.add_argument("ids", nargs="*", help="nur diese Dokumente (id aus documents.json)")
    a = ap.parse_args(argv)
    data = json.loads(DOCS.read_text(encoding="utf-8"))
    docs = [d for d in data["documents"] if not a.ids or d["id"] in a.ids]
    results = check(docs)
    print(report(results))
    if a.update:
        update(results, data)
        print("Vergleichsstand gespeichert.")
        return 0
    if a.issues:
        open_issues(results)
    return 1 if any(r["status"] in ("changed", "error") for r in results) and not a.issues else 0


if __name__ == "__main__":
    sys.exit(main())
