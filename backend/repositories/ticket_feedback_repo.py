"""<<repository>> TicketFeedbackRepo — TicketFeedback records in the ticket_feedback table (HD-13), one per ticket."""
from backend.database import next_number, store_or_memory
from backend.entities.ticket_feedback import TicketFeedback


class TicketFeedbackRepo:
    PREFIX = "FB-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def add(self, request_id, score, comment=""):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "ticket_feedback", "ticket_feedback", "feedback_id", self.PREFIX)
            feedback = TicketFeedback(f"{self.PREFIX}{number:04d}", request_id, score, comment)
            connection.execute("INSERT INTO ticket_feedback(feedback_id, request_id, score, comment, submitted_at) "
                               "VALUES (?, ?, ?, ?, ?)", (feedback.id, request_id, feedback.score, feedback.comment,
                                                          feedback.submitted_at))
        return feedback

    def for_ticket(self, request_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM ticket_feedback WHERE request_id = ?", (request_id,)).fetchone()
        return TicketFeedback(row["feedback_id"], row["request_id"], row["score"], row["comment"],
                              row["submitted_at"]) if row else None
