"""
algorithms.py
-------------
Hand-written algorithms and data structures (assignment section 3).
No heapq, no Counter, no sorted()/sort()/sort_values(): everything is built
from plain lists, dicts and loops.

1. MinHeap + top_k()      Rank the K busiest routes / destinations out of
                          tens of thousands of zone pairs.
2. count_by()             Manual hash-map grouping (replaces collections.Counter).
3. quickselect_median()   Median fare of a zone without sorting all fares, using
                          three-way partitioning because taxi fares contain huge
                          runs of identical values (e.g. the $52 JFK flat fare).

Complexities (n = items, k = how many to keep):
    MinHeap.push / pop        O(log k) time
    top_k                     O(n log k) time, O(k) extra space
    count_by                  O(n) average time, O(distinct values) space
    quickselect_median        O(n) average time, O(n^2) worst case, O(n) space (copy)
"""


# ---------------------------------------------------------------------------
# 1. Min-heap (array-based binary heap)
# ---------------------------------------------------------------------------
class MinHeap:
    """
    A binary heap stored in a list. For the item at index i:
        parent = (i - 1) // 2,  left child = 2i + 1,  right child = 2i + 2
    The smallest item (by `key`) is always at index 0.
    """

    def __init__(self, key=lambda x: x):
        self._items = []
        self._key = key

    def __len__(self):
        return len(self._items)

    def peek(self):
        if not self._items:
            raise IndexError("peek from empty heap")
        return self._items[0]

    def push(self, item):
        self._items.append(item)
        self._sift_up(len(self._items) - 1)

    def pop(self):
        if not self._items:
            raise IndexError("pop from empty heap")
        top = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._sift_down(0)
        return top

    def replace_top(self, item):
        """Pop the smallest and push `item` in one O(log k) step."""
        top = self._items[0]
        self._items[0] = item
        self._sift_down(0)
        return top

    def _sift_up(self, i):
        items, key = self._items, self._key
        while i > 0:
            parent = (i - 1) // 2
            if key(items[i]) < key(items[parent]):
                items[i], items[parent] = items[parent], items[i]
                i = parent
            else:
                break

    def _sift_down(self, i):
        items, key = self._items, self._key
        n = len(items)
        while True:
            smallest = i
            left, right = 2 * i + 1, 2 * i + 2
            if left < n and key(items[left]) < key(items[smallest]):
                smallest = left
            if right < n and key(items[right]) < key(items[smallest]):
                smallest = right
            if smallest == i:
                return
            items[i], items[smallest] = items[smallest], items[i]
            i = smallest


def top_k(items, k, key):
    """
    Return the k items with the LARGEST key, largest first.

    Idea: keep a min-heap of the best k seen so far. Its root is the weakest
    of the current top k, so each new item only needs one comparison with the
    root; if it beats the root, it replaces it. Sorting everything would be
    O(n log n); this is O(n log k), and k (e.g. 10) is tiny compared with n.
    """
    if k <= 0:
        return []
    heap = MinHeap(key=key)
    for item in items:
        if len(heap) < k:
            heap.push(item)
        elif key(item) > key(heap.peek()):
            heap.replace_top(item)

    # Popping a min-heap gives smallest -> largest; fill the result backwards.
    result = [None] * len(heap)
    for i in range(len(result) - 1, -1, -1):
        result[i] = heap.pop()
    return result


# ---------------------------------------------------------------------------
# 2. Manual grouping / counting
# ---------------------------------------------------------------------------
def count_by(values):
    """Count how often each value occurs, using a dict as a hash map."""
    counts = {}
    for v in values:
        if v in counts:
            counts[v] += 1
        else:
            counts[v] = 1
    return counts


# ---------------------------------------------------------------------------
# 3. Quickselect median with three-way partitioning
# ---------------------------------------------------------------------------
def _median_of_three(a, lo, hi):
    mid = (lo + hi) // 2
    x, y, z = a[lo], a[mid], a[hi]
    if x <= y:
        if y <= z:
            return y
        return z if x <= z else x
    if x <= z:
        return x
    return z if y <= z else y


def quickselect(values, k):
    """
    Return the k-th smallest value (0-based) WITHOUT sorting the whole list.

    Each round picks a pivot and partitions the range into
        [ < pivot | == pivot | > pivot ]
    then continues only in the part that contains position k. On average the
    range halves each time: n + n/2 + n/4 + ... = O(n).

    The middle "== pivot" block matters for taxi data: thousands of fares are
    identical ($52.00 JFK flat fare, $2.50 base fare). A normal two-way
    partition keeps re-scanning those duplicates and degrades towards O(n^2);
    grouping them in one block discards all of them in a single step.
    """
    if not values:
        raise ValueError("quickselect on empty list")
    if not 0 <= k < len(values):
        raise IndexError("k out of range")

    a = list(values)              # work on a copy; the caller's list is untouched
    lo, hi = 0, len(a) - 1
    while True:
        if lo == hi:
            return a[lo]
        pivot = _median_of_three(a, lo, hi)

        # Dutch national flag partition of a[lo..hi]
        lt, i, gt = lo, lo, hi
        while i <= gt:
            if a[i] < pivot:
                a[lt], a[i] = a[i], a[lt]
                lt += 1
                i += 1
            elif a[i] > pivot:
                a[i], a[gt] = a[gt], a[i]
                gt -= 1
            else:
                i += 1
        # now: a[lo..lt-1] < pivot, a[lt..gt] == pivot, a[gt+1..hi] > pivot
        if k < lt:
            hi = lt - 1
        elif k > gt:
            lo = gt + 1
        else:
            return pivot


def quickselect_median(values):
    n = len(values)
    if n == 0:
        return None
    if n % 2 == 1:
        return quickselect(values, n // 2)
    return (quickselect(values, n // 2 - 1) + quickselect(values, n // 2)) / 2


# ---------------------------------------------------------------------------
# Self-test: python backend/algorithms.py
# (built-ins are used here ONLY to check the hand-written versions)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import random
    import statistics
    from collections import Counter

    rng = random.Random(7)
    for trial in range(200):
        data = [rng.choice([2.5, 52.0, 7.0]) if rng.random() < 0.5 else round(rng.uniform(2.5, 90), 2)
                for _ in range(rng.randint(1, 400))]
        assert quickselect_median(data) == statistics.median(data), trial

        pairs = [(rng.randint(1, 30), rng.randint(1, 30)) for _ in range(rng.randint(1, 500))]
        counts = count_by(pairs)
        assert counts == dict(Counter(pairs))
        mine = top_k(list(counts.items()), 5, key=lambda kv: (kv[1], kv[0]))
        expected = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[:5]
        assert mine == expected, (mine, expected)

    print("All algorithm self-tests passed.")