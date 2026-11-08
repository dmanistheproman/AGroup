"""<<entity>> Offer — abstract base of documents an ID sends to a client about a request (S-21).

DesignProposal (ID-05) and Quotation (ID-07) are offers: each has revisions, a feedback thread (S-01),
files (S-03) and the client's answer. A new revision points to the one it replaces.

Lifecycle for StatusChangeService (S-04): Draft -> Sent -> Accepted / Declined / Superseded.
Subclasses may keep their own statuses by overriding TRANSITIONS and REASON_REQUIRED.
The class-level defaults below let existing subclasses that do not call Offer.__init__ work as before.
"""
from backend.entities.enums import OfferStatus


class Offer:
    request_id = None
    previous_offer_id = None
    thread_id = None
    attachment_group_id = None
    revision = 1
    status = None
    sent_at = None
    answered_at = None

    TRANSITIONS = {
        OfferStatus.DRAFT: {OfferStatus.SENT},
        OfferStatus.SENT: {OfferStatus.ACCEPTED, OfferStatus.DECLINED, OfferStatus.SUPERSEDED},
    }
    REASON_REQUIRED = frozenset({OfferStatus.DECLINED})

    def __new__(cls, *args, **kwargs):
        if cls is Offer:
            raise TypeError("Offer is abstract. Create a DesignProposal or Quotation.")
        return super().__new__(cls)

    def set_status(self, status):
        self.status = status

    def participant_ids(self):
        """The client and the ID who may see this offer. Subclasses that know them override this."""
        return ()

    def can_access(self, user_id):
        return user_id is not None and user_id in self.participant_ids()
