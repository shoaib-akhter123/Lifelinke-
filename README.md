# LifeLink - Blood Bank Inventory & Emergency Donor Matcher

EE-264 Data Structures and Algorithms course project, NED University.
Educational prototype with **demo data only**. It is not a clinical or
medically validated blood-bank system.

Live app: https://lifelink-ned.streamlit.app/

## Files

| File | Purpose |
|---|---|
| `lifelink_app.py` | Streamlit app: sidebar navigation and the 7 pages |
| `ui_components.py` | Theme (white and deep red), cards, tables, buttons |
| `blood_bank.py` | `BloodBank` controller + demo data |
| `data_structures.py` | Stack, Queue, AVL Tree, compatibility graph, area graph (Dijkstra) |
| `models.py` | Constants, helpers, BloodUnit / Donor / Request / Result |
| `test_lifelink.py` | Automated tests |
| `requirements.txt` | `streamlit`, `pandas` |

## Pages

Dashboard, Blood Inventory (add, update, discard, filter, expiry), Donor Management
(register, search, eligibility), Emergency Requests (queue, process, undo, history),
Donor Matching, DSA Laboratory, Reports.

## Data structures (all hand-written)

| Structure | Used for | Complexity |
|---|---|---|
| AVL Tree (one per blood group) | Stock ordered by expiry (FEFO) | insert / delete / min: O(log n); range query: O(log n + k) |
| 3 Queues (linked list) | Critical, Urgent, Normal requests | enqueue / dequeue: O(1) |
| Stack (linked list) | Undo of Add and Process | push / pop: O(1) |
| Directed graph | Blood group compatibility | 8 nodes, O(1) lookup in practice |
| Weighted graph + Dijkstra | Donor distance by area | O((V + E) log V) |
| Dictionary / Set | Units and donors by ID, donor IDs per group | average O(1) |

## Project rules (educational logic)

- A blood unit expires 42 days after collection.
- A donor is eligible if they never donated, or 90 or more days have passed.
- A group with fewer than 5 units is "low stock".
- Requests are processed Critical, then Urgent, then Normal (first come first served
  inside each level). Compatible blood is used exact group first, O- last.

## Limitations

- Data lives in memory (`st.session_state`). Refreshing the page or restarting the app
  resets it to the demo data, and each visitor has their own separate copy.
- Compatibility, eligibility and distances are demonstration logic, not medical advice.
- A real system would need a database, security, privacy controls and clinically
  validated rules.

## Run tests

```
python -m unittest test_lifelink -v
```

The UI test uses a fake Streamlit object to catch crashes on every page. It does not
check how pages look in a browser.
