"""AAS-Anbindung (Asset Administration Shell, Metamodell V3 / API V3.1).

Baut fuer jeden Transport eine Asset Administration Shell (Asset = die
Sendung) und fuer jedes Tracking-Event ein eigenes Submodel, und laedt
beides -- je nach Station -- auf den fuer diese Location zustaendigen
AAS-Server hoch (siehe :mod:`windx_tracking.aas.server`).
"""

from .builder import build_event_submodel, build_shipment_shell
from .server import AasServerClient, AasServerRegistry

__all__ = [
    "build_event_submodel",
    "build_shipment_shell",
    "AasServerClient",
    "AasServerRegistry",
]
