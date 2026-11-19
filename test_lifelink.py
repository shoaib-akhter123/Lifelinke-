"""
test_lifelink.py - automated tests for LifeLink.

Run with:  python -m unittest test_lifelink -v

Part 1 tests the data structures and BloodBank logic.
Part 2 is a "smoke test": it runs lifelink_app.py against a fake Streamlit
object so typos, wrong names and crashes in every page are caught. It does NOT
check how the pages look in a real browser.
"""

import ast
import itertools
import os
import random
import runpy
import sys
import unittest
from datetime import date, timedelta
from unittest import mock

import pandas  # noqa: F401  (import first so the fake-streamlit patch does not reload it)

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from models import GROUPS, ELIGIBILITY_DAYS, SHELF_LIFE, read_date          # noqa: E402
from data_structures import (Stack, Queue, AVLTree, BloodGraph,             # noqa: E402
                             AreaGraph, plain_bst_height)
from blood_bank import BloodBank, load_demo, load_roads, DEMO_STOCK         # noqa: E402

TODAY = date(2026, 11, 19)


def make_bank(demo=True):
    bank = BloodBank(today=TODAY)
    if demo:
        load_demo(bank)
    return bank


# ---------------------------------------------------------------
# Part 1a: data structures
# ---------------------------------------------------------------
class TestStackQueue(unittest.TestCase):
    def test_stack_is_lifo(self):
        s = Stack()
        for i in range(5):
            s.push(i)
        self.assertEqual(s.peek(), 4)
        self.assertEqual([s.pop() for _ in range(5)], [4, 3, 2, 1, 0])
        self.assertIsNone(s.pop())
        self.assertTrue(s.is_empty())

    def test_queue_is_fifo_and_front_insert(self):
        q = Queue()
        for i in range(3):
            q.enqueue(i)
        q.enqueue_front("first")
        self.assertEqual(len(q), 4)
        self.assertEqual(q.to_list(), ["first", 0, 1, 2])
        self.assertEqual(q.dequeue(), "first")
        self.assertEqual([q.dequeue() for _ in range(3)], [0, 1, 2])
        self.assertIsNone(q.dequeue())
        self.assertEqual(len(q), 0)
        q.enqueue("x")                       # rear pointer must still work
        self.assertEqual(q.to_list(), ["x"])


class TestAVL(unittest.TestCase):
    def test_stays_balanced_and_sorted(self):
        random.seed(1)
        keys = random.sample(range(10000), 800)
        tree = AVLTree()
        for k in keys:
            tree.insert((k, k), k)
        self.assertTrue(tree.is_balanced())
        self.assertEqual(tree.size, 800)
        self.assertEqual(tree.inorder(), sorted(keys))
        for k in random.sample(keys, 400):
            self.assertTrue(tree.delete((k, k)))
            keys.remove(k)
        self.assertTrue(tree.is_balanced())
        self.assertEqual(tree.size, 400)
        self.assertEqual(tree.inorder(), sorted(keys))
        self.assertFalse(tree.delete((-5, -5)))

    def test_pop_min_gives_sorted_order(self):
        tree = AVLTree()
        for k in [50, 20, 70, 10, 30, 60, 80, 5]:
            tree.insert((k, k), k)
        self.assertEqual([tree.pop_min() for _ in range(8)], [5, 10, 20, 30, 50, 60, 70, 80])
        self.assertIsNone(tree.pop_min())
        self.assertEqual(tree.size, 0)

    def test_range_query_matches_brute_force(self):
        random.seed(2)
        keys = random.sample(range(500), 120)
        tree = AVLTree()
        for k in keys:
            tree.insert((k, k), k)
        for low, high in [(0, 499), (100, 200), (250, 250), (400, 100), (-10, 5)]:
            expected = sorted(k for k in keys if low <= k <= high)
            self.assertEqual(sorted(tree.range_query(low, high)), expected)

    def test_duplicate_rejected_and_rotations_counted(self):
        tree = AVLTree()
        for k in (1, 2, 3):
            tree.insert((k, k))
        self.assertEqual(tree.rotations, 1)       # 1,2,3 needs one left rotation
        self.assertEqual(tree.tree_height(), 2)
        with self.assertRaises(ValueError):
            tree.insert((2, 2))

    def test_plain_bst_height_comparison(self):
        self.assertEqual(plain_bst_height([1, 2, 3, 4, 5, 6, 7]), 7)
        sandbox = AVLTree()
        for k in range(1, 8):
            sandbox.insert((k, k))
        self.assertEqual(sandbox.tree_height(), 3)

    def test_to_dot(self):
        tree = AVLTree()
        self.assertIsNone(tree.to_dot(str))
        for k in (2, 1, 3):
            tree.insert((k, k))
        dot = tree.to_dot(lambda n: n.key[0])
        self.assertTrue(dot.startswith("digraph") and dot.count("->") == 2)


class TestGraphs(unittest.TestCase):
    def test_compatibility_table(self):
        g = BloodGraph()
        self.assertTrue(g.can_donate("O-", "AB+"))
        self.assertFalse(g.can_donate("A+", "A-"))
        self.assertEqual(set(g.donors_for("AB+")), set(GROUPS))
        self.assertEqual(set(g.donors_for("O-")), {"O-"})
        for recipient in GROUPS:
            order = g.preferred_order(recipient)
            self.assertEqual(order[0], recipient)
            self.assertEqual(set(order), set(g.donors_for(recipient)))
        self.assertEqual(g.preferred_order("AB+")[-1], "O-")   # universal donor last

    def test_dijkstra_matches_floyd_warshall(self):
        bank = make_bank(demo=False)
        load_roads(bank)
        graph = bank.area_graph
        nodes = list(graph.graph)
        inf = float("inf")
        d = {a: {b: (0 if a == b else graph.graph[a].get(b, inf)) for b in nodes} for a in nodes}
        for k, i, j in itertools.product(nodes, nodes, nodes):
            if d[i][k] + d[k][j] < d[i][j]:
                d[i][j] = d[i][k] + d[k][j]
        for source in nodes:
            self.assertEqual(graph.dijkstra(source), d[source])

    def test_shortest_path_and_errors(self):
        bank = make_bank(demo=False)
        load_roads(bank)
        dist, path = bank.area_graph.shortest_path("NED University", "Saddar")
        self.assertEqual(dist, 18)
        self.assertEqual(path, ["NED University", "Gulshan", "PECHS", "Saddar"])
        self.assertEqual(bank.area_graph.dijkstra("Nowhere"), {})
        self.assertEqual(bank.area_graph.shortest_path("Nowhere", "Saddar"), (None, []))
        with self.assertRaises(ValueError):
            bank.area_graph.add_road("A", "B", 0)
        self.assertIn("graph Roads", bank.area_graph.to_dot("Gulshan"))


# ---------------------------------------------------------------
# Part 1b: BloodBank behaviour
# ---------------------------------------------------------------
class TestBloodBank(unittest.TestCase):
    def test_demo_data(self):
        bank = make_bank()
        self.assertEqual(bank.total_units(), sum(DEMO_STOCK.values()))
        for g in GROUPS:
            self.assertEqual(bank.count(g), DEMO_STOCK[g])
        self.assertEqual(bank.low_stock(), ["O-", "A-", "AB-"])
        self.assertEqual(len(bank.donors), 10)
        self.assertEqual(len(bank.pending()), 3)
        self.assertTrue(bank.undo_stack.is_empty())
        self.assertTrue(all(bank.check_trees().values()))
        self.assertGreater(len(bank.expiring_soon(7)), 0)

    def test_add_unit_validation(self):
        bank = make_bank(demo=False)
        unit = bank.add_unit("a+", TODAY - timedelta(days=2))
        self.assertEqual(unit.group, "A+")
        self.assertEqual(unit.expiry, TODAY - timedelta(days=2) + timedelta(days=SHELF_LIFE))
        with self.assertRaises(ValueError):
            bank.add_unit("XX")
        with self.assertRaises(ValueError):
            bank.add_unit("A+", TODAY + timedelta(days=1))
        with self.assertRaises(ValueError):
            bank.add_unit("A+", TODAY - timedelta(days=SHELF_LIFE + 1))
        with self.assertRaises(ValueError):
            bank.add_unit("A+", donor_id="D999")
        with self.assertRaises(ValueError):
            bank.add_unit("A+", "not-a-date")
        self.assertEqual(bank.total_units(), 1)

    def test_update_and_discard_unit(self):
        bank = make_bank(demo=False)
        u1 = bank.add_unit("A+", TODAY - timedelta(days=10))
        u2 = bank.add_unit("A+", TODAY - timedelta(days=30))
        self.assertEqual(bank.trees["A+"].min_unit().unit_id, u2.unit_id)
        bank.update_unit(u2.unit_id, collected=TODAY)            # now freshest
        self.assertEqual(bank.trees["A+"].min_unit().unit_id, u1.unit_id)
        bank.update_unit(u1.unit_id, group="B+")                 # move between trees
        self.assertEqual((bank.count("A+"), bank.count("B+")), (1, 1))
        self.assertTrue(all(bank.check_trees().values()))
        with self.assertRaises(ValueError):
            bank.update_unit(u1.unit_id, collected=TODAY + timedelta(days=3))
        with self.assertRaises(ValueError):
            bank.update_unit("U9999", group="A+")
        self.assertEqual(bank.units[u1.unit_id].group, "B+")     # failed update changed nothing
        bank.discard_unit(u1.unit_id)
        self.assertEqual(bank.total_units(), 1)
        self.assertEqual(len(bank.discarded), 1)
        with self.assertRaises(ValueError):
            bank.discard_unit(u1.unit_id)

    def test_expiry_removal_and_date_rules(self):
        bank = make_bank()
        before = bank.total_units()
        bank.set_today(TODAY + timedelta(days=SHELF_LIFE + 5))
        self.assertEqual(bank.total_units(), 0)
        self.assertEqual(len(bank.discarded), before)
        with self.assertRaises(ValueError):
            bank.set_today(TODAY)                                 # cannot go backwards

    def test_expiring_soon_boundaries(self):
        bank = make_bank(demo=False)
        edge = bank.add_unit("O+", TODAY - timedelta(days=SHELF_LIFE - 7))   # expires in 7 days
        out = bank.add_unit("O+", TODAY - timedelta(days=SHELF_LIFE - 8))    # expires in 8 days
        today_unit = bank.add_unit("O+", TODAY - timedelta(days=SHELF_LIFE))  # expires today
        ids = [u.unit_id for u in bank.expiring_soon(7)]
        self.assertIn(edge.unit_id, ids)
        self.assertIn(today_unit.unit_id, ids)
        self.assertNotIn(out.unit_id, ids)
        self.assertEqual(sum(bank.expiry_buckets().values()), bank.total_units())

    def test_donor_eligibility_boundary(self):
        bank = make_bank(demo=False)
        a = bank.register_donor("A Demo", "A+", "Gulshan", TODAY - timedelta(days=ELIGIBILITY_DAYS - 1))
        b = bank.register_donor("B Demo", "A+", "Gulshan", TODAY - timedelta(days=ELIGIBILITY_DAYS))
        c = bank.register_donor("C Demo", "A+", "Gulshan", None)
        self.assertFalse(bank.is_eligible(bank.donors[a]))
        self.assertEqual(bank.days_until_eligible(bank.donors[a]), 1)
        self.assertTrue(bank.is_eligible(bank.donors[b]))
        self.assertTrue(bank.is_eligible(bank.donors[c]))
        with self.assertRaises(ValueError):
            bank.register_donor("  ", "A+", "Gulshan")
        with self.assertRaises(ValueError):
            bank.register_donor("X", "Q+", "Gulshan")
        with self.assertRaises(ValueError):
            bank.register_donor("X", "A+", "Gulshan", TODAY + timedelta(days=1))

    def test_donor_search(self):
        bank = make_bank()
        self.assertEqual({d.name for d in bank.search_donors("ali")}, {"Ali Demo"})
        self.assertEqual(len(bank.search_donors("")), 10)
        self.assertEqual({d.donor_id for d in bank.search_donors("D001")}, {"D001"})
        o_neg = bank.search_donors(group="O-")
        self.assertEqual({d.name for d in o_neg}, {"Sara Demo", "Zain Demo"})
        everyone = bank.search_donors()
        eligible = bank.search_donors(eligible_only=True)
        self.assertLess(len(eligible), len(everyone))
        self.assertTrue(all(bank.is_eligible(d) for d in eligible))

    def test_find_donors_rules(self):
        bank = make_bank()
        matches = bank.find_donors("A+", "Gulshan", limit=20)
        for m in matches:
            donor = bank.donors[m["donor_id"]]
            self.assertTrue(bank.blood_graph.can_donate(donor.group, "A+"))
            self.assertTrue(bank.is_eligible(donor))
        ranks = [bank.blood_graph.preferred_order("A+").index(m["group"]) for m in matches]
        self.assertEqual(ranks, sorted(ranks))                      # exact group first
        self.assertEqual(matches[0]["match"], "Exact")
        self.assertEqual(len(bank.find_donors("A+", "Gulshan", limit=2)), 2)
        waiting = bank.ineligible_donors("A+")
        self.assertTrue(all(days > 0 for _, days in waiting))

    def test_priority_processing_and_fefo(self):
        bank = make_bank(demo=False)
        for days_ago in (5, 30, 15):
            bank.add_unit("A+", TODAY - timedelta(days=days_ago))
        normal = bank.submit_request("Normal P", "A+", 1, 3, "Gulshan")
        urgent = bank.submit_request("Urgent P", "A+", 1, 2, "Gulshan")
        critical = bank.submit_request("Critical P", "A+", 1, 1, "Gulshan")
        self.assertEqual([r.req_id for r in bank.pending()],
                         [critical.req_id, urgent.req_id, normal.req_id])
        first = bank.process_next()
        self.assertEqual(first.request.req_id, critical.req_id)
        self.assertEqual(first.issued[0].collected, TODAY - timedelta(days=30))   # earliest expiry
        second = bank.process_next()
        self.assertEqual(second.request.req_id, urgent.req_id)
        self.assertEqual(second.issued[0].collected, TODAY - timedelta(days=15))
        self.assertEqual(bank.request_status(normal.req_id), "Pending")
        self.assertEqual(bank.request_status(critical.req_id), "Fulfilled")

    def test_fifo_inside_same_urgency(self):
        bank = make_bank(demo=False)
        first = bank.submit_request("One", "A+", 1, 2, "Gulshan")
        second = bank.submit_request("Two", "A+", 1, 2, "Gulshan")
        self.assertEqual(bank.process_next().request.req_id, first.req_id)
        self.assertEqual(bank.process_next().request.req_id, second.req_id)
        self.assertIsNone(bank.process_next())

    def test_compatible_fallback_keeps_o_negative_last(self):
        bank = make_bank(demo=False)
        bank.add_unit("O-", TODAY - timedelta(days=1))
        bank.add_unit("A-", TODAY - timedelta(days=1))
        bank.add_unit("A+", TODAY - timedelta(days=1))
        bank.submit_request("P", "A+", 3, 1, "Gulshan")
        result = bank.process_next()
        self.assertEqual([u.group for u in result.issued], ["A+", "A-", "O-"])
        self.assertEqual(result.status, "Fulfilled")

    def test_shortfall_suggests_donors(self):
        bank = make_bank(demo=False)
        load_roads(bank)
        bank.register_donor("Near Demo", "A+", "Gulshan", None)
        bank.register_donor("Far Demo", "A+", "Malir", None)
        bank.add_unit("A+", TODAY)
        bank.submit_request("P", "A+", 3, 1, "NED University")
        result = bank.process_next()
        self.assertEqual((len(result.issued), result.shortfall), (1, 2))
        self.assertEqual(result.status, "Partially fulfilled")
        self.assertEqual([d["name"] for d in result.donors], ["Near Demo", "Far Demo"])
        self.assertLess(result.donors[0]["distance_km"], result.donors[1]["distance_km"])
        bank.submit_request("Q", "B+", 1, 1, "Gulshan")
        self.assertEqual(bank.process_next().status, "Not fulfilled")

    def test_undo_add_restores_donor_date(self):
        bank = make_bank(demo=False)
        donor_id = bank.register_donor("D Demo", "A+", "Gulshan", TODAY - timedelta(days=200))
        old = bank.donors[donor_id].last_donation
        unit = bank.add_unit("A+", TODAY, donor_id)
        self.assertEqual(bank.donors[donor_id].last_donation, TODAY)
        self.assertEqual(bank.undo_label(), f"Add {unit.unit_id}")
        ok, _ = bank.undo()
        self.assertTrue(ok)
        self.assertEqual(bank.total_units(), 0)
        self.assertEqual(bank.donors[donor_id].last_donation, old)
        self.assertTrue(all(bank.check_trees().values()))

    def test_undo_process_restores_units_queue_and_history(self):
        bank = make_bank(demo=False)
        bank.add_unit("A+", TODAY)
        bank.add_unit("A+", TODAY - timedelta(days=3))
        first = bank.submit_request("First", "A+", 1, 1, "Gulshan")
        bank.submit_request("Second", "A+", 1, 1, "Gulshan")
        bank.process_next()
        self.assertEqual(bank.total_units(), 1)
        ok, _ = bank.undo()
        self.assertTrue(ok)
        self.assertEqual(bank.total_units(), 2)
        self.assertEqual(bank.pending()[0].req_id, first.req_id)   # back at the FRONT
        self.assertEqual(bank.request_status(first.req_id), "Pending")
        self.assertNotIn(first.req_id, bank.results)

    def test_undo_empty_and_lifo_order(self):
        bank = make_bank(demo=False)
        self.assertEqual(bank.undo(), (False, "Nothing to undo."))
        u1 = bank.add_unit("A+", TODAY)
        u2 = bank.add_unit("B+", TODAY)
        bank.undo()
        self.assertIn(u1.unit_id, bank.units)
        self.assertNotIn(u2.unit_id, bank.units)

    def test_request_validation(self):
        bank = make_bank(demo=False)
        with self.assertRaises(ValueError):
            bank.submit_request("", "A+", 1, 1, "Gulshan")
        with self.assertRaises(ValueError):
            bank.submit_request("P", "A+", 0, 1, "Gulshan")
        with self.assertRaises(ValueError):
            bank.submit_request("P", "A+", 1, 9, "Gulshan")
        with self.assertRaises(ValueError):
            bank.submit_request("P", "Z+", 1, 1, "Gulshan")
        self.assertEqual(bank.pending(), [])

    def test_process_all_and_reports(self):
        bank = make_bank()
        results = bank.process_all()
        self.assertEqual(len(results), 3)
        self.assertEqual(bank.pending(), [])
        report = {row["Blood group"]: row for row in bank.stock_report()}
        self.assertEqual(set(report), set(GROUPS))
        self.assertEqual(bank.recent_requests(2)[0].req_id, "R003")
        self.assertTrue(bank.show_log())

    def test_date_helpers(self):
        self.assertEqual(read_date("2026-11-19"), TODAY)
        self.assertEqual(read_date(TODAY), TODAY)
        with self.assertRaises(ValueError):
            read_date("19/11/2026")


# ---------------------------------------------------------------
# Part 2: UI smoke test with a fake Streamlit
# ---------------------------------------------------------------
class Dummy:
    """Accepts any call or attribute, works as a context manager."""

    def __call__(self, *a, **k):
        return Dummy()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Dummy()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Container:
    """A column / tab / sidebar: widgets called on it behave like st.<widget>."""

    def __init__(self, fake):
        self._fake = fake

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._fake, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class FakeStreamlit:
    """Minimal stand-in for the streamlit module."""

    def __init__(self, page, submit=False, text="Test Person"):
        self.page, self.submit, self.text = page, submit, text
        self.session_state = FakeState()
        self.sidebar = Container(self)
        self.reruns = 0
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self.calls.append(name)
        return Dummy()

    def radio(self, label, options, **k):
        return self.page

    def selectbox(self, label, options, index=0, **k):
        options = list(options)
        return options[index] if options else None

    def multiselect(self, *a, **k):
        return []

    def text_input(self, label, value="", **k):
        return value if value else self.text

    def number_input(self, label, min_value=None, max_value=None, value=None, **k):
        return value if value is not None else (min_value or 0)

    def slider(self, label, min_value=0, max_value=100, value=None, **k):
        return value if value is not None else min_value

    def checkbox(self, *a, **k):
        return self.submit

    def date_input(self, label, value=None, **k):
        return value or date.today()

    def button(self, *a, **k):
        return self.submit

    def form_submit_button(self, *a, **k):
        return self.submit

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [Container(self) for _ in range(n)]

    def tabs(self, labels):
        return [Container(self) for _ in labels]

    def expander(self, *a, **k):
        return Container(self)

    def rerun(self):
        self.reruns += 1

    def stop(self):
        pass

    def download_button(self, *a, **k):
        return False


PAGE_NAMES = ["Dashboard", "Blood Inventory", "Donor Management",
              "Emergency Requests", "Donor Matching", "DSA Laboratory", "Reports"]


def run_app(page, submit=False, bank_setup=None):
    fake = FakeStreamlit(page, submit=submit)
    if bank_setup:
        bank = BloodBank(today=TODAY)
        load_demo(bank)
        bank_setup(bank)
        fake.session_state["bank"] = bank
    with mock.patch.dict(sys.modules, {"streamlit": fake}):
        for name in ("ui_components", "lifelink_app"):
            sys.modules.pop(name, None)
        runpy.run_path(os.path.join(HERE, "lifelink_app.py"))
        sys.modules.pop("ui_components", None)
    return fake


class TestUISmoke(unittest.TestCase):
    def test_every_page_renders_without_error(self):
        for page in PAGE_NAMES:
            with self.subTest(page=page):
                fake = run_app(page)
                self.assertIn("set_page_config", fake.calls)

    def test_every_page_with_buttons_pressed(self):
        for page in PAGE_NAMES:
            with self.subTest(page=page):
                run_app(page, submit=True)

    def test_pages_with_empty_bank(self):
        def empty(bank):
            for unit_id in list(bank.units):
                bank.discard_unit(unit_id)
            for g in GROUPS:
                bank.queues[1] = bank.queues[2] = bank.queues[3] = type(bank.queues[1])()
            bank.all_requests.clear()
            bank.discarded.clear()
            bank.donors.clear()
            for g in GROUPS:
                bank.donors_by_group[g].clear()
        for page in PAGE_NAMES:
            with self.subTest(page=page):
                run_app(page, bank_setup=empty)
                run_app(page, submit=True, bank_setup=empty)

    def test_no_bare_expressions_that_streamlit_would_print(self):
        """Streamlit 'magic' prints bare expressions such as `a if x else b`
        (the DeltaGenerator bug). Only calls and docstrings may stand alone."""
        for name in ("lifelink_app.py", "ui_components.py", "blood_bank.py",
                     "data_structures.py", "models.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr):
                    ok = isinstance(node.value, ast.Call) or (
                        isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
                    self.assertTrue(ok, f"{name} line {node.lineno}: bare expression")

    def test_no_code_display_calls(self):
        for name in ("lifelink_app.py", "ui_components.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                source = handle.read()
            for banned in ("st.code(", "st.echo(", "st.help("):
                self.assertNotIn(banned, source, f"{name} uses {banned}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
