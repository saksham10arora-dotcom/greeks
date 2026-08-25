#!/usr/bin/env python3
"""greeks: Black-Scholes prices, every greek, and implied volatility.
Single file, zero dependencies, pure standard library."""

import argparse
import json
import math
from statistics import NormalDist

PHI = NormalDist().cdf
PDF = NormalDist().pdf


def bs(spot, strike, t, rate, vol):
    """Core Black-Scholes quantities shared by pricing and greeks."""
    if t <= 0 or vol <= 0:
        raise ValueError("need t > 0 and vol > 0")
    sq = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + vol * vol / 2) * t) / sq
    d2 = d1 - sq
    disc = strike * math.exp(-rate * t)
    return {"d1": d1, "d2": d2, "disc": disc}


def prices(spot, strike, t, rate, vol):
    b = bs(spot, strike, t, rate, vol)
    call = spot * PHI(b["d1"]) - b["disc"] * PHI(b["d2"])
    put = b["disc"] * PHI(-b["d2"]) - spot * PHI(-b["d1"])
    return call, put


def greeks(spot, strike, t, rate, vol):
    """All greeks in per-unit terms; theta returned per calendar day."""
    b = bs(spot, strike, t, rate, vol)
    pdf_d1 = PDF(b["d1"])
    sqrt_t = math.sqrt(t)
    gamma = pdf_d1 / (spot * vol * sqrt_t)
    vega = spot * pdf_d1 * sqrt_t
    theta_common = -spot * pdf_d1 * vol / (2 * sqrt_t)
    theta_call = theta_common - rate * b["disc"] * PHI(b["d2"])
    theta_put = theta_common + rate * b["disc"] * PHI(-b["d2"])
    rho_call = strike * t * b["disc"] * PHI(b["d2"])
    rho_put = -strike * t * b["disc"] * PHI(-b["d2"])
    return {
        "delta_call": PHI(b["d1"]),
        "delta_put": PHI(b["d1"]) - 1,
        "gamma": gamma,
        "vega_per_1pct": vega / 100,
        "theta_call_per_day": theta_call / 365,
        "theta_put_per_day": theta_put / 365,
        "rho_call_per_1pct": rho_call / 100,
        "rho_put_per_1pct": rho_put / 100,
    }


def implied_vol(price_target, spot, strike, t, rate, kind="call", lo=1e-9, hi=10.0):
    """Implied volatility by Newton with bisection fallback. Returns vol or None."""
    def model(v):
        c, p = prices(spot, strike, t, rate, v)
        return c if kind == "call" else p

    intrinsic = max(0.0, spot - strike * math.exp(-rate * t)) if kind == "call" \
        else max(0.0, strike * math.exp(-rate * t) - spot)
    if price_target <= intrinsic:
        return None

    sigma = 0.5
    for _ in range(60):
        diff = model(sigma) - price_target
        if abs(diff) < 1e-10:
            return sigma
        _, p = prices(spot, strike, t, rate, sigma)
        vega_full = spot * PDF((math.log(spot / strike) + (rate + sigma * sigma / 2) * t) / (sigma * math.sqrt(t))) * math.sqrt(t)
        if vega_full < 1e-12:
            break
        step = diff / vega_full
        nxt = sigma - step
        if not (lo < nxt < hi):
            break
        sigma = nxt
    while hi - lo > 1e-12:
        mid = (lo + hi) / 2
        if model(mid) < price_target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 10)


def main():
    ap = argparse.ArgumentParser(description="Black-Scholes prices, greeks, and implied vol. Zero deps.")
    sub = ap.add_subparsers(dest="mode", required=True)

    p_price = sub.add_parser("price", help="prices + full greeks table")
    p_price.add_argument("--spot", type=float, required=True)
    p_price.add_argument("--strike", type=float, required=True)
    p_price.add_argument("-t", "--time", type=float, required=True, help="years to expiry")
    p_price.add_argument("-r", "--rate", type=float, required=True, help="risk-free, decimal")
    p_price.add_argument("-v", "--vol", type=float, required=True, help="volatility, decimal")
    p_price.add_argument("--json", action="store_true")

    p_iv = sub.add_parser("iv", help="solve implied volatility from a market price")
    p_iv.add_argument("--price", type=float, required=True)

    def add_common_args(parser):
        parser.add_argument("--spot", type=float, required=True)
        parser.add_argument("--strike", type=float, required=True)
        parser.add_argument("-t", "--time", type=float, required=True)
        parser.add_argument("-r", "--rate", type=float, required=True)

    add_common_args(p_iv)
    p_iv.add_argument("--kind", choices=["call", "put"], default="call")

    args = ap.parse_args()

    if args.mode == "iv":
        vol = implied_vol(args.price, args.spot, args.strike, args.time, args.rate, args.kind)
        out = {"implied_vol": vol, "kind": args.kind} if vol is not None else \
              {"error": "price below intrinsic value or no solution"}
        print(json.dumps(out))
        return

    call, put = prices(args.spot, args.strike, args.time, args.rate, args.vol)
    g = greeks(args.spot, args.strike, args.time, args.rate, args.vol)
    parity = call - put - (args.spot - args.strike * math.exp(-args.rate * args.time))

    print(json.dumps({
        "call": round(call, 4),
        "put": round(put, 4),
        **{k: round(v, 6) for k, v in g.items()},
        "parity_residual": round(parity, 12),
        "breakeven_call": round(args.strike + call, 4),
        "breakeven_put": round(args.strike - put, 4),
    }, indent=2))


if __name__ == "__main__":
    main()
