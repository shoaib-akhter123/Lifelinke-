"""
lifelink_app.py - LifeLink: Blood Bank Inventory & Emergency Donor Matcher
EE-264 Data Structures and Algorithms course project (NED University).

Main Streamlit file: page navigation and page layouts only.
The real logic lives in blood_bank.py and data_structures.py.

Educational demonstration prototype. Demo data only, held in memory.
Not a clinical or medically validated system.
"""

from datetime import timedelta

import pandas as pd
import streamlit as st

from models import GROUPS, AREAS, URGENCY, URGENCY_CODE, SHELF_LIFE
from blood_bank import BloodBank, load_demo
from data_structures import AVLTree, plain_bst_height
from ui_components import (
    inject_css, page_header, kpi_card, disclaimer, note, show_table,
    action_button, flash, show_flash, units_frame, donors_frame, requests_frame,
)

st.set_page_config(page_title="LifeLink | Blood Bank", page_icon="🩸",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()

PAGES = {
    "Dashboard": "📊",
    "Blood Inventory": "🩸",
    "Donor Management": "👥",
    "Emergency Requests": "🚨",
    "Donor Matching": "🔎",
    "DSA Laboratory": "🧪",
    "Reports": "📈",
}


# ---------------------------------------------------------------
# state
# ---------------------------------------------------------------
def new_bank():
    bank = BloodBank()
    load_demo(bank)
    return bank


if "bank" not in st.session_state:
    st.session_state["bank"] = new_bank()
bank = st.session_state["bank"]


def undo_button(key):
    """Shared Undo button (supports Add and Process only)."""
    label = bank.undo_label()
    text = f"Undo: {label}" if label else "Undo (nothing to undo)"
    if action_button(text, key=key):
        ok, message = bank.undo()
        flash("success" if ok else "info", message)
        st.rerun()


# ---------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🩸 LifeLink")
    st.caption("Blood Bank Inventory & Emergency Donor Matcher")
    page = st.radio("Navigation", list(PAGES.keys()),
                    format_func=lambda name: f"{PAGES[name]}  {name}",
                    label_visibility="collapsed")
    st.divider()
    st.caption(f"System date: {bank.today}")
    with st.expander("Demo tools"):
        days_forward = st.number_input("Move date forward (days)", min_value=1,
                                       max_value=60, value=7, step=1)
        if action_button("Advance system date", key="advance_date"):
            bank.set_today(bank.today + timedelta(days=int(days_forward)))
            flash("info", f"System date is now {bank.today}. Expired units were discarded.")
            st.rerun()
        if action_button("Reset demo data", key="reset_demo"):
            st.session_state["bank"] = new_bank()
            st.session_state.pop("last_results", None)
            flash("success", "Demo data reset.")
            st.rerun()
    st.caption("Educational prototype. Demo data only. Not for clinical use.")

show_flash()


# ---------------------------------------------------------------
# page: Dashboard
# ---------------------------------------------------------------
def page_dashboard():
    page_header("Dashboard", "Live overview of stock, donors and emergency requests", "📊")
    low = bank.low_stock()
    pending = bank.pending()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total blood units", bank.total_units(), f"{SHELF_LIFE}-day shelf life")
    with c2:
        kpi_card("Registered donors", len(bank.donors), "demo records")
    with c3:
        kpi_card("Pending requests", len(pending), "waiting in queues",
                 "warn" if pending else "good")
    with c4:
        kpi_card("Low-stock groups", len(low), ", ".join(low) if low else "all groups OK",
                 "warn" if low else "good")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Inventory by blood group")
        report = bank.stock_report()
        chart = pd.DataFrame({
            "In stock": [r["Units"] if r["Status"] == "OK" else 0 for r in report],
            "Low stock": [r["Units"] if r["Status"] != "OK" else 0 for r in report],
        }, index=[r["Blood group"] for r in report])
        st.bar_chart(chart, color=["#9f1239", "#f59e0b"])
    with right:
        st.subheader("Blood group availability")
        show_table(pd.DataFrame(report))

    a, b = st.columns(2)
    with a:
        st.subheader("Low-stock alerts")
        if low:
            for group in low:
                st.warning(f"{group}: only {bank.count(group)} unit(s) in stock")
        else:
            st.success("No low-stock alerts.")
    with b:
        st.subheader("Requests waiting by priority")
        p1, p2, p3 = st.columns(3)
        with p1:
            kpi_card("Critical", len(bank.queues[1]))
        with p2:
            kpi_card("Urgent", len(bank.queues[2]), "", "warn")
        with p3:
            kpi_card("Normal", len(bank.queues[3]), "", "good")

    st.subheader("Expiring within 7 days")
    expiring = bank.expiring_soon(7)
    show_table(units_frame(expiring, bank.today) if expiring else None,
               "No units expiring within 7 days.")

    st.subheader("Recent emergency requests")
    show_table(requests_frame(bank, bank.recent_requests(5)) if bank.all_requests else None,
               "No requests yet.")


# ---------------------------------------------------------------
# page: Blood Inventory
# ---------------------------------------------------------------
def page_inventory():
    page_header("Blood Inventory", "Add, view, update and track expiry of blood units", "🩸")
    t_stock, t_add, t_manage, t_expiry = st.tabs(
        ["Stock", "Add unit", "Update / discard", "Expiry tracking"])

    with t_stock:
        c1, c2 = st.columns([1, 1])
        chosen = c1.selectbox("Filter by blood group", ["All groups"] + GROUPS)
        only_soon = c2.checkbox("Only units expiring within 7 days")
        units = [u for u in bank.units.values()
                 if (chosen == "All groups" or u.group == chosen)
                 and (not only_soon or u.days_left(bank.today) <= 7)]
        units.sort(key=lambda u: (u.expiry, u.unit_id))
        st.caption(f"{len(units)} unit(s) shown, earliest expiry first (FEFO).")
        show_table(units_frame(units, bank.today) if units else None,
                   "No units match this filter.")
        low = bank.low_stock()
        if low:
            st.warning("Low stock: " + ", ".join(low))

    with t_add:
        with st.form("add_unit_form", clear_on_submit=False):
            a, b, c = st.columns(3)
            group = a.selectbox("Blood group", GROUPS, key="add_unit_group")
            collected = b.date_input("Collection date", value=bank.today,
                                     min_value=bank.today - timedelta(days=SHELF_LIFE),
                                     max_value=bank.today, key="add_unit_date")
            donor_choice = c.selectbox("Linked donor (optional)",
                                       ["No linked donor"] + sorted(bank.donors.keys()),
                                       key="add_unit_donor")
            submitted = st.form_submit_button("Add blood unit", type="primary")
        if submitted:
            ok = True
            try:
                donor_id = None if donor_choice == "No linked donor" else donor_choice
                unit = bank.add_unit(group, collected, donor_id)
                flash("success", f"Added {unit.unit_id} ({unit.group}). Expires {unit.expiry}.")
            except ValueError as error:
                ok = False
                st.error(str(error))
            if ok:
                st.rerun()
        undo_button("undo_inventory")

    with t_manage:
        if not bank.units:
            st.info("There are no units in stock.")
        else:
            ordered = sorted(bank.units.values(), key=lambda u: (u.group, u.expiry, u.unit_id))
            labels = {u.unit_id: f"{u.unit_id} | {u.group} | expires {u.expiry}" for u in ordered}
            unit_id = st.selectbox("Select a unit", list(labels.keys()),
                                   format_func=lambda uid: labels[uid])
            unit = bank.units[unit_id]
            with st.form("update_unit_form"):
                a, b = st.columns(2)
                new_group = a.selectbox("Blood group", GROUPS, index=GROUPS.index(unit.group),
                                        key=f"upd_group_{unit_id}")
                new_date = b.date_input("Collection date", value=unit.collected,
                                        min_value=bank.today - timedelta(days=SHELF_LIFE),
                                        max_value=bank.today, key=f"upd_date_{unit_id}")
                save = st.form_submit_button("Save changes", type="primary")
            if save:
                ok = True
                try:
                    bank.update_unit(unit_id, new_date, new_group)
                    flash("success", f"{unit_id} updated.")
                except ValueError as error:
                    ok = False
                    st.error(str(error))
                if ok:
                    st.rerun()
            if action_button("Discard this unit", key="discard_unit"):
                bank.discard_unit(unit_id)
                flash("info", f"{unit_id} discarded.")
                st.rerun()
            note("Update and discard are not undoable. Undo supports Add and Process only.")

    with t_expiry:
        days = st.slider("Show units expiring within (days)", 1, SHELF_LIFE, 7)
        expiring = bank.expiring_soon(days)
        st.caption("Found with an AVL range query on the expiry key.")
        show_table(units_frame(expiring, bank.today) if expiring else None,
                   "No units expiring in this period.")
        st.subheader("Discarded (expired or removed) units")
        show_table(units_frame(bank.discarded, bank.today) if bank.discarded else None,
                   "No units have been discarded.")


# ---------------------------------------------------------------
# page: Donor Management
# ---------------------------------------------------------------
def page_donors():
    page_header("Donor Management", "Register donors and review their eligibility", "👥")
    disclaimer("All donors are demo records. The 90-day eligibility rule is project "
               "logic only, not medical screening.")
    t_dir, t_reg = st.tabs(["Donor directory", "Register donor"])

    with t_dir:
        a, b, c = st.columns([2, 1, 1])
        text = a.text_input("Search by name or ID", placeholder="e.g. Ali or D003")
        group = b.selectbox("Blood group", ["All groups"] + GROUPS, key="donor_filter_group")
        eligible_only = c.checkbox("Eligible only")
        donors = bank.search_donors(text, None if group == "All groups" else group,
                                    eligible_only)
        st.caption(f"{len(donors)} donor(s) found.")
        show_table(donors_frame(bank, donors) if donors else None,
                   "No donors match your search.")

    with t_reg:
        has_last = st.checkbox("Previous donation date is known")
        with st.form("donor_form", clear_on_submit=False):
            a, b = st.columns(2)
            name = a.text_input("Donor name (use a demo name)", max_chars=60)
            group = b.selectbox("Blood group", GROUPS, key="donor_reg_group")
            c, d = st.columns(2)
            area = c.selectbox("Area", AREAS)
            last = d.date_input("Last donation date",
                                value=bank.today - timedelta(days=120),
                                max_value=bank.today, disabled=not has_last)
            submitted = st.form_submit_button("Register donor", type="primary")
        if submitted:
            ok = True
            try:
                donor_id = bank.register_donor(name, group, area, last if has_last else None)
                flash("success", f"Donor registered: {donor_id}")
            except ValueError as error:
                ok = False
                st.error(str(error))
            if ok:
                st.rerun()


# ---------------------------------------------------------------
# page: Emergency Requests
# ---------------------------------------------------------------
def page_requests():
    page_header("Emergency Requests", "Queue, prioritise and process patient blood requests", "🚨")
    t_new, t_queue, t_history = st.tabs(["New request", "Queue & processing", "History"])

    with t_new:
        with st.form("request_form", clear_on_submit=False):
            a, b, c = st.columns(3)
            patient = a.text_input("Patient name / demo label", max_chars=60)
            group = b.selectbox("Blood group needed", GROUPS)
            units = c.number_input("Units required", min_value=1, max_value=20,
                                   value=2, step=1)
            d, e = st.columns(2)
            urgency = d.selectbox("Urgency", list(URGENCY.values()))
            area = e.selectbox("Patient area", AREAS)
            submitted = st.form_submit_button("Add request to queue", type="primary")
        if submitted:
            ok = True
            try:
                req = bank.submit_request(patient, group, units, URGENCY_CODE[urgency], area)
                flash("success", f"{req.req_id} added to the {urgency} queue.")
            except ValueError as error:
                ok = False
                st.error(str(error))
            if ok:
                st.rerun()
        note("Processing order: all CRITICAL requests first, then URGENT, then NORMAL. "
             "Inside each queue the order is first come, first served.")

    with t_queue:
        p1, p2, p3 = st.columns(3)
        with p1:
            kpi_card("Critical", len(bank.queues[1]))
        with p2:
            kpi_card("Urgent", len(bank.queues[2]), "", "warn")
        with p3:
            kpi_card("Normal", len(bank.queues[3]), "", "good")

        pending = bank.pending()
        st.subheader("Pending requests (in processing order)")
        show_table(requests_frame(bank, pending) if pending else None,
                   "No pending requests.")

        b1, b2, b3 = st.columns(3)
        with b1:
            go_next = action_button("Process next", key="process_next", primary=True)
        with b2:
            go_all = action_button("Process all", key="process_all")
        with b3:
            undo_button("undo_requests")

        if go_next:
            result = bank.process_next()
            if result is None:
                flash("info", "No pending requests.")
            else:
                st.session_state["last_results"] = [result]
            st.rerun()
        if go_all:
            results = bank.process_all()
            if results:
                st.session_state["last_results"] = results
            else:
                flash("info", "No pending requests.")
            st.rerun()

        last_results = st.session_state.get("last_results", [])
        if last_results:
            st.subheader("Latest processing result")
            for result in last_results:
                show_result(result)

    with t_history:
        done = [r for r in bank.all_requests if r.req_id in bank.results]
        st.subheader("Processed requests")
        show_table(requests_frame(bank, done) if done else None,
                   "No request has been processed yet.")
        if done:
            counts = {"Fulfilled": 0, "Partially fulfilled": 0, "Not fulfilled": 0}
            for r in done:
                counts[bank.request_status(r.req_id)] += 1
            st.caption("  |  ".join(f"{k}: {v}" for k, v in counts.items()))


def show_result(result):
    req = result.request
    status = result.status
    message = (f"{req.req_id} - {req.patient}: needed {req.units} x {req.group} "
               f"[{URGENCY[req.urgency]}]. Issued {len(result.issued)}, "
               f"shortfall {result.shortfall}.")
    if status == "Fulfilled":
        st.success(message)
    elif status == "Partially fulfilled":
        st.warning(message)
    else:
        st.error(message)
    if result.issued:
        show_table(units_frame(result.issued, bank.today))
    if result.donors:
        st.caption("Suggested eligible donors for the shortfall (project demo rules):")
        show_table(matches_frame(result.donors))


# ---------------------------------------------------------------
# page: Donor Matching
# ---------------------------------------------------------------
def matches_frame(matches):
    rows = []
    for m in matches:
        rows.append({
            "ID": m["donor_id"],
            "Name": m["name"],
            "Group": m["group"],
            "Match": m["match"],
            "Area": m["area"],
            "Distance (km)": "unknown" if m["distance_km"] is None else m["distance_km"],
            "Last donation": m["last_donation"].isoformat() if m["last_donation"] else "Not recorded",
        })
    return pd.DataFrame(rows)


def page_matching():
    page_header("Donor Matching", "Find eligible, compatible donors near a patient", "🔎")
    disclaimer("Matches use the project's compatibility table, a 90-day eligibility rule "
               "and sample road distances. They are NOT medically approved - real "
               "donors need proper screening and cross-matching.")
    a, b, c = st.columns(3)
    group = a.selectbox("Patient blood group", GROUPS, key="match_group")
    area = b.selectbox("Patient area", AREAS, key="match_area")
    limit = c.slider("Maximum donors", 1, 20, 10)

    matches = bank.find_donors(group, area, limit)
    exact = sum(1 for m in matches if m["match"] == "Exact")
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Matches found", len(matches))
    with k2:
        kpi_card("Exact group", exact, "", "good")
    with k3:
        known = [m["distance_km"] for m in matches if m["distance_km"] is not None]
        kpi_card("Nearest donor", f"{min(known)} km" if known else "-", "sample distances")

    st.subheader("Eligible compatible donors")
    st.caption("Sorted by blood-group preference (exact first, O- last), then distance.")
    show_table(matches_frame(matches) if matches else None,
               "No eligible compatible demo donors found.")

    st.subheader("Compatible blood in stock")
    stock = bank.compatible_stock(group)
    show_table(pd.DataFrame([{"Donor group": g, "Units in stock": n} for g, n in stock.items()]))

    waiting = bank.ineligible_donors(group)
    with st.expander(f"Compatible donors not yet eligible ({len(waiting)})"):
        if waiting:
            show_table(donors_frame(bank, [d for d, _ in waiting]))
        else:
            st.write("Every compatible donor is currently eligible.")


# ---------------------------------------------------------------
# page: DSA Laboratory
# ---------------------------------------------------------------
OVERVIEW_ROWS = [
    {"Structure": "AVL Tree (8, one per blood group)",
     "Used in LifeLink for": "Stock ordered by expiry date (FEFO)",
     "Why chosen": "Always balanced, so earliest-expiry lookup and range search stay fast; "
                   "a sorted list needs O(n) inserts, a heap cannot do range queries.",
     "Complexity": "insert / delete / min / pop_min: O(log n); range query: O(log n + k)"},
    {"Structure": "Queue (3, linked list)",
     "Used in LifeLink for": "Pending requests per urgency level",
     "Why chosen": "Fair first-come-first-served order inside each level; "
                   "three queues give priority between levels.",
     "Complexity": "enqueue / dequeue / enqueue_front: O(1)"},
    {"Structure": "Stack (linked list)",
     "Used in LifeLink for": "Undo of Add and Process actions",
     "Why chosen": "The latest action must be undone first (LIFO).",
     "Complexity": "push / pop / peek: O(1)"},
    {"Structure": "Directed graph (adjacency lists)",
     "Used in LifeLink for": "Which blood group can donate to which",
     "Why chosen": "Compatibility is a set of one-way relationships between groups.",
     "Complexity": "8 nodes: lookup O(1) in practice; ordering O(V log V)"},
    {"Structure": "Weighted graph + Dijkstra (min-heap)",
     "Used in LifeLink for": "Distance from the patient area to each donor area",
     "Why chosen": "Roads have different lengths; Dijkstra finds shortest paths.",
     "Complexity": "O((V + E) log V)"},
    {"Structure": "Dictionary and Set (hash tables)",
     "Used in LifeLink for": "Units by ID, donors by ID, donor IDs per blood group",
     "Why chosen": "Direct lookup by ID without scanning.",
     "Complexity": "average O(1) lookup, insert, delete"},
]


def page_dsa():
    page_header("DSA Laboratory", "Inspect the real data structures running inside LifeLink", "🧪")
    t_over, t_avl, t_sand, t_queue, t_stack, t_graph = st.tabs(
        ["Overview", "AVL Tree", "AVL Sandbox", "Queues", "Stack", "Graphs"])

    with t_over:
        st.write("Every structure below is implemented by hand in `data_structures.py` "
                 "and is used by the live system.")
        show_table(pd.DataFrame(OVERVIEW_ROWS))
        st.markdown("**How they work together:** a request waits in a **Queue**; when processed, "
                    "the **compatibility graph** gives the donor-group order; each group's "
                    "**AVL tree** gives the earliest-expiry unit; if stock is short, "
                    "**Dijkstra** ranks nearby eligible donors; the action is pushed on the "
                    "**Stack** so it can be undone.")

    with t_avl:
        group = st.selectbox("Select an inventory tree", GROUPS, key="avl_group")
        tree = bank.trees[group]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Nodes", tree.size)
        m2.metric("Height", tree.tree_height())
        m3.metric("Balanced", "Yes" if tree.is_balanced() else "No")
        m4.metric("Rotations so far", tree.rotations)
        st.caption("Each node is one blood unit. Key = (expiry date, unit ID). "
                   "The leftmost node is the earliest-expiring unit.")
        if tree.size == 0:
            st.info("This tree is empty.")
        elif tree.size <= 31:
            dot = tree.to_dot(lambda n: f"{n.value.unit_id}\\n{n.value.expiry}\\nh={n.height}")
            st.graphviz_chart(dot)
        else:
            st.info("Tree has more than 31 nodes, so only the sorted list is shown.")
        st.markdown("**In-order traversal (sorted by expiry):**")
        show_table(units_frame(tree.inorder(), bank.today) if tree.size else None, "")
        st.write("All trees balanced:", ", ".join(
            f"{g} {'OK' if ok else 'NO'}" for g, ok in bank.check_trees().items()))

    with t_sand:
        st.write("Type some numbers and watch an AVL tree keep itself balanced.")
        text = st.text_input("Keys (comma separated)", value="10, 20, 30, 40, 50, 25")
        keys = []
        bad = []
        for part in text.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                keys.append(int(part))
            except ValueError:
                bad.append(part)
        if bad:
            st.warning("Ignored (not whole numbers): " + ", ".join(bad))
        keys = keys[:40]
        sandbox = AVLTree()
        for key in keys:
            try:
                sandbox.insert((key, key), None)
            except ValueError:
                pass
        if sandbox.size == 0:
            st.info("Enter at least one whole number.")
        else:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Nodes", sandbox.size)
            s2.metric("AVL height", sandbox.tree_height())
            s3.metric("Rotations", sandbox.rotations)
            s4.metric("Plain BST height", plain_bst_height(keys))
            st.graphviz_chart(sandbox.to_dot(lambda n: n.key[0]))
            st.caption("Plain BST height is the height the same keys would give WITHOUT "
                       "balancing. Try 1, 2, 3, 4, 5, 6, 7 to see the difference.")
            st.write("In-order keys:", [k[0] for k in sandbox.inorder_keys()])

    with t_queue:
        for priority in (1, 2, 3):
            items = bank.queues[priority].to_list()
            st.markdown(f"**{URGENCY[priority]} queue** - {len(items)} request(s) "
                        "(front is processed first)")
            if items:
                show_table(pd.DataFrame([{"Position": i + 1, "ID": r.req_id,
                                          "Patient": r.patient, "Group": r.group,
                                          "Units": r.units} for i, r in enumerate(items)]))
            else:
                st.caption("Queue is empty.")
        st.caption("Between queues: Critical, then Urgent, then Normal. "
                   "Inside a queue: first in, first out.")

    with t_stack:
        actions = bank.undo_stack.to_list()
        st.write(f"Stack size: {len(actions)} (top of the stack is listed first)")
        rows = []
        for position, action in enumerate(actions):
            if action[0] == "ADD":
                rows.append({"Position": position + 1, "Action": "ADD",
                             "Detail": f"Added {action[1].unit_id} ({action[1].group})"})
            else:
                rows.append({"Position": position + 1, "Action": "PROCESS",
                             "Detail": f"Processed {action[1].req_id}"})
        show_table(pd.DataFrame(rows) if rows else None, "The undo stack is empty.")
        undo_button("undo_stack_tab")

    with t_graph:
        st.subheader("Blood compatibility (directed graph)")
        recipient = st.selectbox("Recipient blood group", GROUPS, key="compat_recipient")
        order = bank.blood_graph.preferred_order(recipient)
        st.write("Preferred donor-group order: " + " → ".join(order))
        show_table(pd.DataFrame([
            {"Donor group": d,
             "Can donate to recipient?": "Yes" if bank.blood_graph.can_donate(d, recipient) else "No"}
            for d in GROUPS]))
        st.caption("Edges go from donor group to compatible recipient group "
                   "(project table, not medical advice).")

        st.subheader("Area roads and Dijkstra (weighted graph)")
        areas = sorted(bank.area_graph.graph.keys())
        s1, s2 = st.columns(2)
        source = s1.selectbox("Start area", areas, key="dij_source")
        target = s2.selectbox("Destination area", areas, index=len(areas) - 1, key="dij_target")
        st.graphviz_chart(bank.area_graph.to_dot(source))
        distance, path = bank.area_graph.shortest_path(source, target)
        if distance is None:
            st.warning("No route between these areas.")
        else:
            st.success(f"Shortest route: {' → '.join(path)}  ({distance} km)")
        dist = bank.area_graph.dijkstra(source)
        show_table(pd.DataFrame(
            [{"Area": a, "Distance (km)": "unreachable" if d == float("inf") else d}
             for a, d in sorted(dist.items())]))
        st.caption("Distances are illustrative sample values.")


# ---------------------------------------------------------------
# page: Reports
# ---------------------------------------------------------------
def page_reports():
    page_header("Reports & Analytics", "Stock, expiry, requests and system activity", "📈")
    t_stock, t_req, t_log = st.tabs(["Stock & expiry", "Requests", "Activity log"])

    with t_stock:
        report = pd.DataFrame(bank.stock_report())
        show_table(report)
        buckets = bank.expiry_buckets()
        st.subheader("Units by time left before expiry")
        st.bar_chart(pd.DataFrame({"Units": list(buckets.values())},
                                  index=list(buckets.keys())), color="#9f1239")
        inventory = units_frame(sorted(bank.units.values(),
                                       key=lambda u: (u.expiry, u.unit_id)), bank.today)
        if len(inventory):
            st.download_button("Download inventory (CSV)",
                               inventory.to_csv(index=False).encode("utf-8"),
                               file_name="lifelink_inventory.csv", mime="text/csv")

    with t_req:
        counts = {"Pending": len(bank.pending()), "Fulfilled": 0,
                  "Partially fulfilled": 0, "Not fulfilled": 0}
        for r in bank.all_requests:
            status = bank.request_status(r.req_id)
            if status != "Pending":
                counts[status] += 1
        k = st.columns(4)
        for column, (label, value) in zip(k, counts.items()):
            with column:
                kpi_card(label, value)
        show_table(requests_frame(bank, bank.all_requests) if bank.all_requests else None,
                   "No requests yet.")

    with t_log:
        entries = bank.show_log()
        show_table(pd.DataFrame({"Activity (newest first)": list(reversed(entries))})
                   if entries else None, "No activity recorded.")


# ---------------------------------------------------------------
# router
# ---------------------------------------------------------------
if page == "Dashboard":
    page_dashboard()
elif page == "Blood Inventory":
    page_inventory()
elif page == "Donor Management":
    page_donors()
elif page == "Emergency Requests":
    page_requests()
elif page == "Donor Matching":
    page_matching()
elif page == "DSA Laboratory":
    page_dsa()
elif page == "Reports":
    page_reports()

st.divider()
st.caption("LifeLink · EE-264 DSA Course Project · Educational prototype with demo data. "
           "Not a clinical or medically validated system.")
