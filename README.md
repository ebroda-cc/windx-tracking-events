# windx-tracking-events

Ereignisdiskrete Simulation (Discrete Event Simulation) des Transports von
Rotorblättern einer Windenergieanlage vom Produzenten zum Hafen. Es können
mehrere Transporte gleichzeitig/zeitversetzt gestartet werden; jede Station
auf dem Weg erzeugt zu ihrer Zeit ein Tracking-Event, das sowohl als
**EDI-Nachricht (EDIFACT IFTSTA)** als auch als **GS1-EPCIS-2.0-Event**
(JSON-LD) dargestellt wird.

## Konzept

### Simulationskern (`windx_tracking/des.py`)

Ein minimaler, abhängigkeitsfreier DES-Kern auf Basis eines Min-Heaps
(`heapq`). Zwei Arten von Arbeit können eingeplant werden:

- `sim.schedule(delay, callback)` — einfacher, verzögerter Funktionsaufruf
- `sim.process(generator)` — ein generator-basierter *Prozess*, der per
  `yield <minuten>` seine Ausführung pausiert und automatisch fortgesetzt
  wird, sobald die Simulationszeit entsprechend fortgeschritten ist

Jeder Transport ist ein solcher Prozess (`windx_tracking/transport.py`),
was es erlaubt, den Weg entlang der Route als einfache, lineare Funktion
zu schreiben, statt die Ereigniswarteschlange von Hand zu verwalten.

### Route (`windx_tracking/route.py`)

Für diese erste Version ist die Route für alle Transporte identisch:

1. **Werk** (Rotorblattwerk) — Verladung auf Schwerlast-Trailer
2. **Kontrollstelle** — Kontrolle/Wiegung des Großraumtransports
3. **Nachtlager** — Zwischenstopp wegen gesetzlichem Nachtfahrverbot für
   Schwertransporte
4. **Hafen-Gate** (Cuxhaven) — Gate-In / Zollformalitäten
5. **Hafen-Lagerfläche** (Cuxhaven) — Zwischenlagerung bis zur
   Verladung auf das Seeschiff

Fahrzeiten zwischen Stationen ergeben sich aus Distanz und
Durchschnittsgeschwindigkeit der Teilstrecke plus Zufallsstreuung;
Verweildauern je Station werden aus einer Dreiecksverteilung gezogen
(z. B. 8–10 h Übernachtung am Nachtlager, 12–48 h Wartezeit auf das
Schiff im Hafen).

An jeder Station werden i. d. R. zwei Events erzeugt (Ankunft, Abfahrt);
am Werk zusätzlich ein `PICKUP`-Ereignis zu Beginn, am Zielhafen ein
abschließendes `LOADED_ON_VESSEL` statt einer Abfahrt.

Hinweis: UN/LOCODEs und GLNs der Zwischenstationen sind zu
Demonstrationszwecken frei erfunden. Cuxhaven (`DECUX`) ist ein echter,
für den Export von Windenergieanlagen-Komponenten genutzter Hafen.

### Event-Darstellungen (`windx_tracking/formatters/`)

- **`edi.py`**: vereinfachte UN/EDIFACT-**IFTSTA**-Nachricht (der
  Standardnachrichtentyp für multimodale Transport-Statusmeldungen) mit
  Segmenten wie `UNB`, `BGM`, `LOC`, `STS`, `RFF`, `UNT`.
- **`epcis.py`**: **GS1 EPCIS 2.0** `ObjectEvent` als JSON-LD, mit
  `epcList` (fiktive SGTIN-EPCs je Rotorblatt), `bizStep`/`disposition`
  aus dem GS1-CBV-Vokabular sowie `bizLocation`/`readPoint` als SGLN.
  Zusätzliche, simulationsspezifische Felder (Sendungs-ID, Spediteur, ...)
  liegen im eigenen `windx:`-Namespace.

Beide Formate sind bewusst vereinfacht/illustrativ (keine vollständige
Codeliste, keine echten GS1-Präfixe) — die Struktur folgt aber den
jeweiligen realen Standards.

## Verwendung

```bash
# 3 Transporte simulieren, Events auf der Konsole ausgeben
python -m windx_tracking --transports 3

# 5 Transporte, 4 Stunden Startabstand, EDI/EPCIS-Dateien schreiben
python -m windx_tracking --transports 5 --interval-minutes 240 --output-dir out
```

Für jedes Event werden dabei `<Sendung>_<Nr>_<Typ>.edi` und
`<Sendung>_<Nr>_<Typ>.epcis.json` geschrieben, zusätzlich ein
`all_events.epcis.json` mit allen Events chronologisch in einem
EPCISDocument.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
