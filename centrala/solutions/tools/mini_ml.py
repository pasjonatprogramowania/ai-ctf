"""Minimalny klasyfikator (CART) na cechach binarnych - bez scikit-learn.

Używany w zadaniu RESEARCH, żeby pokazać, że klasyfikację można zrobić
klasycznym uczeniem maszynowym, bez wywołań do LLM.
"""
from __future__ import annotations


def gini(pos: int, neg: int) -> float:
    total = pos + neg
    if total == 0:
        return 0.0
    p = pos / total
    return 2 * p * (1 - p)


class Node:
    __slots__ = ("feature", "left", "right", "value")

    def __init__(self):
        self.feature: int | None = None
        self.left: "Node | None" = None
        self.right: "Node | None" = None
        self.value: int = 0


class TinyTree:
    """Drzewo decyzyjne dla cech binarnych (podział: cecha == 1)."""

    def __init__(self, max_depth: int = 5, min_leaf: int = 8):
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.root = Node()

    def fit(self, X: list[list[int]], y: list[int]) -> "TinyTree":
        self._build(self.root, X, y, 0)
        return self

    def _build(self, node: Node, X, y, depth: int) -> None:
        pos = sum(y)
        node.value = 1 if pos * 2 >= len(y) else 0
        if depth >= self.max_depth or len(y) < 2 * self.min_leaf or pos in (0, len(y)):
            return
        base = gini(pos, len(y) - pos)
        best = None
        for f in range(len(X[0])):
            l_pos = r_pos = l_n = r_n = 0
            for row, label in zip(X, y):
                if row[f]:
                    l_n += 1
                    l_pos += label
                else:
                    r_n += 1
                    r_pos += label
            if l_n < self.min_leaf or r_n < self.min_leaf:
                continue
            gain = base - (l_n * gini(l_pos, l_n - l_pos) + r_n * gini(r_pos, r_n - r_pos)) / len(y)
            if best is None or gain > best[0]:
                best = (gain, f)
        if not best or best[0] <= 1e-9:
            return
        node.feature = best[1]
        node.left, node.right = Node(), Node()
        Xl, yl, Xr, yr = [], [], [], []
        for row, label in zip(X, y):
            (Xl if row[node.feature] else Xr).append(row)
            (yl if row[node.feature] else yr).append(label)
        self._build(node.left, Xl, yl, depth + 1)
        self._build(node.right, Xr, yr, depth + 1)

    def predict_one(self, row: list[int]) -> int:
        node = self.root
        while node.feature is not None:
            node = node.left if row[node.feature] else node.right
        return node.value

    def predict(self, X: list[list[int]]) -> list[int]:
        return [self.predict_one(row) for row in X]


def f1_score(y_true: list[int], y_pred: list[int]) -> tuple[float, float, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return f1, prec, rec


def features(bits: list[int]) -> list[int]:
    """Cechy pochodne: bity + pary XOR + progi sumy wiersza (reguła nieliniowa)."""
    out = list(bits)
    for i in range(16):
        for j in range(i + 1, 16):
            out.append(bits[i] ^ bits[j])
    total = sum(bits)
    out.extend(1 if total >= k else 0 for k in range(1, 16))
    return out
