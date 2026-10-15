"""Inventario do jogador: guarda quantidades por id de item."""
from catalog import ITEMS, WEAPON, TOOL


class Inventory:
    def __init__(self):
        self.counts = {}
        self.on_change = None      # funcao chamada sempre que algo muda

    def count(self, item_id):
        return self.counts.get(item_id, 0)

    def has(self, item_id, amount=1):
        return self.count(item_id) >= amount

    def space_for(self, item_id):
        return ITEMS[item_id].max_stack - self.count(item_id)

    def add(self, item_id, amount=1):
        """Adiciona ate o limite da pilha. Retorna quanto realmente entrou."""
        added = max(0, min(amount, self.space_for(item_id)))
        if added:
            self.counts[item_id] = self.count(item_id) + added
            self._changed()
        return added

    def remove(self, item_id, amount=1):
        if not self.has(item_id, amount):
            return False
        self.counts[item_id] -= amount
        if self.counts[item_id] <= 0:
            del self.counts[item_id]
        self._changed()
        return True

    def has_all(self, cost):
        return all(self.has(i, n) for i, n in cost.items())

    def remove_all(self, cost):
        if not self.has_all(cost):
            return False
        for i, n in cost.items():
            self.remove(i, n)
        return True

    def items_of(self, *kinds):
        """Itens possuidos de certos tipos, na ordem do catalogo."""
        return [ITEMS[i] for i in ITEMS if self.count(i) > 0 and ITEMS[i].kind in kinds]

    def equippables(self):
        return self.items_of(WEAPON, TOOL)

    def _changed(self):
        if self.on_change:
            self.on_change()
