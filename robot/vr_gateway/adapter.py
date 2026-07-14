"""Thin transport adapter that wires raw JSON strings to :class:`VrGateway`.

The adapter owns no safety decisions. When a raw JSON string cannot be decoded,
the adapter routes an opaque sentinel through ``VrGateway.handle`` so the
gateway's existing fail-closed path emits the ``INVALID_PAYLOAD`` rejection
(and any elapsed-deadline events) rather than the adapter synthesizing a safety
event itself. Accepted commands decode to a DTO and are passed directly to
``VrGateway.handle``. Output events are encoded in the original gateway order.
"""
from __future__ import annotations

from robot.vr_gateway import wire
from robot.vr_gateway.gateway import VrGateway


class _Unparseable:
    """Opaque sentinel routed through the gateway fail-closed path."""


_UNPARSEABLE = _Unparseable()


class VrGatewayAdapter:
    """Bridge raw JSON strings to a :class:`VrGateway` instance."""

    def __init__(self, gateway: VrGateway) -> None:
        self._gateway = gateway

    def handle_command(self, raw: str) -> list[str]:
        """Decode ``raw`` and return the gateway's events as JSON strings.

        Decode failures never raise: the malformed input is routed through
        ``VrGateway.handle`` so the gateway's fail-closed path produces the
        appropriate rejection (and any elapsed deadline) events.
        """
        try:
            command = wire.decode_command(raw)
        except wire.WireError:
            command = _UNPARSEABLE  # type: ignore[assignment]
        events = self._gateway.handle(command)
        return wire.encode_events(events)

    def poll(self) -> list[str]:
        """Return the gateway's timer events (``poll()``) as JSON strings."""
        events = self._gateway.poll()
        return wire.encode_events(events)