"""<<repository>> ThreadRepo — in-memory store of Thread (S-01)."""
from backend.entities.thread import Thread


class ThreadRepo:
    PREFIX = "THR-"

    def __init__(self):
        self.items = {}

    def create(self):
        thread = Thread(f"{self.PREFIX}{len(self.items) + 1:04d}")
        self.items[thread.id] = thread
        return thread

    def get(self, thread_id):
        return self.items.get(thread_id)
