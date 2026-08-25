import json
import math
import random
import subprocess
import sys
import unittest

from greeks import greeks, implied_vol, prices


class TestKnownValues(unittest.TestCase):
    # S=100 K=100 T=1 r=5% sigma=20%: call 10.4506, put 5.5735.
    # Cross-checked via put-call parity: 10.4506 - 5.5735 = 100 - 100*e^(-0.05)

    def test_hull_reference(self):
        call, put = prices(100, 100, 1.0, 0.05, 0.20)
        self.assertAlmostEqual(call, 10.4506, places=3)
        self.assertAlmostEqual(put, 5.5735, places=3)

    def test_atm_forward_approximation(self):
        # ATM call ~ 0.4 * S * sigma * sqrt(T)
        call, _ = prices(100, 100, 1.0, 0.0, 0.20)
        self.assertAlmostEqual(call, 0.4 * 100 * 0.2 * 1, delta=0.35)


class TestParity(unittest.TestCase):
    def test_put_call_parity_grid(self):
        rng = random.Random(1)
        for _ in range(200):
            s = rng.uniform(50, 150)
            k = rng.uniform(50, 150)
            t = rng.uniform(0.05, 3.0)
            r = rng.uniform(0.0, 0.12)
            v = rng.uniform(0.05, 1.2)
            c, p = prices(s, k, t, r, v)
            residual = c - p - (s - k * math.exp(-r * t))
            self.assertLess(abs(residual), 1e-9)


class TestGreeksFiniteDifference(unittest.TestCase):
    def test_delta_gamma_vega_match_fd(self):
        s, k, t, r, v = 105.0, 100.0, 0.6, 0.04, 0.28
        eps = 1e-4
        g = greeks(s, k, t, r, v)

        cu, pu = prices(s + eps, k, t, r, v)
        cd, pd = prices(s - eps, k, t, r, v)
        self.assertAlmostEqual(g["delta_call"], (cu - cd) / (2 * eps), places=6)
        self.assertAlmostEqual(g["delta_put"], (pu - pd) / (2 * eps), places=6)

        c, _ = prices(s, k, t, r, v)
        gamma_fd = ((cu - c) / eps - (c - cd) / eps) / eps
        self.assertAlmostEqual(g["gamma"], gamma_fd, places=4)

        ch, _ = prices(s, k, t, r, v + eps)
        clo, _ = prices(s, k, t, r, v - eps)
        self.assertAlmostEqual(g["vega_per_1pct"], (ch - clo) / (2 * eps) / 100, places=6)

    def test_deltas_sum_to_one(self):
        g = greeks(100, 110, 0.8, 0.03, 0.25)
        self.assertAlmostEqual(g["delta_call"] - g["delta_put"], 1.0, places=10)


class TestImpliedVol(unittest.TestCase):
    def test_round_trip(self):
        rng = random.Random(5)
        for _ in range(100):
            s = rng.uniform(80, 120)
            k = rng.uniform(80, 120)
            t = rng.uniform(0.1, 2.0)
            r = rng.uniform(0.0, 0.08)
            true_v = rng.uniform(0.1, 0.9)
            c, p = prices(s, k, t, r, true_v)
            iv_c = implied_vol(c, s, k, t, r, "call")
            iv_p = implied_vol(p, s, k, t, r, "put")
            self.assertIsNotNone(iv_c)
            self.assertAlmostEqual(iv_c, true_v, places=7)
            self.assertAlmostEqual(iv_p, true_v, places=7)

    def test_below_intrinsic_returns_none(self):
        self.assertIsNone(implied_vol(1.0, 100, 90, 0.5, 0.05, "call"))


class TestCLI(unittest.TestCase):
    def test_price_subcommand(self):
        out = subprocess.run(
            [sys.executable, "greeks.py", "price", "--spot", "100", "--strike", "100",
             "-t", "1", "-r", "0.05", "-v", "0.2"],
            capture_output=True, text=True)
        data = json.loads(out.stdout)
        self.assertAlmostEqual(data["call"], 10.4506, places=3)
        self.assertLess(abs(data["parity_residual"]), 1e-9)

    def test_iv_subcommand(self):
        out = subprocess.run(
            [sys.executable, "greeks.py", "iv", "--price", "10.4506", "--spot", "100",
             "--strike", "100", "-t", "1", "-r", "0.05"],
            capture_output=True, text=True)
        data = json.loads(out.stdout)
        self.assertAlmostEqual(data["implied_vol"], 0.2, places=6)


if __name__ == "__main__":
    unittest.main()
