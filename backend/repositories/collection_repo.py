"""<<repository>> CollectionRepo — collections and their items in the collection and collection_item tables (S-22)."""
from datetime import datetime, timezone

from backend.database import next_number, store_or_memory
from backend.entities.collection import Collection, CollectionItem, Moodboard

ITEM_COLUMNS = ("item_id", "collection_id", "project_id", "attachment_id", "item_type", "colour", "note", "sort_order")


def _number(reference):
    return int(str(reference).split("-")[1]) if reference else None


class CollectionRepo:
    PREFIX = "COL-"
    ITEM_PREFIX = "ITEM-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    # ---- collections ----
    def create(self, customer_id, name, kind):
        with self.store.transaction(write=True) as connection:
            collection_id = f"{self.PREFIX}{next_number(connection, 'collection', 'collection', 'collection_id', self.PREFIX):04d}"
            connection.execute("INSERT INTO collection(collection_id, customer_id, name, kind, created_at) "
                               "VALUES (?, ?, ?, ?, ?)",
                               (collection_id, customer_id, name, kind, datetime.now(timezone.utc).isoformat()))
        return self.get(collection_id)

    def get(self, collection_id):
        found = self._select("WHERE collection_id = ?", (collection_id,))
        return found[0] if found else None

    def for_customer(self, customer_id):
        return self._select("WHERE customer_id = ?", (customer_id,), "name COLLATE NOCASE, collection_id")

    def rename(self, collection_id, name):
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE collection SET name = ? WHERE collection_id = ?", (name, collection_id))

    def set_share_token(self, collection_id, token):
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE collection SET share_token = ? WHERE collection_id = ?", (token, collection_id))

    def by_share_token(self, token):
        found = self._select("WHERE share_token = ?", (token,)) if token else []
        return found[0] if found else None

    def delete(self, collection_id):
        with self.store.transaction(write=True) as connection:
            connection.execute("DELETE FROM collection_item WHERE collection_id = ?", (collection_id,))
            connection.execute("DELETE FROM collection WHERE collection_id = ?", (collection_id,))

    # ---- items ----
    def add_item(self, collection_id, item_type, project_id=None, colour=None, note=None, attachment_id=None):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "collection_item", "collection_item", "item_id", self.ITEM_PREFIX)
            order = connection.execute("SELECT COUNT(*) FROM collection_item WHERE collection_id = ?",
                                       (collection_id,)).fetchone()[0]
            item = CollectionItem(f"{self.ITEM_PREFIX}{number:05d}", collection_id, item_type, project_id,
                                  attachment_id=attachment_id, colour=colour, note=note, sort_order=order)
            connection.execute(f"INSERT INTO collection_item({', '.join(ITEM_COLUMNS)}) "
                               f"VALUES ({', '.join('?' * len(ITEM_COLUMNS))})",
                               (item.id, collection_id, _number(project_id), attachment_id, item_type, colour, note,
                                order))
        return item

    def items(self, collection_id):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM collection_item WHERE collection_id = ? ORDER BY sort_order, item_id",
                                      (collection_id,)).fetchall()
        return [CollectionItem(r["item_id"], r["collection_id"], r["item_type"],
                               f"IDP-{r['project_id']:03d}" if r["project_id"] is not None else None,
                               r["attachment_id"], r["colour"], r["note"], r["sort_order"]) for r in rows]

    def remove_item(self, item_id):
        with self.store.transaction(write=True) as connection:
            connection.execute("DELETE FROM collection_item WHERE item_id = ?", (item_id,))

    def set_order(self, item_ids):
        with self.store.transaction(write=True) as connection:
            connection.executemany("UPDATE collection_item SET sort_order = ? WHERE item_id = ?",
                                   [(order, item_id) for order, item_id in enumerate(item_ids)])

    def remove_project_for_customer(self, customer_id, project_reference):
        with self.store.transaction(write=True) as connection:
            connection.execute("DELETE FROM collection_item WHERE project_id = ? AND collection_id IN "
                               "(SELECT collection_id FROM collection WHERE customer_id = ?)",
                               (_number(project_reference), customer_id))

    def _select(self, where, args, order="collection_id"):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM collection {where} ORDER BY {order}", args).fetchall()
        result = []
        for r in rows:
            cls = Moodboard if r["kind"] == Collection.KIND_MOODBOARD else Collection
            extra = {} if cls is Moodboard else {"kind": r["kind"]}
            result.append(cls(r["collection_id"], r["customer_id"], r["name"], attachment_group_id=r["attachment_group_id"],
                              share_token=r["share_token"], created_at=r["created_at"], **extra))
        return result
