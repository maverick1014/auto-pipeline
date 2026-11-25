"""city-office test fixtures: office views (the snapshot's "world" since 2026-11-25) for the page sim tests that
used island views (plan_view / plan_views / ac.layout). A view is what the server sends:
{"v": 2, "repos": [{"id", "name", "here", "n"}], "floors": [ids bottom first], "designs": {}, "asked": []}."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_city as ac  # noqa: E402


def office_view(*names):
    """An office view with one floor per NAME (bottom first); default one floor "app". Each repo's identity is
    /work/<name>/.git, so its id is ac.territory_id of that (the same id a hook line of that repo gets)."""
    names = names or ("app",)
    repos = [{"id": ac.territory_id("/work/%s/.git" % n), "name": n, "here": True, "n": i} for i, n in enumerate(names)]
    return {"v": 2, "repos": repos, "floors": [r["id"] for r in repos], "designs": {}, "asked": [r["id"] for r in repos]}


def office_views():
    """plan_views() stand-in: {name: view}, one view of one floor."""
    return {"office": office_view("app")}


def office_view_of(*pairs):
    """An office view of (identity, name) pairs, bottom floor first. For the old drivers it also carries a
    test-only "territories" list in the same order, each {id, name, floor, cx, cz} as the page computes them
    (floor n at cx = (n - 1) * 60): a driver's `V.territories[0].id` still names the first repo. The page
    ignores that key (officeState reads repos and floors)."""
    repos = [{"id": ac.territory_id(ident), "name": name, "here": True, "n": i} for i, (ident, name) in enumerate(pairs)]
    terrs = [{"id": r["id"], "name": r["name"], "floor": i + 1, "cx": i * 60, "cz": 0} for i, r in enumerate(repos)]
    return {"v": 2, "repos": repos, "floors": [r["id"] for r in repos], "designs": {}, "asked": [r["id"] for r in repos],
            "territories": terrs}
