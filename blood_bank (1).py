"""
blood_bank.py - the BloodBank controller plus sample (demo) data.

BloodBank connects the data structures:
  AVL trees   -> stock per blood group, ordered by expiry (FEFO)
  3 Queues    -> pending requests (Critical, Urgent, Normal)
  Stack       -> undo history
  Graphs      -> blood compatibility and area distances
  dict / set  -> fast lookup of units, donors and donor ids by group

All records are DEMO data held in memory only. Educational prototype,
not a clinical system.
"""

from datetime import timedelta

from models import (
    GROUPS, SHELF_LIFE, ELIGIBILITY_DAYS, LOW_STOCK, URGENCY,
    BloodUnit, Donor, Request, Result,
    check_group, read_date, local_today,
)
from data_structures import Stack, Queue, AVLTree, BloodGraph, AreaGraph


class BloodBank:
    def __init__(self, today=None):
        self.today = read_date(today) if today else local_today()
        self.blood_graph = BloodGraph()
        self.area_graph = AreaGraph()
        self.trees = {g: AVLTree() for g in GROUPS}
        self.units = {}                              # unit_id -> BloodUnit
        self.donors = {}                             # donor_id -> Donor
        self.donors_by_group = {g: set() for g in GROUPS}
        self.queues = {1: Queue(), 2: Queue(), 3: Queue()}
        self.undo_stack = Stack()
        self.log = []
        self.discarded = []                          # expired / discarded units
        self.thresholds = {g: LOW_STOCK for g in GROUPS}
        self.all_requests = []                       # every request, in order
        self.results = {}                            # req_id -> Result
        self.cancelled = set()                       # cancelled request ids
        self.unit_count = 0
        self.donor_count = 0
        self.request_count = 0

    # ------------------------------------------------------------
    # log and date
    # ------------------------------------------------------------
    def add_log(self, message):
        self.log.append(f"{self.today} : {message}")
        if len(self.log) > 100:
            self.log.pop(0)

    def set_today(self, new_date):
        """Move the system date forward (used to demonstrate expiry)."""
        new_date = read_date(new_date)
        if new_date < self.today:
            raise ValueError("System date can only move forward")
        self.today = new_date
        self.remove_expired()
        self.add_log(f"System date moved to {new_date}")

    # ------------------------------------------------------------
    # inventory
    # ------------------------------------------------------------
    def total_units(self):
        return len(self.units)

    def count(self, group):
        return self.trees[group].size

    def add_unit(self, group, collected=None, donor_id=None, record_undo=True):
        group = check_group(group)
        collected = self.today if collected is None else read_date(collected)
        if collected > self.today:
            raise ValueError("Collection date cannot be in the future")
        expiry = collected + timedelta(days=SHELF_LIFE)
        if expiry < self.today:
            raise ValueError("This blood unit is already expired")
        if donor_id is not None and donor_id not in self.donors:
            raise ValueError("Donor not found")

        self.unit_count += 1
        unit_id = "U" + str(self.unit_count).zfill(4)
        unit = BloodUnit(unit_id, group, collected, expiry, donor_id)
        self.trees[group].insert(unit.key(), unit)
        self.units[unit_id] = unit

        previous_date = None
        if donor_id is not None:
            previous_date = self.donors[donor_id].last_donation
            self.donors[donor_id].last_donation = collected
        if record_undo:
            self.undo_stack.push(("ADD", unit, previous_date))
        self.add_log(f"Added {unit_id} ({group}), expires {expiry}")
        return unit

    def update_unit(self, unit_id, collected=None, group=None):
        """Change a unit's collection date and/or blood group (not undoable)."""
        unit = self.units.get(unit_id)
        if unit is None:
            raise ValueError("Blood unit not found")
        new_group = check_group(group) if group else unit.group
        new_collected = unit.collected if collected is None else read_date(collected)
        if new_collected > self.today:
            raise ValueError("Collection date cannot be in the future")
        new_expiry = new_collected + timedelta(days=SHELF_LIFE)
        if new_expiry < self.today:
            raise ValueError("Updated unit would already be expired")

        self.trees[unit.group].delete(unit.key())    # remove with the OLD key
        unit.group, unit.collected, unit.expiry = new_group, new_collected, new_expiry
        self.trees[unit.group].insert(unit.key(), unit)   # insert with NEW key
        self.add_log(f"Updated {unit_id}: group {new_group}, expires {new_expiry}")
        return unit

    def discard_unit(self, unit_id, reason="Discarded manually"):
        """Remove a unit from stock (not undoable)."""
        unit = self.units.get(unit_id)
        if unit is None:
            raise ValueError("Blood unit not found")
        self.trees[unit.group].delete(unit.key())
        del self.units[unit_id]
        self.discarded.append(unit)
        self.add_log(f"{reason}: {unit_id} ({unit.group})")
        return unit

    def remove_expired(self):
        expired = []
        for group in GROUPS:
            tree = self.trees[group]
            while True:
                unit = tree.min_unit()
                if unit is None or unit.expiry >= self.today:
                    break
                tree.pop_min()
                self.units.pop(unit.unit_id, None)
                expired.append(unit)
        if expired:
            self.discarded.extend(expired)
            self.add_log(f"Discarded {len(expired)} expired unit(s)")
        return expired

    def expiring_soon(self, days=7):
        self.remove_expired()
        low = self.today.toordinal()
        high = (self.today + timedelta(days=days)).toordinal()
        result = []
        for group in GROUPS:
            result.extend(self.trees[group].range_query(low, high))
        return sorted(result, key=lambda u: (u.expiry, u.unit_id))

    def expiry_buckets(self):
        """Number of units by days left: 0-7, 8-14, 15-28, 29+."""
        buckets = {"0-7 days": 0, "8-14 days": 0, "15-28 days": 0, "29+ days": 0}
        for unit in self.units.values():
            left = unit.days_left(self.today)
            if left <= 7:
                buckets["0-7 days"] += 1
            elif left <= 14:
                buckets["8-14 days"] += 1
            elif left <= 28:
                buckets["15-28 days"] += 1
            else:
                buckets["29+ days"] += 1
        return buckets

    # ------------------------------------------------------------
    # donors
    # ------------------------------------------------------------
    def register_donor(self, name, group, area, last_donation=None):
        group = check_group(group)
        name = str(name).strip()
        if not name:
            raise ValueError("Donor name cannot be empty")
        if not str(area).strip():
            raise ValueError("Area cannot be empty")
        if last_donation is not None:
            last_donation = read_date(last_donation)
            if last_donation > self.today:
                raise ValueError("Last donation date cannot be in the future")
        self.donor_count += 1
        donor_id = "D" + str(self.donor_count).zfill(3)
        self.donors[donor_id] = Donor(donor_id, name, group, area, last_donation)
        self.donors_by_group[group].add(donor_id)
        self.add_log(f"Registered donor {donor_id} ({group})")
        return donor_id

    def is_eligible(self, donor):
        return (donor.last_donation is None
                or (self.today - donor.last_donation).days >= ELIGIBILITY_DAYS)

    def days_until_eligible(self, donor):
        if self.is_eligible(donor):
            return 0
        return ELIGIBILITY_DAYS - (self.today - donor.last_donation).days

    def search_donors(self, text="", group=None, eligible_only=False):
        """Filter donors by name / id text, blood group and eligibility."""
        text = str(text).strip().lower()
        if group:
            pool = [self.donors[i] for i in self.donors_by_group[check_group(group)]]
        else:
            pool = list(self.donors.values())
        found = []
        for donor in pool:
            if text and text not in donor.name.lower() and text not in donor.donor_id.lower():
                continue
            if eligible_only and not self.is_eligible(donor):
                continue
            found.append(donor)
        return sorted(found, key=lambda d: d.donor_id)

    def find_donors(self, group, area=None, limit=10):
        """Eligible donors whose group is compatible with the needed group.
        Sorted by preferred group order, then distance, then donor id."""
        group = check_group(group)
        distances = self.area_graph.dijkstra(area) if area else {}
        candidates = []
        for rank, donor_group in enumerate(self.blood_graph.preferred_order(group)):
            for donor_id in self.donors_by_group[donor_group]:
                donor = self.donors[donor_id]
                if self.is_eligible(donor):
                    distance = distances.get(donor.area, float("inf"))
                    candidates.append((rank, distance, donor_id, donor))
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        matches = []
        for _, distance, _, donor in candidates[:limit]:
            matches.append({
                "donor_id": donor.donor_id,
                "name": donor.name,
                "group": donor.group,
                "match": "Exact" if donor.group == group else "Compatible",
                "area": donor.area,
                "distance_km": None if distance == float("inf") else distance,
                "last_donation": donor.last_donation,
            })
        return matches

    def ineligible_donors(self, group):
        """Compatible donors who are NOT yet eligible: [(Donor, days to wait)]."""
        group = check_group(group)
        rows = []
        for donor_group in self.blood_graph.preferred_order(group):
            for donor_id in self.donors_by_group[donor_group]:
                donor = self.donors[donor_id]
                if not self.is_eligible(donor):
                    rows.append((donor, self.days_until_eligible(donor)))
        return sorted(rows, key=lambda row: (row[1], row[0].donor_id))

    # ------------------------------------------------------------
    # requests
    # ------------------------------------------------------------
    def submit_request(self, patient, group, units, urgency, area):
        patient = str(patient).strip()
        if not patient:
            raise ValueError("Patient name cannot be empty")
        group = check_group(group)
        if int(units) < 1:
            raise ValueError("Units must be at least 1")
        if int(urgency) not in URGENCY:
            raise ValueError("Invalid urgency")
        self.request_count += 1
        req = Request("R" + str(self.request_count).zfill(3), patient, group,
                      int(units), int(urgency), area)
        self.queues[req.urgency].enqueue(req)
        self.all_requests.append(req)
        self.add_log(f"Submitted {req.req_id} ({URGENCY[req.urgency]}, "
                     f"{req.units} x {group})")
        return req

    def pending(self):
        """Pending requests: Critical first, then Urgent, then Normal."""
        return [r for p in (1, 2, 3) for r in self.queues[p].to_list()]

    def request_status(self, req_id):
        if req_id in self.cancelled:
            return "Cancelled"
        result = self.results.get(req_id)
        return "Pending" if result is None else result.status

    def next_request(self):
        """The request that will be delivered next (not removed)."""
        for priority in (1, 2, 3):
            if not self.queues[priority].is_empty():
                return self.queues[priority].peek()
        return None

    def delivery_preview(self):
        """Next request plus how many compatible units are in stock for it."""
        request = self.next_request()
        if request is None:
            return None
        self.remove_expired()
        available = sum(self.count(g) for g in self.blood_graph.preferred_order(request.group))
        return {"request": request, "available": available,
                "short": max(0, request.units - available)}

    def cancel_request(self, req_id):
        """Remove a pending request from its queue (not undoable)."""
        for priority in (1, 2, 3):
            request = self.queues[priority].remove_where(lambda r: r.req_id == req_id)
            if request is not None:
                self.cancelled.add(req_id)
                self.add_log(f"Cancelled {req_id}")
                return request
        raise ValueError("Request is not pending")

    def recent_requests(self, limit=5):
        return list(reversed(self.all_requests))[:limit]

    def process_next(self):
        request = None
        for priority in (1, 2, 3):
            if not self.queues[priority].is_empty():
                request = self.queues[priority].dequeue()
                break
        if request is None:
            return None

        self.remove_expired()
        result = Result(request)
        for donor_group in self.blood_graph.preferred_order(request.group):
            tree = self.trees[donor_group]
            while len(result.issued) < request.units and tree.min_unit() is not None:
                unit = tree.pop_min()              # earliest expiry first
                self.units.pop(unit.unit_id, None)
                result.issued.append(unit)
        result.shortfall = request.units - len(result.issued)
        if result.shortfall:
            result.donors = self.find_donors(request.group, request.area, 10)

        self.results[request.req_id] = result
        self.undo_stack.push(("PROCESS", request, result.issued, result))
        self.add_log(f"Processed {request.req_id}: issued {len(result.issued)}, "
                     f"shortfall {result.shortfall}")
        return result

    def process_all(self):
        results = []
        while self.pending():
            results.append(self.process_next())
        return results

    # ------------------------------------------------------------
    # undo (supports ADD and PROCESS only)
    # ------------------------------------------------------------
    def undo_label(self):
        action = self.undo_stack.peek()
        if action is None:
            return None
        if action[0] == "ADD":
            return f"Add {action[1].unit_id}"
        return f"Process {action[1].req_id}"

    def undo(self):
        """Undo the latest supported action. Returns (success, message)."""
        action = self.undo_stack.pop()
        if action is None:
            return False, "Nothing to undo."
        if action[0] == "ADD":
            _, unit, previous_date = action
            if unit.unit_id not in self.units:
                return True, f"{unit.unit_id} is no longer in stock; entry dropped."
            self.trees[unit.group].delete(unit.key())
            del self.units[unit.unit_id]
            if unit.donor_id and unit.donor_id in self.donors:
                self.donors[unit.donor_id].last_donation = previous_date
            self.add_log(f"Undo: removed {unit.unit_id}")
            return True, f"Undone: {unit.unit_id} removed from stock."
        if action[0] == "PROCESS":
            _, request, issued, _result = action
            for unit in issued:
                self.trees[unit.group].insert(unit.key(), unit)
                self.units[unit.unit_id] = unit
            self.queues[request.urgency].enqueue_front(request)
            self.results.pop(request.req_id, None)
            self.add_log(f"Undo: restored {request.req_id} to its queue")
            return True, f"Undone: {request.req_id} is back at the front of its queue."
        return False, "Unknown action."

    # ------------------------------------------------------------
    # reports
    # ------------------------------------------------------------
    def stock_report(self):
        rows = []
        for group in GROUPS:
            earliest = self.trees[group].min_unit()
            units = self.count(group)
            rows.append({
                "Blood group": group,
                "Units": units,
                "Earliest expiry": earliest.expiry.isoformat() if earliest else "-",
                "Status": "LOW STOCK" if units < self.thresholds[group] else "OK",
            })
        return rows

    def compatible_stock(self, recipient):
        recipient = check_group(recipient)
        return {g: self.count(g) for g in self.blood_graph.preferred_order(recipient)}

    def low_stock(self):
        return [g for g in GROUPS if self.count(g) < self.thresholds[g]]

    def show_log(self):
        return list(self.log)

    def check_trees(self):
        return {g: self.trees[g].is_balanced() for g in GROUPS}


# ---------------------------------------------------------------
# Sample data (illustrative only - no real people or stock)
# ---------------------------------------------------------------
def load_roads(bank):
    roads = [
        ("NED University", "Gulshan", 4), ("Gulshan", "Johar", 7),
        ("Gulshan", "PECHS", 9), ("PECHS", "Saddar", 5),
        ("Saddar", "Clifton", 8), ("Johar", "Malir", 12),
        ("Johar", "Korangi", 14), ("Gulshan", "North Nazimabad", 10),
        ("North Nazimabad", "Nazimabad", 6), ("Nazimabad", "Saddar", 11),
        ("PECHS", "Korangi", 13), ("Clifton", "Korangi", 10),
    ]
    for a, b, km in roads:
        bank.area_graph.add_road(a, b, km)


DEMO_STOCK = {"O-": 4, "O+": 8, "A-": 3, "A+": 9,
              "B-": 6, "B+": 7, "AB-": 2, "AB+": 5}


def load_demo(bank):
    load_roads(bank)
    demo_donors = [
        ("Ali Demo", "A+", "Gulshan", 120), ("Sara Demo", "O-", "Johar", None),
        ("Usman Demo", "B+", "Saddar", 150), ("Hira Demo", "AB+", "Clifton", 30),
        ("Ahmed Demo", "O+", "PECHS", 100), ("Mina Demo", "A-", "North Nazimabad", None),
        ("Bilal Demo", "B-", "Malir", 200), ("Noor Demo", "AB-", "Nazimabad", 110),
        ("Zain Demo", "O-", "Korangi", 95), ("Ayesha Demo", "A+", "Johar", 45),
    ]
    for name, group, area, days in demo_donors:
        last = bank.today - timedelta(days=days) if days is not None else None
        bank.register_donor(name, group, area, last)

    # Collection dates are spread over ~40 days so some units expire soon.
    for index, group in enumerate(GROUPS):
        for i in range(DEMO_STOCK[group]):
            days_ago = (i * 5 + index * 3) % 40
            bank.add_unit(group, bank.today - timedelta(days=days_ago),
                          record_undo=False)

    bank.submit_request("Demo Patient 1", "O-", 2, 1, "NED University")
    bank.submit_request("Demo Patient 2", "A+", 3, 2, "Gulshan")
    bank.submit_request("Demo Patient 3", "B+", 1, 3, "Clifton")

    bank.undo_stack = Stack()      # demo setup must not be undoable
    bank.add_log("Demo data loaded")
