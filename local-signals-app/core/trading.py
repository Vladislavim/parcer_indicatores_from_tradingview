from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


BLUE_CHIPS = {"BTC", "ETH"}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def symbol_key(symbol: str) -> str:
    raw = str(symbol or "").upper().strip()
    if not raw:
        return ""
    if "/" in raw:
        return raw.split("/", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if raw.endswith(quote) and len(raw) > len(quote):
            return raw[: -len(quote)]
    return raw


def normalize_side(side: str) -> str:
    raw = str(side or "").lower().strip()
    if raw in ("buy", "long"):
        return "buy"
    if raw in ("sell", "short"):
        return "sell"
    return ""


def stop_distance(entry_price: float, stop_price: float) -> float:
    return abs(max(0.0, safe_float(entry_price)) - max(0.0, safe_float(stop_price)))


def stop_distance_pct(entry_price: float, stop_price: float) -> float:
    entry = max(0.0, safe_float(entry_price))
    if entry <= 0:
        return 0.0
    return (stop_distance(entry_price, stop_price) / entry) * 100.0


def normalize_amount(exchange: Any, symbol: str, size: float) -> float:
    qty = max(0.0, safe_float(size))
    if qty <= 0:
        return 0.0

    try:
        normalized = float(exchange.amount_to_precision(symbol, qty))
        if normalized > 0:
            return normalized
    except Exception:
        pass

    key = symbol_key(symbol)
    if key == "BTC":
        return round(qty, 3)
    if key in {"ETH", "SOL"}:
        return round(qty, 2)
    if qty >= 1000:
        return round(qty, 0)
    if qty >= 100:
        return round(qty, 1)
    if qty >= 1:
        return round(qty, 2)
    return round(qty, 4)


@dataclass
class MarketGate:
    ok: bool
    reason: str = ""
    spread_pct: float = 0.0
    quote_volume: float = 0.0
    last_price: float = 0.0


@dataclass
class PortfolioState:
    open_risk_usd: float = 0.0
    gross_exposure_usd: float = 0.0
    same_side_alt_positions: int = 0


@dataclass
class RiskPlan:
    ok: bool
    reason: str = ""
    size: float = 0.0
    notional_usd: float = 0.0
    margin_usd: float = 0.0
    risk_amount_usd: float = 0.0
    stop_distance_pct: float = 0.0
    open_risk_usd: float = 0.0
    gross_exposure_usd: float = 0.0
    portfolio_risk_limit_usd: float = 0.0
    same_side_alt_positions: int = 0


def market_gate_from_ticker(
    ticker: Mapping[str, Any],
    *,
    max_spread_pct: float,
    min_quote_volume: float,
) -> MarketGate:
    bid = safe_float(ticker.get("bid"))
    ask = safe_float(ticker.get("ask"))
    last = safe_float(ticker.get("last") or ticker.get("close"))
    quote_volume = safe_float(ticker.get("quoteVolume"))

    spread_pct = 0.0
    if bid > 0 and ask > 0 and last > 0:
        spread_pct = ((ask - bid) / last) * 100.0
        if spread_pct > max_spread_pct:
            return MarketGate(
                ok=False,
                reason=f"wide spread {spread_pct:.2f}%",
                spread_pct=spread_pct,
                quote_volume=quote_volume,
                last_price=last,
            )

    if quote_volume > 0 and quote_volume < max(0.0, float(min_quote_volume)):
        return MarketGate(
            ok=False,
            reason=f"low quote volume {quote_volume:,.0f}",
            spread_pct=spread_pct,
            quote_volume=quote_volume,
            last_price=last,
        )

    return MarketGate(
        ok=True,
        spread_pct=spread_pct,
        quote_volume=quote_volume,
        last_price=last,
    )


def _tracked_stop_price(
    symbol: str,
    tracked_positions: Optional[Mapping[str, Mapping[str, Any]]],
    exchange_stop: float,
) -> float:
    tracked = tracked_positions or {}
    meta = tracked.get(symbol) or {}
    meta_stop = safe_float(meta.get("sl_price"))
    if meta_stop > 0:
        return meta_stop

    key = symbol_key(symbol)
    if key:
        for tracked_symbol, tracked_meta in tracked.items():
            if symbol_key(str(tracked_symbol or "")) != key:
                continue
            meta_stop = safe_float((tracked_meta or {}).get("sl_price"))
            if meta_stop > 0:
                return meta_stop

    return max(0.0, exchange_stop)


def build_portfolio_state(
    positions: Iterable[Mapping[str, Any]],
    *,
    tracked_positions: Optional[Mapping[str, Mapping[str, Any]]] = None,
    candidate_symbol: str = "",
    candidate_side: str = "",
    fallback_stop_pct: float = 1.8,
) -> PortfolioState:
    open_risk_usd = 0.0
    gross_exposure_usd = 0.0
    same_side_alt_positions = 0

    candidate_key = symbol_key(candidate_symbol)
    normalized_candidate_side = normalize_side(candidate_side)

    for pos in positions or []:
        contracts = safe_float(pos.get("contracts"))
        if contracts <= 0:
            continue

        symbol = str(pos.get("symbol") or "")
        key = symbol_key(symbol)
        side = normalize_side(pos.get("side"))
        entry = safe_float(pos.get("entryPrice") or pos.get("avgPrice"))
        mark = safe_float(pos.get("markPrice") or pos.get("lastPrice") or entry)
        stop = _tracked_stop_price(symbol, tracked_positions, safe_float(pos.get("stopLoss")))
        if stop <= 0 and entry > 0:
            if side == "buy":
                stop = entry * (1.0 - fallback_stop_pct / 100.0)
            elif side == "sell":
                stop = entry * (1.0 + fallback_stop_pct / 100.0)

        gross_exposure_usd += abs(contracts * (mark or entry))
        if entry > 0 and stop > 0:
            open_risk_usd += abs(entry - stop) * abs(contracts)

        if (
            normalized_candidate_side
            and side == normalized_candidate_side
            and key
            and key not in BLUE_CHIPS
            and key != candidate_key
        ):
            same_side_alt_positions += 1

    return PortfolioState(
        open_risk_usd=open_risk_usd,
        gross_exposure_usd=gross_exposure_usd,
        same_side_alt_positions=same_side_alt_positions,
    )


def build_risk_plan(
    *,
    exchange: Any,
    symbol: str,
    side: str,
    entry_price: float,
    stop_price: float,
    leverage: int,
    risk_pct: float,
    available_balance: float,
    total_equity: float,
    positions: Iterable[Mapping[str, Any]],
    tracked_positions: Optional[Mapping[str, Mapping[str, Any]]] = None,
    max_margin_pct: float = 0.10,
    max_notional_pct: float = 0.20,
    max_portfolio_risk_pct: float = 0.0,
    max_same_side_alt_positions: int = 0,
    min_notional_usd: float = 5.0,
    min_margin_usd: float = 5.0,
    fallback_stop_pct: float = 1.8,
) -> RiskPlan:
    entry = max(0.0, safe_float(entry_price))
    stop = max(0.0, safe_float(stop_price))
    free_balance = max(0.0, safe_float(available_balance))
    equity = max(0.0, safe_float(total_equity) or free_balance)
    normalized_side = normalize_side(side)
    leverage = max(1, int(leverage))

    if entry <= 0 or stop <= 0 or normalized_side not in {"buy", "sell"}:
        return RiskPlan(ok=False, reason="invalid entry/stop/side")

    if normalized_side == "buy" and stop >= entry:
        return RiskPlan(ok=False, reason="stop is not below entry for long")
    if normalized_side == "sell" and stop <= entry:
        return RiskPlan(ok=False, reason="stop is not above entry for short")

    per_unit_risk = stop_distance(entry, stop)
    if per_unit_risk <= 0:
        return RiskPlan(ok=False, reason="stop distance is zero")

    portfolio = build_portfolio_state(
        positions,
        tracked_positions=tracked_positions,
        candidate_symbol=symbol,
        candidate_side=normalized_side,
        fallback_stop_pct=fallback_stop_pct,
    )

    key = symbol_key(symbol)
    side_cap_enabled = int(max_same_side_alt_positions) > 0
    if (
        side_cap_enabled
        and key
        and key not in BLUE_CHIPS
        and portfolio.same_side_alt_positions >= max_same_side_alt_positions
    ):
        return RiskPlan(
            ok=False,
            reason=f"same-side alt cap reached ({portfolio.same_side_alt_positions})",
            open_risk_usd=portfolio.open_risk_usd,
            gross_exposure_usd=portfolio.gross_exposure_usd,
            same_side_alt_positions=portfolio.same_side_alt_positions,
        )

    trade_risk_budget = equity * max(0.0, safe_float(risk_pct)) / 100.0
    portfolio_cap_enabled = safe_float(max_portfolio_risk_pct) > 0.0
    portfolio_limit = equity * max(0.0, safe_float(max_portfolio_risk_pct)) / 100.0 if portfolio_cap_enabled else 0.0
    remaining_portfolio_risk = max(0.0, portfolio_limit - portfolio.open_risk_usd) if portfolio_cap_enabled else trade_risk_budget
    usable_risk_budget = min(trade_risk_budget, remaining_portfolio_risk) if portfolio_cap_enabled else trade_risk_budget
    if portfolio_cap_enabled and usable_risk_budget <= 0:
        return RiskPlan(
            ok=False,
            reason="portfolio risk limit reached",
            open_risk_usd=portfolio.open_risk_usd,
            gross_exposure_usd=portfolio.gross_exposure_usd,
            portfolio_risk_limit_usd=portfolio_limit,
            same_side_alt_positions=portfolio.same_side_alt_positions,
        )

    max_margin_usd = min(
        free_balance * 0.85,
        equity * max(0.0, safe_float(max_margin_pct)),
    )
    max_notional_usd = min(
        max_margin_usd * leverage,
        equity * max(0.0, safe_float(max_notional_pct)) * max(1, leverage),
    )
    if max_margin_usd < min_margin_usd or max_notional_usd < min_notional_usd:
        return RiskPlan(
            ok=False,
            reason="insufficient free balance for protected entry",
            open_risk_usd=portfolio.open_risk_usd,
            gross_exposure_usd=portfolio.gross_exposure_usd,
            portfolio_risk_limit_usd=portfolio_limit,
            same_side_alt_positions=portfolio.same_side_alt_positions,
        )

    raw_size = usable_risk_budget / per_unit_risk
    capped_size = min(raw_size, max_notional_usd / entry)
    size = normalize_amount(exchange, symbol, capped_size)
    if size <= 0:
        return RiskPlan(
            ok=False,
            reason="normalized size is zero",
            open_risk_usd=portfolio.open_risk_usd,
            gross_exposure_usd=portfolio.gross_exposure_usd,
            portfolio_risk_limit_usd=portfolio_limit,
            same_side_alt_positions=portfolio.same_side_alt_positions,
        )

    notional_usd = size * entry
    margin_usd = notional_usd / leverage
    risk_amount_usd = size * per_unit_risk
    if notional_usd < min_notional_usd or margin_usd < min_margin_usd:
        return RiskPlan(
            ok=False,
            reason="size below exchange minimums",
            open_risk_usd=portfolio.open_risk_usd,
            gross_exposure_usd=portfolio.gross_exposure_usd,
            portfolio_risk_limit_usd=portfolio_limit,
            same_side_alt_positions=portfolio.same_side_alt_positions,
        )

    return RiskPlan(
        ok=True,
        size=size,
        notional_usd=notional_usd,
        margin_usd=margin_usd,
        risk_amount_usd=risk_amount_usd,
        stop_distance_pct=stop_distance_pct(entry, stop),
        open_risk_usd=portfolio.open_risk_usd,
        gross_exposure_usd=portfolio.gross_exposure_usd,
        portfolio_risk_limit_usd=portfolio_limit,
        same_side_alt_positions=portfolio.same_side_alt_positions,
    )
