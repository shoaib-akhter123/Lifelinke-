# ============================================================
# LIFELINK - BLOOD BANK INVENTORY & EMERGENCY DONOR MATCHER
# EE-264 Data Structures and Algorithms Course Project
# Educational demonstration prototype only.
# ============================================================

from datetime import date, timedelta
import streamlit as st
import pandas as pd

GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
SHELF_LIFE = 42
ELIGIBILITY_DAYS = 90
LOW_STOCK = 5
URGENCY = {1: "CRITICAL", 2: "URGENT", 3: "NORMAL"}
AREAS = ["NED University", "Gulshan", "Johar", "Saddar", "Clifton",
         "North Nazimabad", "Nazimabad", "PECHS", "Korangi", "Malir"]

def check_group(group):
    group = group.strip().upper()
    if group not in GROUPS:
        raise ValueError("Invalid blood group")
    return group

def read_date(value):
    return date.fromisoformat(str(value))

class Node:
    def __init__(self, data):
        self.data, self.next = data, None

class Stack:
    def __init__(self): self.top = None
    def push(self, data):
        node = Node(data); node.next = self.top; self.top = node
    def pop(self):
        if self.top is None: return None
        data = self.top.data; self.top = self.top.next; return data
    def is_empty(self): return self.top is None
    def to_list(self):
        out, cur = [], self.top
        while cur: out.append(cur.data); cur = cur.next
        return out

class Queue:
    def __init__(self): self.front = self.rear = None
    def enqueue(self, data):
        node = Node(data)
        if self.rear is None: self.front = self.rear = node
        else: self.rear.next = node; self.rear = node
    def enqueue_front(self, data):
        node = Node(data); node.next = self.front; self.front = node
        if self.rear is None: self.rear = node
    def dequeue(self):
        if self.front is None: return None
        data = self.front.data; self.front = self.front.next
        if self.front is None: self.rear = None
        return data
    def is_empty(self): return self.front is None
    def to_list(self):
        out, cur = [], self.front
        while cur: out.append(cur.data); cur = cur.next
        return out
    def __len__(self):
        n, cur = 0, self.front
        while cur: n += 1; cur = cur.next
        return n

class AVLNode:
    def __init__(self, key, unit):
        self.key, self.unit = key, unit
        self.left = self.right = None
        self.height = 1

class AVLTree:
    def __init__(self): self.root, self.size = None, 0
    def height(self, node): return node.height if node else 0
    def update_height(self, node):
        node.height = 1 + max(self.height(node.left), self.height(node.right))
    def balance(self, node): return self.height(node.left) - self.height(node.right)
    def rotate_right(self, root):
        new_root = root.left; root.left = new_root.right; new_root.right = root
        self.update_height(root); self.update_height(new_root); return new_root
    def rotate_left(self, root):
        new_root = root.right; root.right = new_root.left; new_root.left = root
        self.update_height(root); self.update_height(new_root); return new_root
    def rebalance(self, node):
        self.update_height(node); b = self.balance(node)
        if b > 1:
            if self.balance(node.left) < 0: node.left = self.rotate_left(node.left)
            return self.rotate_right(node)
        if b < -1:
            if self.balance(node.right) > 0: node.right = self.rotate_right(node.right)
            return self.rotate_left(node)
        return node
    def insert(self, key, unit):
        self.root = self._insert(self.root, key, unit); self.size += 1
    def _insert(self, root, key, unit):
        if root is None: return AVLNode(key, unit)
        if key < root.key: root.left = self._insert(root.left, key, unit)
        elif key > root.key: root.right = self._insert(root.right, key, unit)
        else: raise ValueError("Duplicate unit key")
        return self.rebalance(root)
    def delete(self, key):
        self.root, deleted = self._delete(self.root, key)
        if deleted: self.size -= 1
        return deleted
    def _delete(self, root, key):
        if root is None: return None, False
        if key < root.key: root.left, deleted = self._delete(root.left, key)
        elif key > root.key: root.right, deleted = self._delete(root.right, key)
        else:
            deleted = True
            if root.left is None: return root.right, True
            if root.right is None: return root.left, True
            successor = root.right
            while successor.left: successor = successor.left
            root.key, root.unit = successor.key, successor.unit
            root.right, _ = self._delete(root.right, successor.key)
        if root is None: return None, deleted
        return self.rebalance(root), deleted
    def min_unit(self):
        cur = self.root
        if cur is None: return None
        while cur.left: cur = cur.left
        return cur.unit
    def pop_min(self):
        unit = self.min_unit()
        if unit is not None: self.delete(unit.key())
        return unit
    def range_query(self, low, high):
        result = []
        def walk(node):
            if not node: return
            if low <= node.key[0]: walk(node.left)
            if low <= node.key[0] <= high: result.append(node.unit)
            if node.key[0] <= high: walk(node.right)
        walk(self.root); return result
    def inorder(self):
        out = []
        def walk(n):
            if n:
                walk(n.left); out.append(n.unit); walk(n.right)
        walk(self.root); return out
    def structure(self):
        """Read-only nested representation for truthful tree visualization."""
        def walk(n):
            if not n: return None
            return {"id": n.unit.unit_id, "expiry": n.unit.expiry.isoformat(),
                    "height": n.height, "left": walk(n.left), "right": walk(n.right)}
        return walk(self.root)
    def is_balanced(self):
        def check(n):
            if not n: return True, 0
            lok, lh = check(n.left); rok, rh = check(n.right)
            return lok and rok and abs(lh-rh) <= 1, 1 + max(lh, rh)
        return check(self.root)[0]

class BloodGraph:
    def __init__(self):
        self.graph = {
            "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
            "O+": ["O+", "A+", "B+", "AB+"],
            "A-": ["A-", "A+", "AB-", "AB+"],
            "A+": ["A+", "AB+"], "B-": ["B-", "B+", "AB-", "AB+"],
            "B+": ["B+", "AB+"], "AB-": ["AB-", "AB+"], "AB+": ["AB+"]
        }
        self.reverse_graph = {g: [] for g in GROUPS}
        for donor in GROUPS:
            for recipient in self.graph[donor]:
                self.reverse_graph[recipient].append(donor)
    def can_donate(self, donor, recipient): return recipient in self.graph[donor]
    def donors_for(self, recipient): return self.reverse_graph[recipient]
    def preferred_order(self, recipient):
        donors = self.donors_for(recipient)
        others = [g for g in donors if g != recipient]
        others.sort(key=lambda g: (len(self.graph[g]), g))
        return [recipient] + others

class AreaGraph:
    def __init__(self): self.graph = {}
    def add_road(self, a, b, distance):
        if distance <= 0: raise ValueError("Distance must be positive")
        self.graph.setdefault(a, {}); self.graph.setdefault(b, {})
        self.graph[a][b] = distance; self.graph[b][a] = distance
    def dijkstra(self, source):
        if source not in self.graph: return {}
        dist = {a: float("inf") for a in self.graph}; dist[source] = 0
        visited = set()
        while len(visited) < len(self.graph):
            current = min((a for a in self.graph if a not in visited),
                          key=lambda a: dist[a], default=None)
            if current is None or dist[current] == float("inf"): break
            visited.add(current)
            for neighbour, weight in self.graph[current].items():
                candidate = dist[current] + weight
                if candidate < dist[neighbour]: dist[neighbour] = candidate
        return dist

class BloodUnit:
    def __init__(self, unit_id, group, collected, expiry, donor_id=None):
        self.unit_id, self.group = unit_id, group
        self.collected, self.expiry, self.donor_id = collected, expiry, donor_id
    def key(self): return (self.expiry.toordinal(), self.unit_id)

class Donor:
    def __init__(self, donor_id, name, group, area, last_donation=None):
        self.donor_id, self.name, self.group = donor_id, name, group
        self.area, self.last_donation = area, last_donation

class Request:
    def __init__(self, req_id, patient, group, units, urgency, area):
        self.req_id, self.patient, self.group = req_id, patient, group
        self.units, self.urgency, self.area = units, urgency, area

class Result:
    def __init__(self, request):
        self.request = request; self.issued = []; self.shortfall = 0; self.donors = []

class BloodBank:
    def __init__(self):
        self.today = date.today()
        self.blood_graph, self.area_graph = BloodGraph(), AreaGraph()
        self.trees = {g: AVLTree() for g in GROUPS}
        self.units, self.donors = {}, {}
        self.donors_by_group = {g: set() for g in GROUPS}
        self.queues = {1: Queue(), 2: Queue(), 3: Queue()}
        self.undo_stack = Stack()
        self.log, self.discarded = [], []
        self.thresholds = {g: LOW_STOCK for g in GROUPS}
        self.unit_count = self.donor_count = self.request_count = 0
    def add_log(self, message):
        self.log.append(f"{self.today} : {message}")
        if len(self.log) > 100: self.log.pop(0)
    def set_today(self, new_date):
        self.today = read_date(new_date); self.remove_expired(); self.add_log("Date updated")
    def total_units(self): return len(self.units)
    def count(self, group): return self.trees[group].size
    def add_unit(self, group, collected=None, donor_id=None, record_undo=True):
        group = check_group(group)
        if collected is None: collected = self.today
        if isinstance(collected, str): collected = read_date(collected)
        if collected > self.today: raise ValueError("Collection date cannot be in future")
        expiry = collected + timedelta(days=SHELF_LIFE)
        if expiry < self.today: raise ValueError("Blood unit is already expired")
        if donor_id is not None and donor_id not in self.donors: raise ValueError("Donor not found")
        self.unit_count += 1; unit_id = "U" + str(self.unit_count).zfill(4)
        unit = BloodUnit(unit_id, group, collected, expiry, donor_id)
        self.trees[group].insert(unit.key(), unit); self.units[unit_id] = unit
        previous_date = None
        if donor_id is not None:
            previous_date = self.donors[donor_id].last_donation
            self.donors[donor_id].last_donation = collected
        if record_undo: self.undo_stack.push(("ADD", unit, previous_date))
        self.add_log(f"Added {unit_id} ({group})")
        return unit
    def remove_expired(self):
        expired = []
        for group in GROUPS:
            tree = self.trees[group]
            while True:
                unit = tree.min_unit()
                if unit is None or unit.expiry >= self.today: break
                tree.pop_min(); self.units.pop(unit.unit_id, None); expired.append(unit)
        if expired:
            self.discarded.extend(expired)
            self.add_log(f"Discarded {len(expired)} expired units")
        return expired
    def expiring_soon(self, days=7):
        self.remove_expired()
        low, high = self.today.toordinal(), (self.today + timedelta(days=days)).toordinal()
        result = []
        for group in GROUPS: result.extend(self.trees[group].range_query(low, high))
        return sorted(result, key=lambda u: (u.expiry, u.unit_id))
    def register_donor(self, name, group, area, last_donation=None):
        group = check_group(group)
        if not name.strip(): raise ValueError("Name cannot be empty")
        if last_donation is not None:
            if isinstance(last_donation, str): last_donation = read_date(last_donation)
            if last_donation > self.today: raise ValueError("Donation date cannot be in future")
        self.donor_count += 1; donor_id = "D" + str(self.donor_count).zfill(3)
        self.donors[donor_id] = Donor(donor_id, name.strip(), group, area, last_donation)
        self.donors_by_group[group].add(donor_id); self.add_log(f"Registered donor {donor_id}")
        return donor_id
    def is_eligible(self, donor):
        return donor.last_donation is None or (self.today - donor.last_donation).days >= ELIGIBILITY_DAYS
    def find_donors(self, group, area=None, limit=10):
        group = check_group(group)
        distances = self.area_graph.dijkstra(area) if area else {}
        candidates = []
        for rank, donor_group in enumerate(self.blood_graph.preferred_order(group)):
            for donor_id in self.donors_by_group[donor_group]:
                donor = self.donors[donor_id]
                if self.is_eligible(donor):
                    distance = distances.get(donor.area, float("inf"))
                    candidates.append((rank, distance, donor_id, donor))
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        return [{"donor_id": d.donor_id, "name": d.name, "group": d.group,
                 "area": d.area, "distance_km": None if dist == float("inf") else dist}
                for _, dist, _, d in candidates[:limit]]
    def submit_request(self, patient, group, units, urgency, area):
        if not patient.strip(): raise ValueError("Patient name cannot be empty")
        group = check_group(group)
        if int(units) < 1: raise ValueError("Units must be at least 1")
        if int(urgency) not in URGENCY: raise ValueError("Invalid urgency")
        self.request_count += 1
        req = Request("R" + str(self.request_count).zfill(3), patient.strip(),
                      group, int(units), int(urgency), area)
        self.queues[req.urgency].enqueue(req)
        self.add_log(f"Submitted {req.req_id} ({URGENCY[req.urgency]})")
        return req
    def pending(self):
        return [r for p in (1, 2, 3) for r in self.queues[p].to_list()]
    def process_next(self):
        request = None
        for priority in (1, 2, 3):
            if not self.queues[priority].is_empty():
                request = self.queues[priority].dequeue(); break
        if request is None: return None
        self.remove_expired()
        result = Result(request)
        for donor_group in self.blood_graph.preferred_order(request.group):
            tree = self.trees[donor_group]
            while len(result.issued) < request.units and tree.min_unit() is not None:
                unit = tree.pop_min()
                self.units.pop(unit.unit_id, None)
                result.issued.append(unit)
        result.shortfall = request.units - len(result.issued)
        if result.shortfall:
            result.donors = self.find_donors(request.group, request.area, 10)
        self.undo_stack.push(("PROCESS", request, result.issued))
        self.add_log(f"Processed {request.req_id}: issued {len(result.issued)}, shortfall {result.shortfall}")
        return result
    def process_all(self):
        results = []
        while self.pending():
            result = self.process_next()
            if result: results.append(result)
        return results
    def undo(self):
        action = self.undo_stack.pop()
        if action is None: return False
        kind = action[0]
        if kind == "ADD":
            _, unit, previous_date = action
            self.trees[unit.group].delete(unit.key()); self.units.pop(unit.unit_id, None)
            if unit.donor_id and unit.donor_id in self.donors:
                self.donors[unit.donor_id].last_donation = previous_date
            self.add_log(f"Undo: removed {unit.unit_id}")
        elif kind == "PROCESS":
            _, request, issued = action
            for unit in issued:
                self.trees[unit.group].insert(unit.key(), unit); self.units[unit.unit_id] = unit
            self.queues[request.urgency].enqueue_front(request)
            self.add_log(f"Undo: restored processing of {request.req_id}")
        else: return False
        return True
    def stock_report(self):
        rows = []
        for group in GROUPS:
            earliest = self.trees[group].min_unit()
            rows.append({"Blood group": group, "Units": self.count(group),
                         "Earliest expiry": earliest.expiry.isoformat() if earliest else "—",
                         "Status": "LOW STOCK" if self.count(group) < self.thresholds[group] else "OK"})
        return rows
    def compatible_stock(self, recipient):
        recipient = check_group(recipient)
        return {g: self.count(g) for g in self.blood_graph.preferred_order(recipient)}
    def low_stock(self):
        return [g for g in GROUPS if self.count(g) < self.thresholds[g]]
    def show_log(self): return list(self.log) or ["No activity recorded."]
    def check_trees(self): return {g: self.trees[g].is_balanced() for g in GROUPS}

def load_roads(bank):
    roads = [
        ("NED University", "Gulshan", 4), ("Gulshan", "Johar", 7),
        ("Gulshan", "PECHS", 9), ("PECHS", "Saddar", 5),
        ("Saddar", "Clifton", 8), ("Johar", "Malir", 12),
        ("Johar", "Korangi", 14), ("Gulshan", "North Nazimabad", 10),
        ("North Nazimabad", "Nazimabad", 6), ("Nazimabad", "Saddar", 11),
        ("PECHS", "Korangi", 13), ("Clifton", "Korangi", 10)
    ]
    for a, b, km in roads: bank.area_graph.add_road(a, b, km)

def load_demo(bank):
    load_roads(bank)
    # Sample records are illustrative, not real donors or stock.
    demo_donors = [
        ("Ali Demo", "A+", "Gulshan", 120), ("Sara Demo", "O-", "Johar", None),
        ("Usman Demo", "B+", "Saddar", 150), ("Hira Demo", "AB+", "Clifton", 30),
        ("Ahmed Demo", "O+", "PECHS", 100), ("Mina Demo", "A-", "North Nazimabad", None),
        ("Bilal Demo", "B-", "Malir", 200), ("Noor Demo", "AB-", "Nazimabad", 110),
        ("Zain Demo", "O-", "Korangi", 95), ("Ayesha Demo", "A+", "Johar", 45)
    ]
    donor_ids = {}
    for name, group, area, days in demo_donors:
        last = bank.today - timedelta(days=days) if days is not None else None
        donor_ids[name] = bank.register_donor(name, group, area, last)
    for group in GROUPS:
        for i in range(3):
            collected = bank.today - timedelta(days=(i * 5 + (GROUPS.index(group) % 3)))
            bank.add_unit(group, collected, record_undo=False)
    # Extra units make the FEFO order and stock counts more visible.
    bank.add_unit("A+", bank.today - timedelta(days=35), record_undo=False)
    bank.add_unit("O-", bank.today - timedelta(days=20), record_undo=False)
    bank.undo_stack = Stack()
    bank.add_log("Demo data loaded")

# --------------------------- STREAMLIT UI ---------------------------
st.set_page_config(page_title="LifeLink | Blood Bank DSA", page_icon="🩸",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
.hero {padding: 1.25rem 1.5rem; border-radius: 16px;
       background: linear-gradient(120deg,#172554,#991b1b); color:white; margin-bottom:1rem;}
.hero h1 {color:white; margin:0; font-size:2.1rem;}
.hero p {color:#fee2e2; margin:.35rem 0 0 0;}
.small-note {color:#64748b; font-size:.85rem;}
</style>
""", unsafe_allow_html=True)

if "bank" not in st.session_state:
    bank = BloodBank(); load_demo(bank); st.session_state.bank = bank
bank = st.session_state.bank

with st.sidebar:
    st.markdown("## 🩸 LifeLink")
    st.caption("Blood Bank Inventory & Emergency Donor Matcher")
    page = st.radio("Navigation", ["Dashboard", "Blood Inventory", "Donor Management",
                                   "Patient Requests", "DSA Laboratory", "Activity Log"])
    st.divider()
    st.caption(f"System date: {bank.today}")
    if st.button("Reset Demo Data", use_container_width=True):
        fresh = BloodBank(); load_demo(fresh); st.session_state.bank = fresh
        st.rerun()
    st.caption("Educational prototype. Not for clinical use.")

st.markdown('<div class="hero"><h1>🩸 LifeLink</h1><p>Smart blood inventory and emergency donor matching system</p></div>',
            unsafe_allow_html=True)

def units_frame(units):
    return pd.DataFrame([{"Unit ID": u.unit_id, "Blood Group": u.group,
                          "Collection": u.collected.isoformat(), "Expiry": u.expiry.isoformat(),
                          "Donor ID": u.donor_id or "—"} for u in units])

if page == "Dashboard":
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total blood units", bank.total_units())
    c2.metric("Registered donors", len(bank.donors))
    c3.metric("Pending requests", len(bank.pending()))
    c4.metric("Low-stock groups", len(bank.low_stock()))
    st.subheader("Inventory by blood group")
    stock = pd.DataFrame(bank.stock_report())
    st.bar_chart(stock.set_index("Blood group")["Units"], color="#b91c1c")
    left,right = st.columns(2)
    with left:
        st.subheader("Low-stock alerts")
        low = bank.low_stock()
        if low: st.warning("Low stock: " + ", ".join(low))
        else: st.success("No low-stock alerts.")
    with right:
        st.subheader("Requests waiting by priority")
        st.write({URGENCY[p]: len(bank.queues[p]) for p in (1,2,3)})
    st.subheader("Expiring within 7 days")
    exp = bank.expiring_soon(7)
    if exp:
    st.dataframe(
        units_frame(exp),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No units expiring within 7 days.")
elif page == "Blood Inventory":
    st.subheader("Add blood unit")
    with st.form("add_unit_form"):
        a,b,c = st.columns(3)
        group = a.selectbox("Blood group", GROUPS)
        collected = b.date_input("Collection date", value=bank.today)
        donor_options = ["No linked donor"] + list(bank.donors.keys())
        donor = c.selectbox("Donor record (optional)", donor_options)
        submitted = st.form_submit_button("Add blood unit", type="primary")
    if submitted:
        try:
            unit = bank.add_unit(group, collected, None if donor == "No linked donor" else donor)
            st.success(f"Added {unit.unit_id}. Expiry: {unit.expiry}")
        except Exception as e: st.error(str(e))
    st.subheader("Current inventory")
    chosen = st.selectbox("Filter by blood group", ["All groups"] + GROUPS)
    rows = [u for u in bank.units.values() if chosen == "All groups" or u.group == chosen]
    st.dataframe(units_frame(sorted(rows, key=lambda x:(x.expiry,x.unit_id))),
                 use_container_width=True, hide_index=True)
    st.subheader("Expiry report")
    days = st.slider("Show units expiring within days", 1, 42, 7)
    exp = bank.expiring_soon(days)
    st.dataframe(units_frame(exp), use_container_width=True, hide_index=True) if exp else st.info("No matching units.")

elif page == "Donor Management":
    st.subheader("Register a donor")
    with st.form("donor_form"):
        a,b = st.columns(2)
        name = a.text_input("Donor name")
        group = b.selectbox("Blood group", GROUPS)
        c,d = st.columns(2)
        area = c.selectbox("Area", AREAS)
        has_last = d.checkbox("Previous donation date is known")
        last = st.date_input("Last donation date", value=bank.today-timedelta(days=120),
                             disabled=not has_last)
        submit = st.form_submit_button("Register donor", type="primary")
    if submit:
        try:
            donor_id = bank.register_donor(name, group, area, last if has_last else None)
            st.success(f"Donor registered: {donor_id}")
        except Exception as e: st.error(str(e))
    st.subheader("Donor directory")
    donor_rows = []
    for d in bank.donors.values():
        donor_rows.append({"ID":d.donor_id,"Name":d.name,"Group":d.group,"Area":d.area,
                           "Last donation":d.last_donation.isoformat() if d.last_donation else "Not recorded",
                           "Eligibility (project rule)":"Eligible" if bank.is_eligible(d) else "Not yet eligible"})
    st.dataframe(pd.DataFrame(donor_rows), use_container_width=True, hide_index=True)
    st.subheader("Find compatible eligible donors")
    a,b = st.columns(2)
    target = a.selectbox("Required blood group", GROUPS, key="find_group")
    target_area = b.selectbox("Patient area", AREAS, key="find_area")
    if st.button("Find matching donors"):
        matches = bank.find_donors(target, target_area)
        if matches: st.dataframe(pd.DataFrame(matches), use_container_width=True, hide_index=True)
        else: st.info("No eligible compatible demo donors found.")

elif page == "Patient Requests":
    st.subheader("Submit patient request")
    with st.form("request_form"):
        a,b,c = st.columns(3)
        patient = a.text_input("Patient name / demo label")
        group = b.selectbox("Required blood group", GROUPS)
        quantity = c.number_input("Units required", min_value=1, max_value=20, value=2)
        d,e = st.columns(2)
        urgency_label = d.selectbox("Urgency", ["CRITICAL","URGENT","NORMAL"])
        area = e.selectbox("Patient area", AREAS)
        submit = st.form_submit_button("Add request to queue", type="primary")
    if submit:
        try:
            priority = {"CRITICAL":1,"URGENT":2,"NORMAL":3}[urgency_label]
            req = bank.submit_request(patient, group, quantity, priority, area)
            st.success(f"Request {req.req_id} added to {urgency_label} queue.")
        except Exception as e: st.error(str(e))
    x,y = st.columns(2)
    if x.button("Process next request", type="primary", use_container_width=True):
        result = bank.process_next()
        if result is None: st.info("No pending requests.")
        else:
            st.session_state.last_result = result
            st.rerun()
    if y.button("Process all requests", use_container_width=True):
        results = bank.process_all()
        st.session_state.batch_results = results
        st.rerun()
    if "last_result" in st.session_state:
        r = st.session_state.last_result
        st.subheader(f"Latest result: {r.request.req_id}")
        st.write(f"Patient: **{r.request.patient}** | Required: **{r.request.units} × {r.request.group}** | Priority: **{URGENCY[r.request.urgency]}**")
        st.metric("Units issued", len(r.issued))
        st.metric("Shortfall", r.shortfall)
        if r.issued: st.dataframe(units_frame(r.issued), use_container_width=True, hide_index=True)
        if r.donors: st.write("Eligible donor suggestions (project demo rules):"); st.dataframe(pd.DataFrame(r.donors), use_container_width=True, hide_index=True)
    if st.session_state.get("batch_results"):
        st.subheader("Batch processing results")
        for r in st.session_state.batch_results:
            st.write(f"{r.request.req_id} · {r.request.patient} · issued {len(r.issued)} · shortfall {r.shortfall}")
    st.subheader("Pending requests")
    pending_rows = [{"ID":r.req_id,"Patient":r.patient,"Group":r.group,"Units":r.units,
                     "Urgency":URGENCY[r.urgency],"Area":r.area} for r in bank.pending()]
    st.dataframe(pd.DataFrame(pending_rows), use_container_width=True, hide_index=True) if pending_rows else st.info("No pending requests.")
    if st.button("Undo latest supported operation"):
        if bank.undo(): st.success("Latest supported operation undone."); st.rerun()
        else: st.info("Nothing to undo.")

elif page == "DSA Laboratory":
    st.subheader("Live data-structure inspection")
    tab1,tab2,tab3,tab4,tab5 = st.tabs(["AVL Trees","Priority Queues","Undo Stack","Compatibility Graph","Area Graph / Dijkstra"])
    with tab1:
        g = st.selectbox("Select inventory tree", GROUPS)
        tree = bank.trees[g]
        st.write(f"Nodes: {tree.size} | Height: {tree.height(tree.root)} | Balanced: {'Yes' if tree.is_balanced() else 'No'}")
        st.caption("In-order traversal shows units sorted by expiry date (FEFO).")
        st.dataframe(units_frame(tree.inorder()), use_container_width=True, hide_index=True)
        st.json(tree.structure() or {"tree":"Empty"})
        st.write("All AVL trees balanced:", bank.check_trees())
    with tab2:
        for p in (1,2,3):
            st.markdown(f"**{URGENCY[p]} queue · {len(bank.queues[p])} request(s)**")
            qrows = [{"ID":r.req_id,"Patient":r.patient,"Group":r.group,"Units":r.units} for r in bank.queues[p].to_list()]
            if qrows: st.dataframe(pd.DataFrame(qrows), use_container_width=True, hide_index=True)
            else: st.caption("Queue is empty.")
        st.caption("FIFO is preserved inside each urgency queue; processing checks Critical, then Urgent, then Normal.")
    with tab3:
        actions = bank.undo_stack.to_list()
        st.write(f"Stack size: {len(actions)}")
        st.write("Top of stack is shown first.")
        st.write([a[0] + (": " + (a[1].unit_id if a[0]=="ADD" else a[1].req_id)) for a in actions])
        if st.button("Undo top stack action", key="stack_undo"):
            if bank.undo(): st.success("Undo completed."); st.rerun()
            else: st.info("Stack is empty.")
    with tab4:
        recipient = st.selectbox("Recipient blood group", GROUPS, key="compat_recipient")
        order = bank.blood_graph.preferred_order(recipient)
        st.write("Preferred compatible donor-group order:", " → ".join(order))
        matrix = [{"Donor":d,"Can donate to recipient?":"Yes" if bank.blood_graph.can_donate(d,recipient) else "No"} for d in GROUPS]
        st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)
        st.caption("Directed edges represent donor group → compatible recipient group, using the project's predefined compatibility table.")
    with tab5:
        source = st.selectbox("Starting area", sorted(bank.area_graph.graph.keys()))
        distances = bank.area_graph.dijkstra(source)
        st.write(f"Shortest estimated distances from **{source}** (sample road network)")
        st.dataframe(pd.DataFrame([{"Area":a,"Distance (km)":"Unreachable" if d==float("inf") else d}
                                   for a,d in distances.items()]).sort_values("Area"),
                     use_container_width=True, hide_index=True)
        st.caption("Dijkstra uses the sample weighted, undirected area graph. Distances are illustrative demo values.")

elif page == "Activity Log":
    st.subheader("Recent system activity")
    st.code("\n".join(bank.show_log()))
    st.subheader("Discarded expired units")
    st.dataframe(units_frame(bank.discarded), use_container_width=True, hide_index=True) if bank.discarded else st.info("No expired units discarded.")

st.divider()
st.caption("LifeLink · EE-264 DSA Course Project · Educational prototype only. Not for clinical use.")
