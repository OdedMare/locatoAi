"""Deterministic union-find used by spatial clustering."""


class UnionFind:
    def __init__(self, node_count: int) -> None:
        self._parent = list(range(node_count))

    def components(self, pairs):
        for left, right in pairs:
            self._union(left, right)
        roots = [self._find(index) for index in range(len(self._parent))]
        identifiers = {}
        for root in roots:
            identifiers.setdefault(root, len(identifiers))
        return [identifiers[root] for root in roots]

    def _find(self, index: int) -> int:
        while self._parent[index] != index:
            self._parent[index] = self._parent[self._parent[index]]
            index = self._parent[index]
        return index

    def _union(self, left: int, right: int) -> None:
        left_root = self._find(left)
        right_root = self._find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root
