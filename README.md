# GoGoHam – Contest-Regeln / contest rules

Die offiziellen Contest-Regeln für **GoGoHam by DO2GGH**, einen Contest-Logger für Linux.
GoGoHam lädt neue und geänderte Regeln automatisch von hier – ohne neue Programmversion.

*The official contest rules for **GoGoHam by DO2GGH**, a contest logger for Linux.
GoGoHam downloads new and changed rules from here automatically.*

Jede Datei beschreibt einen Contest: Bänder, Betriebsarten, Austausch, Punkte, Multis,
Dupe-Regel, Wertung, Termin, verlangtes Log-Format und Standard-Spalten.
Die Rechenwege (z. B. WPX-Präfix, Entfernung zwischen Locatoren) stehen im Programm –
die Datei sagt nur, *welche* Bausteine ein Contest benutzt und *mit welchen Zahlen*.

*Each file describes one contest (bands, modes, exchange, points, multipliers, dupe rule,
scoring, schedule, required log format, default columns). The calculations themselves live
in the program; a file only says which building blocks a contest uses and with which numbers.*

## Contests

| Datei | Contest | Revision | geprüft |
|---|---|---|---|
| `cqww-ssb.json` | CQ WW DX SSB | 1 | 2026-11 |
| `cqww-cw.json` | CQ WW DX CW | 1 | 2026-11 |
| `wpx-ssb.json` | CQ WPX SSB | 1 | 2026-11 |
| `wpx-cw.json` | CQ WPX CW | 1 | 2026-11 |
| `ww-digi.json` | WW Digi DX (FT4/FT8) | 1 | 2026-11 |

`index.json` ist das Inhaltsverzeichnis (Revision und SHA-256-Prüfsumme je Datei), das
GoGoHam zuerst abfragt. *`index.json` is the table of contents GoGoHam reads first.*

## Format

Die Schlüssel sind englisch, damit Funkamateure aus aller Welt Regeln beisteuern können.
Alle Angaben sind im GoGoHam-Handbuch (Kapitel „Regel-Dateien“) erklärt. Kurz:

| Key | Bedeutung / meaning |
|---|---|
| `format` | Format-Version (1) |
| `revision` | Stand der Datei – bei jeder Änderung +1 / increase by 1 on every change |
| `id`, `name`, `cabrillo_name` | Kurzname, Anzeigename, Contest-Name im Cabrillo-Log |
| `rules_url`, `rules_checked` | offizielle Ausschreibung, zuletzt geprüft (JJJJ-MM) |
| `schedule` | Termin: `weekend: last_full`, `month`, `start_hour` (UTC), `hours` |
| `operating_time` | Betriebszeit-Grenze Single-OP (`single_op_hours`, `classic_hours`, `min_break_minutes`) |
| `bands`, `modes`, `rig_modes` | Bänder (`160` … `2`, `70cm` … `3cm`), Modes `PH CW RY DG` |
| `dupe` | `band` oder `band_mode` |
| `exchange` | `rst` + eines von `cq_zone`, `serial`, `grid4` |
| `points` | `fixed`, `continent` (`own_country`, `same_continent`, `same_continent_na`, `other_continent`), `distance` (`base`, `per_km`) – Zahl oder Tabelle je Band mit `default` |
| `multipliers` | `cq_zone`, `country`, `wpx_prefix`, `grid_field` – `per`: `band` oder `once` |
| `score` | `points_x_mults` |
| `log_format` | `cabrillo`, `adif` (`edi` geplant) |
| `columns` | Standard-Spalten der Log-Tabelle |

## Mitmachen / contributing

Fehler gefunden oder ein Contest fehlt? Bitte ein *Issue* öffnen – am besten mit Link zur
offiziellen Ausschreibung. *Found a mistake or missing a contest? Please open an issue,
ideally with a link to the official rules.*

## Lizenz / license

© 2026 Franz, DO2GGH · gogoham@bluemailx.com

Diese Regel-Dateien stehen unter der **Creative Commons Namensnennung 4.0 International
(CC BY 4.0)** – siehe [`LICENSE`](LICENSE). Jede Nutzung ist erlaubt, auch in anderen
Programmen, solange „GoGoHam / DO2GGH“ als Quelle genannt wird.

*These rule files are licensed under **CC BY 4.0** – see [`LICENSE`](LICENSE). Any use is
permitted, also in other programs, as long as "GoGoHam / DO2GGH" is credited.*
