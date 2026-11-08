"""<<repository>> ProposalRepo — DesignProposal records (shared offers, S-21).

Stored as the ER diagram's offer base row plus a design_proposal row.
The ID-05 and ID-06 controllers share one ProposalRepo.
"""
import json

from backend.database import exists, next_number, save_offer, store_or_memory
from backend.entities.design_proposal import DesignProposal

SEED_PROPOSAL_DATA = [
    {"proposal_id": "PROP-801", "client_name": "Alex Tan", "title": "Concept proposal",
     "description": "Living room and storage plan. Warm palette with a defined dining corner.",
     "status": "UNDER_REVIEW", "version": 2,
     "feedback": "Prefer lighter oak and more enclosed storage.",
     "feedback_history": ["Initial layout felt too open; please define a dining corner."]},
    {"proposal_id": "PROP-802", "client_name": "Casey Lim", "title": "Layout proposal",
     "description": "Open kitchen concept with a quiet home office nook.",
     "status": "UNDER_REVIEW", "version": 1},
    {"proposal_id": "PROP-803", "client_name": "Meera Raj", "title": "Material board",
     "description": "Material and finish palette for the child-safe renovation.",
     "status": "DRAFT", "version": 1},
]

OFFER_TYPE = "DESIGN_PROPOSAL"


class ProposalRepo:
    PREFIX = "PROP-"
    FIRST_NUMBER = 801

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed proposals that are missing; stored proposals keep their changes."""
        repo = cls(store)
        for row in rows:
            with repo.store.transaction() as connection:
                if exists(connection, "offer", "offer_id", row["proposal_id"]):
                    continue
            repo.save(DesignProposal(**row))
        return repo

    def get(self, proposal_id):
        found = self._select("WHERE o.offer_id = ?", (proposal_id,))
        return found[0] if found else None

    def save(self, proposal):
        with self.store.transaction(write=True) as connection:
            save_offer(connection, proposal, OFFER_TYPE)
            connection.execute("""
                INSERT INTO design_proposal(offer_id, client_name, title, design_description, attachments, feedback,
                                            feedback_history, revision_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(offer_id) DO UPDATE SET client_name = excluded.client_name, title = excluded.title,
                    design_description = excluded.design_description, attachments = excluded.attachments,
                    feedback = excluded.feedback, feedback_history = excluded.feedback_history,
                    revision_note = excluded.revision_note
            """, (proposal.id, proposal.client_name, proposal.title, proposal.description,
                  json.dumps(proposal.attachments), proposal.feedback, json.dumps(proposal.feedback_history),
                  proposal.revision_note))
        return proposal

    def all(self):
        return self._select("", ())

    def next_reference(self):
        """Next proposal number, continuing after the seeds (PROP-801 when empty)."""
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "design_proposal", "offer", "offer_id", self.PREFIX,
                                 first=self.FIRST_NUMBER)
        return f"{self.PREFIX}{number}"

    def _select(self, where, args):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM offer o JOIN design_proposal p ON p.offer_id = o.offer_id "
                                      f"{where} ORDER BY o.offer_id", args).fetchall()
        return [DesignProposal(row["offer_id"], row["client_name"], row["title"], row["design_description"],
                               attachments=json.loads(row["attachments"]), status=row["status"],
                               version=row["revision"], feedback=row["feedback"],
                               feedback_history=json.loads(row["feedback_history"]),
                               revision_note=row["revision_note"]) for row in rows]
