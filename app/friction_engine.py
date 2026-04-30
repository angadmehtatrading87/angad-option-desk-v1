from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class FrictionDecision:
    expected_edge_usd: float
    friction_usd: float
    net_edge_usd: float
    tradable: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_trade_economics(
    notional_usd: float,
    expected_move_bps: float,
    spread_bps: float,
    admin_fee_usd: float = 0.0,
    financing_usd: float = 0.0,
    min_net_edge_usd: float = 75.0,
) -> FrictionDecision:
    expected_edge = notional_usd * (expected_move_bps / 10000.0)
    friction = notional_usd * (spread_bps / 10000.0) + admin_fee_usd + financing_usd
    net_edge = expected_edge - friction
    edge_to_friction = (expected_edge / friction) if friction > 0 else 0.0
    tradable = net_edge >= min_net_edge_usd and edge_to_friction >= 1.35
    notes = [
        f"notional={notional_usd:.2f}",
        f"expected_edge={expected_edge:.2f}",
        f"friction={friction:.2f}",
        f"edge_to_friction={edge_to_friction:.2f}",
    ]
    return FrictionDecision(round(expected_edge, 2), round(friction, 2), round(net_edge, 2), tradable, notes)
