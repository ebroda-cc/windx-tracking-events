"""Generischer ereignisdiskreter Simulationskern (Discrete Event Simulation).

Die Simulationszeit ist eine einheitenlose ``float`` (in diesem Projekt in
Minuten interpretiert). Es gibt zwei Arten, Arbeit einzuplanen:

* einfache Callbacks ueber :meth:`Simulation.schedule`
* generator-basierte *Prozesse* ueber :meth:`Simulation.process`. Ein
  Prozess kann per ``yield <delay>`` eine Verzoegerung anfordern, nach der
  er automatisch fortgesetzt wird. Das erlaubt es, den Weg eines
  Transports entlang mehrerer Stationen als einfache, lineare Funktion zu
  schreiben, ohne die Ereignis-Warteschlange von Hand zu verwalten.
"""

from __future__ import annotations

import heapq
import itertools
from typing import Any, Callable, Generator, Optional

ProcessGenerator = Generator[float, None, None]


class Simulation:
    """Ereigniswarteschlange (Min-Heap) plus Simulationsuhr."""

    def __init__(self) -> None:
        self._queue: list[tuple[float, int, Callable[[], None]]] = []
        self._counter = itertools.count()
        self.now: float = 0.0

    def schedule(self, delay: float, callback: Callable[[], None]) -> float:
        """Plant ``callback`` in ``delay`` Zeiteinheiten ab jetzt ein."""
        if delay < 0:
            raise ValueError("delay muss >= 0 sein")
        event_time = self.now + delay
        heapq.heappush(self._queue, (event_time, next(self._counter), callback))
        return event_time

    def process(self, generator: ProcessGenerator) -> None:
        """Startet einen generator-basierten Prozess sofort."""
        self._advance(generator, None)

    def _advance(self, generator: ProcessGenerator, value: Optional[Any]) -> None:
        try:
            delay = generator.send(value)
        except StopIteration:
            return
        self.schedule(delay, lambda: self._advance(generator, None))

    def run(self, until: Optional[float] = None) -> None:
        """Verarbeitet Ereignisse in Zeitreihenfolge bis die Warteschlange
        leer ist (oder ``until`` erreicht wurde)."""
        while self._queue:
            if until is not None and self._queue[0][0] > until:
                break
            time, _, callback = heapq.heappop(self._queue)
            self.now = time
            callback()
