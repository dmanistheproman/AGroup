"""<<repository>> SupportTicketRepo — in-memory store of SupportTicket.

Numbers start at TKT-1001 so they never clash with the portal's sample tickets (TKT-4xx/5xx).
"""
from backend.entities.support_ticket import SupportTicket


class SupportTicketRepo:
    PREFIX = "TKT-"
    FIRST_NUMBER = 1001

    def __init__(self, tickets=None):
        self.items = {t.id: t for t in (tickets or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([SupportTicket(**row) for row in rows])

    def get(self, ticket_id):
        return self.items.get(ticket_id)

    def save(self, ticket):
        self.items[ticket.id] = ticket
        return ticket

    def all(self):
        return list(self.items.values())

    def for_requester(self, user_id):
        """Newest first."""
        own = [t for t in self.items.values() if t.requester_id == user_id]
        return sorted(own, key=lambda t: (t.created_at, t.id), reverse=True)

    def next_id(self):
        numbers = [int(i[len(self.PREFIX):]) for i in self.items if i.startswith(self.PREFIX) and i[len(self.PREFIX):].isdigit()]
        return f"{self.PREFIX}{max(numbers + [self.FIRST_NUMBER - 1]) + 1}"
