# windx-tracking-events

Ereignisdiskrete Simulation (Discrete Event Simulation) des Transports von
Rotorblättern einer Windenergieanlage vom Produzenten zum Hafen. Es können
mehrere Transporte gleichzeitig/zeitversetzt gestartet werden; jede Station
auf dem Weg erzeugt zu ihrer Zeit ein Tracking-Event, das als
**EDI-Nachricht (EDIFACT IFTSTA)**, als **GS1-EPCIS-2.0-Event** (JSON-LD)
und als **Asset Administration Shell (AAS, Metamodell V3 / API V3.1)**
dargestellt und optional auf einen — je Location konfigurierbaren —
AAS-Server hochgeladen wird.

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

EDI und EPCIS sind bewusst vereinfacht/illustrativ (keine vollständige
Codeliste, keine echten GS1-Präfixe) — die Struktur folgt aber den
jeweiligen realen Standards.

### AAS-Anbindung (`windx_tracking/aas/`)

Jeder Transport bekommt genau eine **Asset Administration Shell** (Asset =
die Sendung, mit `globalAssetId` und `specificAssetId` je Blatt-
Seriennummer), jedes Tracking-Event ein eigenes **Submodel** (Pendant zu
EDI/EPCIS), das der Shell per Submodel-Referenz angehängt wird. Aufbau der
AAS-Objekte erfolgt mit dem offiziellen
[`basyx-python-sdk`](https://github.com/eclipse-basyx/basyx-python-sdk)
(Metamodell V3), die JSON-Serialisierung entspricht damit direkt dem
Schema, das eine AAS-API V3.1 erwartet.

- **`builder.py`** — baut Shell und Event-Submodels (`semanticId`-Verweise
  liegen wie bei EPCIS in einem eigenen, fiktiven `windx:`-Namespace).
- **`server.py`** — `AasServerRegistry` ordnet jeder Station/Location ihre
  eigene AAS-Server-Basis-URL zu (Default in `route.py` je Station, per
  JSON-Datei überschreibbar); `AasServerClient` ist ein schlanker
  HTTP-Client für die Standard-Endpunkte `POST/PUT /shells`,
  `POST/PUT /submodels` und `POST /shells/{id}/submodel-refs` (IDTA
  "Details of the AAS Part 2: APIs", Shell-/Submodel-Repository, V3.0/V3.1
  — die Kern-CRUD-Endpunkte sind zwischen beiden Versionen unverändert).
- **`pipeline.py`** — verbindet beides: pro Event wird an dem für die
  jeweilige Station zuständigen Server die Shell bei Bedarf angelegt
  (create-if-missing) und das Event-Submodel hochgeladen bzw. verlinkt.
  Da jede Station ihren eigenen Server haben kann, entsteht dort jeweils
  eine **lokale Kopie** der (identisch identifizierten) Shell, ergänzt um
  die an dieser Location erzeugten Submodels — passend zu einem später
  angebundenen Dataspace-Szenario, in dem jede Location ihre AAS über
  einen eigenen EDC-Connector anbietet.

Jede Station kann so grundsätzlich einen eigenen, unabhängigen
AAS-Server betreiben (siehe `Station.aas_server_url` in `route.py`).

## Verwendung

```bash
# 3 Transporte simulieren, Events auf der Konsole ausgeben
python -m windx_tracking --transports 3

# 5 Transporte, 4 Stunden Startabstand, EDI/EPCIS-Dateien schreiben
python -m windx_tracking --transports 5 --interval-minutes 240 --output-dir out

# AAS-Objekte (Shell je Sendung + Submodel je Event) lokal als JSON ablegen,
# ohne einen AAS-Server anzusprechen
python -m windx_tracking --transports 2 --aas-output-dir out/aas

# ... oder direkt auf die je Location konfigurierten AAS-Server hochladen
python -m windx_tracking --transports 2 --upload-aas \
    --aas-server-config aas-servers.json
```

Für jedes Event werden dabei `<Sendung>_<Nr>_<Typ>.edi` und
`<Sendung>_<Nr>_<Typ>.epcis.json` geschrieben, zusätzlich ein
`all_events.epcis.json` mit allen Events chronologisch in einem
EPCISDocument.

`aas-servers.json` überschreibt die Default-URLs aus `route.py` pro
Station-Code, z. B.:

```json
{
  "STA-FACTORY": "https://factory.example.com/aas",
  "STA-PORT-GATE": "https://port-cuxhaven.example.com/aas"
}
```

## Ausblick: DataSpace-Integration (EDC)

Als nächster Schritt sollen die je Location gehosteten AAS-Server als
**Dataspace Assets** über jeweils zugehörige EDC-Connectoren (Eclipse
Dataspace Components) angeboten werden — d. h. pro Location ein EDC, das
den dortigen AAS-Server (Shells + Submodels) als `Asset` mit
entsprechender `dataAddress` registriert und über Policies/Contract-
Definitions für andere Teilnehmer im Datenraum auffindbar/abrufbar macht.
Die hier bereits pro Station getrennten AAS-Server bilden dafür die
Grundlage; die EDC-Anbindung selbst ist noch nicht implementiert.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
