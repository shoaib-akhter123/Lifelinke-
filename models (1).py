"""
models.py - constants, helper functions and plain record classes for LifeLink.

Educational DSA prototype. Not for clinical use.
"""

from datetime import date, datetime, timedelta, timezone

# ---------------------------------------------------------------
# Project rules (educational logic, not medical advice)
# ---------------------------------------------------------------
GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
SHELF_LIFE = 42          # days a blood unit stays usable after collection
ELIGIBILITY_DAYS = 90    # days a donor must wait between donations
LOW_STOCK = 5            # a group below this many units is "low stock"
URGENCY = {1: "CRITICAL", 2: "URGENT", 3: "NORMAL"}
URGENCY_CODE = {name: code for code, name in URGENCY.items()}
AREAS = ["NED University", "Gulshan", "Johar", "Saddar", "Clifton",
         "North Nazimabad", "Nazimabad", "PECHS", "Korangi", "Malir"]

PKT = timezone(timedelta(hours=5))   # Pakistan Standard Time (UTC+5)


def local_today():
    """Today's date in Pakistan time (cloud servers run in UTC)."""
    return datetime.now(PKT).date()


def check_group(group):
    """Clean a blood group string and make sure it is one of the 8 groups."""
    group = str(group).strip().upper()
    if group not in GROUPS:
        raise ValueError("Invalid blood group")
    return group


def read_date(value):
    """Accept a date, a datetime or an 'YYYY-MM-DD' string; return a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format")


# ---------------------------------------------------------------
# Record classes
# ---------------------------------------------------------------
class BloodUnit:
    """One physical unit of blood in stock."""

    def __init__(self, unit_id, group, collected, expiry, donor_id=None):
        self.unit_id = unit_id
        self.group = group
        self.collected = collected
        self.expiry = expiry
        self.donor_id = donor_id

    def key(self):
        """AVL ordering key: expiry date first, unit id breaks ties."""
        return (self.expiry.toordinal(), self.unit_id)

    def days_left(self, today):
        return (self.expiry - today).days


class Donor:
    """A registered (demo) donor."""

    def __init__(self, donor_id, name, group, area, last_donation=None):
        self.donor_id = donor_id
        self.name = name
        self.group = group
        self.area = area
        self.last_donation = last_donation


class Request:
    """A patient's blood request waiting in a queue."""

    def __init__(self, req_id, patient, group, units, urgency, area):
        self.req_id = req_id
        self.patient = patient
        self.group = group
        self.units = units
        self.urgency = urgency
        self.area = area


class Result:
    """Outcome of processing one request."""

    def __init__(self, request):
        self.request = request
        self.issued = []        # BloodUnit objects taken from stock
        self.shortfall = 0      # units that could not be supplied
        self.donors = []        # suggested donors (dicts) when stock is short

    @property
    def status(self):
        if self.shortfall == 0:
            return "Delivered"
        if self.issued:
            return "Partially delivered"
        return "Not delivered (no stock)"
