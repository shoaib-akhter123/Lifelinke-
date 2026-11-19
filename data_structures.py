"""
data_structures.py - every data structure used by LifeLink, written by hand.

Stack, Queue, AVL Tree, directed blood-compatibility graph and a weighted
area graph (Dijkstra). Educational implementations - no external libraries
except Python's heapq for the Dijkstra priority queue.
"""

import heapq

from models import GROUPS


# ---------------------------------------------------------------
# Linked-list node (shared by Stack and Queue)
# ---------------------------------------------------------------
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


# ---------------------------------------------------------------
# Stack (LIFO) - used for Undo.   push / pop / peek: O(1)
# ---------------------------------------------------------------
class Stack:
    def __init__(self):
        self.top = None
        self.size = 0

    def push(self, data):
        node = Node(data)
        node.next = self.top
        self.top = node
        self.size += 1

    def pop(self):
        if self.top is None:
            return None
        data = self.top.data
        self.top = self.top.next
        self.size -= 1
        return data

    def peek(self):
        return None if self.top is None else self.top.data

    def is_empty(self):
        return self.top is None

    def to_list(self):
        """Items from top to bottom (read-only view for display)."""
        items, cur = [], self.top
        while cur:
            items.append(cur.data)
            cur = cur.next
        return items

    def __len__(self):
        return self.size


# ---------------------------------------------------------------
# Queue (FIFO) - used for patient requests.
# enqueue / enqueue_front / dequeue / len: O(1)   (front + rear pointers)
# ---------------------------------------------------------------
class Queue:
    def __init__(self):
        self.front = None
        self.rear = None
        self.size = 0

    def enqueue(self, data):
        node = Node(data)
        if self.rear is None:
            self.front = self.rear = node
        else:
            self.rear.next = node
            self.rear = node
        self.size += 1

    def enqueue_front(self, data):
        """Put an item back at the front (used by Undo)."""
        node = Node(data)
        node.next = self.front
        self.front = node
        if self.rear is None:
            self.rear = node
        self.size += 1

    def dequeue(self):
        if self.front is None:
            return None
        data = self.front.data
        self.front = self.front.next
        if self.front is None:
            self.rear = None
        self.size -= 1
        return data

    def is_empty(self):
        return self.front is None

    def to_list(self):
        items, cur = [], self.front
        while cur:
            items.append(cur.data)
            cur = cur.next
        return items

    def __len__(self):
        return self.size


# ---------------------------------------------------------------
# AVL Tree - one per blood group, ordered by expiry key.
# insert / delete / min / pop_min: O(log n)
# range_query: O(log n + k)      in-order listing: O(n)
# ---------------------------------------------------------------
class AVLNode:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.left = None
        self.right = None
        self.height = 1


class AVLTree:
    def __init__(self):
        self.root = None
        self.size = 0
        self.rotations = 0     # counts rotations (shown in the DSA Lab)

    # ----- balance helpers -----
    def height(self, node):
        return node.height if node else 0

    def tree_height(self):
        return self.height(self.root)

    def update_height(self, node):
        node.height = 1 + max(self.height(node.left), self.height(node.right))

    def balance(self, node):
        return self.height(node.left) - self.height(node.right)

    def rotate_right(self, root):
        new_root = root.left
        root.left = new_root.right
        new_root.right = root
        self.update_height(root)
        self.update_height(new_root)
        self.rotations += 1
        return new_root

    def rotate_left(self, root):
        new_root = root.right
        root.right = new_root.left
        new_root.left = root
        self.update_height(root)
        self.update_height(new_root)
        self.rotations += 1
        return new_root

    def rebalance(self, node):
        self.update_height(node)
        b = self.balance(node)
        if b > 1:                                   # left heavy
            if self.balance(node.left) < 0:         # left-right case
                node.left = self.rotate_left(node.left)
            return self.rotate_right(node)
        if b < -1:                                  # right heavy
            if self.balance(node.right) > 0:        # right-left case
                node.right = self.rotate_right(node.right)
            return self.rotate_left(node)
        return node

    # ----- insert -----
    def insert(self, key, value=None):
        self.root = self._insert(self.root, key, value)
        self.size += 1

    def _insert(self, node, key, value):
        if node is None:
            return AVLNode(key, value)
        if key < node.key:
            node.left = self._insert(node.left, key, value)
        elif key > node.key:
            node.right = self._insert(node.right, key, value)
        else:
            raise ValueError("Duplicate key")
        return self.rebalance(node)

    # ----- delete -----
    def delete(self, key):
        self.root, deleted = self._delete(self.root, key)
        if deleted:
            self.size -= 1
        return deleted

    def _delete(self, node, key):
        if node is None:
            return None, False
        if key < node.key:
            node.left, deleted = self._delete(node.left, key)
        elif key > node.key:
            node.right, deleted = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right, True
            if node.right is None:
                return node.left, True
            # two children: copy the in-order successor, then delete it
            successor = node.right
            while successor.left:
                successor = successor.left
            node.key, node.value = successor.key, successor.value
            node.right, deleted = self._delete(node.right, successor.key)
        return self.rebalance(node), deleted

    # ----- earliest expiry -----
    def _min_node(self):
        node = self.root
        if node is None:
            return None
        while node.left:
            node = node.left
        return node

    def min_unit(self):
        node = self._min_node()
        return None if node is None else node.value

    def pop_min(self):
        node = self._min_node()
        if node is None:
            return None
        value = node.value
        self.delete(node.key)
        return value

    # ----- range search on the first part of the key -----
    def range_query(self, low, high):
        result = []

        def walk(node):
            if node is None:
                return
            if low <= node.key[0]:
                walk(node.left)
            if low <= node.key[0] <= high:
                result.append(node.value)
            if node.key[0] <= high:
                walk(node.right)

        walk(self.root)
        return result

    # ----- views for display / checking -----
    def inorder(self):
        out = []

        def walk(node):
            if node:
                walk(node.left)
                out.append(node.value)
                walk(node.right)

        walk(self.root)
        return out

    def inorder_keys(self):
        out = []

        def walk(node):
            if node:
                walk(node.left)
                out.append(node.key)
                walk(node.right)

        walk(self.root)
        return out

    def is_balanced(self):
        def check(node):
            if node is None:
                return True, 0
            left_ok, left_h = check(node.left)
            right_ok, right_h = check(node.right)
            ok = left_ok and right_ok and abs(left_h - right_h) <= 1
            return ok, 1 + max(left_h, right_h)

        return check(self.root)[0]

    def to_dot(self, label_fn):
        """Graphviz DOT text of the real tree (None if empty)."""
        if self.root is None:
            return None
        lines = [
            "digraph AVL {",
            '  node [shape=box, style="rounded,filled", fillcolor="#fee2e2", '
            'color="#991b1b", fontname="Helvetica", fontsize=11];',
            '  edge [color="#7f1d1d"];',
        ]
        counter = [0]

        def walk(node):
            my_id = counter[0]
            counter[0] += 1
            label = str(label_fn(node)).replace('"', "'")
            lines.append(f'  n{my_id} [label="{label}"];')
            for child in (node.left, node.right):
                if child is not None:
                    child_id = walk(child)
                    lines.append(f"  n{my_id} -> n{child_id};")
            return my_id

        walk(self.root)
        lines.append("}")
        return "\n".join(lines)


def plain_bst_height(keys):
    """Height of an ordinary (unbalanced) BST built from keys - for comparison."""
    root = None
    height = 0
    nodes = {}                      # key -> [left, right]
    for key in keys:
        if key in nodes:
            continue
        nodes[key] = [None, None]
        if root is None:
            root = key
            height = max(height, 1)
            continue
        cur, depth = root, 1
        while True:
            depth += 1
            side = 0 if key < cur else 1
            if nodes[cur][side] is None:
                nodes[cur][side] = key
                break
            cur = nodes[cur][side]
        height = max(height, depth)
    return height


# ---------------------------------------------------------------
# Blood compatibility graph (directed): donor group -> recipient groups
# ---------------------------------------------------------------
class BloodGraph:
    def __init__(self):
        self.graph = {
            "O-":  ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
            "O+":  ["O+", "A+", "B+", "AB+"],
            "A-":  ["A-", "A+", "AB-", "AB+"],
            "A+":  ["A+", "AB+"],
            "B-":  ["B-", "B+", "AB-", "AB+"],
            "B+":  ["B+", "AB+"],
            "AB-": ["AB-", "AB+"],
            "AB+": ["AB+"],
        }
        # reverse view: recipient group -> donor groups that can supply it
        self.reverse_graph = {g: [] for g in GROUPS}
        for donor in GROUPS:
            for recipient in self.graph[donor]:
                self.reverse_graph[recipient].append(donor)

    def can_donate(self, donor, recipient):
        return recipient in self.graph[donor]

    def donors_for(self, recipient):
        return self.reverse_graph[recipient]

    def preferred_order(self, recipient):
        """Exact group first; then groups that serve fewer recipients, so the
        universal donor (O-) is kept for last."""
        others = [g for g in self.donors_for(recipient) if g != recipient]
        others.sort(key=lambda g: (len(self.graph[g]), g))
        return [recipient] + others


# ---------------------------------------------------------------
# Area graph (weighted, undirected) + Dijkstra with a min-heap
# Dijkstra: O((V + E) log V)
# ---------------------------------------------------------------
class AreaGraph:
    def __init__(self):
        self.graph = {}

    def add_road(self, a, b, distance):
        if distance <= 0:
            raise ValueError("Distance must be positive")
        self.graph.setdefault(a, {})
        self.graph.setdefault(b, {})
        self.graph[a][b] = distance
        self.graph[b][a] = distance

    def _run(self, source):
        """Return (distance dict, previous-area dict)."""
        if source not in self.graph:
            return {}, {}
        dist = {area: float("inf") for area in self.graph}
        prev = {}
        dist[source] = 0
        heap = [(0, source)]
        while heap:
            d, area = heapq.heappop(heap)
            if d > dist[area]:
                continue                      # stale heap entry
            for neighbour, weight in self.graph[area].items():
                candidate = d + weight
                if candidate < dist[neighbour]:
                    dist[neighbour] = candidate
                    prev[neighbour] = area
                    heapq.heappush(heap, (candidate, neighbour))
        return dist, prev

    def dijkstra(self, source):
        return self._run(source)[0]

    def shortest_path(self, source, target):
        """(distance, [areas along the route]) or (None, []) if unreachable."""
        dist, prev = self._run(source)
        if target not in dist or dist[target] == float("inf"):
            return None, []
        path = [target]
        while path[-1] != source:
            path.append(prev[path[-1]])
        path.reverse()
        return dist[target], path

    def to_dot(self, source=None):
        lines = [
            "graph Roads {",
            '  node [shape=ellipse, style=filled, fillcolor="#ffffff", '
            'color="#991b1b", fontname="Helvetica", fontsize=11];',
            '  edge [color="#7f1d1d", fontname="Helvetica", fontsize=10];',
        ]
        for area in sorted(self.graph):
            if area == source:
                lines.append(f'  "{area}" [fillcolor="#fecaca", penwidth=2];')
        done = set()
        for a in sorted(self.graph):
            for b, w in sorted(self.graph[a].items()):
                if (b, a) not in done:
                    lines.append(f'  "{a}" -- "{b}" [label="{w} km"];')
                    done.add((a, b))
        lines.append("}")
        return "\n".join(lines)
