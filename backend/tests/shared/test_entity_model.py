"""Shared entity model: enumerations, Rating (S-11), Request base (S-19), Offer base (S-21),
Thread (S-01) and attachments (S-03)."""
import pytest

from backend.entities.enums import (AccountRole, AccountStatus, CategoryStatus, EventType, OfferStatus,
                                    ProjectPhase, ProjectStatus, TicketStatus)
from backend.entities.rating import Rating
from backend.entities.request import Request
from backend.entities.offer import Offer
from backend.entities.thread import Thread
from backend.entities.attachment import Attachment, AttachmentGroup
from backend.entities.support_ticket import SupportTicket
from backend.entities.enquiry import Enquiry
from backend.entities.verification_request import VerificationRequest
from backend.entities.design_proposal import DesignProposal
from backend.entities.quotation import Quotation
from backend.entities.user_account import UserAccount
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.thread_repo import ThreadRepo


# ---- enumerations ----

def test_enum_members_compare_equal_to_the_stored_text():
    assert AccountRole.CUSTOMER == "CUSTOMER" and AccountStatus.SUSPENDED == "SUSPENDED"
    assert ProjectStatus.HIDDEN == "HIDDEN" and OfferStatus.SUPERSEDED == "SUPERSEDED"
    assert TicketStatus.AWAITING_INFO == "AWAITING_INFO" and EventType.FAVOURITE_ADD == "FAVOURITE_ADD"


def test_category_status_and_project_phase_use_the_text_already_in_the_database():
    assert CategoryStatus.ACTIVE == "Active" and CategoryStatus.MERGED == "Merged"
    assert ProjectPhase.PAST == "Past project" and ProjectPhase.CURRENT == "Current project"


def test_project_status_lists_every_status_of_the_project_model():
    assert [s.value for s in ProjectStatus] == ["DRAFT", "PUBLISHED", "UNPUBLISHED", "HIDDEN"]


def test_user_account_constants_are_the_shared_enumerations():
    assert UserAccount.ROLE_DESIGNER is AccountRole.DESIGNER
    assert UserAccount.STATUS_ACTIVE is AccountStatus.ACTIVE
    assert set(UserAccount.ROLES) == set(AccountRole)


def test_support_ticket_statuses_are_the_shared_enumeration():
    assert SupportTicket.STATUS_OPEN is TicketStatus.OPEN
    assert SupportTicket.STATUS_MERGED is TicketStatus.MERGED


# ---- Rating (S-11) ----

@pytest.mark.parametrize("score", [1, 3, 5])
def test_rating_score_from_one_to_five_is_valid(score):
    assert Rating(score, "Lovely work").is_valid()


@pytest.mark.parametrize("score", [0, 6, -1, 2.5, "4", None, True])
def test_rating_score_outside_one_to_five_or_not_a_whole_number_is_invalid(score):
    assert not Rating(score).is_valid()


def test_rating_comment_is_trimmed_and_limited():
    assert Rating(4, "  Good  ").comment == "Good"
    assert not Rating(4, "x" * (Rating.MAX_COMMENT + 1)).is_valid()


def test_validate_raises_a_clear_message():
    with pytest.raises(ValueError, match="1 and 5"):
        Rating(7).validate()


def test_average_of_ratings_is_rounded_to_one_decimal():
    assert Rating.average([Rating(5), Rating(4), Rating(4)]) == 4.3
    assert Rating.average([]) is None


# ---- Request base (S-19) ----

def test_request_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        Request()


@pytest.mark.parametrize("cls", [SupportTicket, Enquiry, VerificationRequest])
def test_every_request_type_is_a_request(cls):
    assert issubclass(cls, Request)


def test_requester_and_handler_can_access_a_request_others_cannot():
    ticket = SupportTicket("TKT-1001", "CUS-101", "CUSTOMER", "TECHNICAL", "Broken page")
    ticket.assign_handler("user-helpdesk")
    assert ticket.can_access("CUS-101") and ticket.can_access("user-helpdesk")
    assert not ticket.can_access("CUS-102") and not ticket.can_access(None)


def test_request_keeps_its_thread_and_attachment_group():
    ticket = SupportTicket("TKT-1001", "CUS-101", "CUSTOMER", "TECHNICAL", "Broken page")
    ticket.attach("THR-0001", "AG-0001")
    assert (ticket.thread_id, ticket.attachment_group_id) == ("THR-0001", "AG-0001")


def test_set_status_changes_the_status():
    ticket = SupportTicket("TKT-1001", "CUS-101", "CUSTOMER", "TECHNICAL", "Broken page")
    ticket.set_status(TicketStatus.ESCALATED)
    assert ticket.status == "ESCALATED"


def test_existing_request_types_keep_their_own_fields():
    enquiry = Enquiry("CUS-101", "Alex Tan", "Warm materials", 60000)
    assert enquiry.status == Enquiry.STATUS_AWAITING_REPLY and enquiry.handler_id is None
    request = VerificationRequest("VR-1", "COM-001", "user-form-field")
    assert request.status == "PENDING_REVIEW" and request.thread_id is None


# ---- Offer base (S-21) ----

def test_offer_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        Offer()


@pytest.mark.parametrize("cls", [DesignProposal, Quotation])
def test_design_proposals_and_quotations_are_offers(cls):
    assert issubclass(cls, Offer)


def test_offer_lifecycle_and_reason_rule():
    assert Offer.TRANSITIONS[OfferStatus.DRAFT] == {OfferStatus.SENT}
    assert OfferStatus.DECLINED in Offer.REASON_REQUIRED


def test_existing_offer_types_keep_their_own_fields():
    proposal = DesignProposal("PRP-1", "Alex Tan", "Living room", "Warm oak")
    assert proposal.status == DesignProposal.STATUS_DRAFT and proposal.previous_offer_id is None
    assert not proposal.can_access("CUS-101")


# ---- Thread (S-01) and attachments (S-03) ----

def test_thread_repo_creates_numbered_threads():
    threads = ThreadRepo()
    first, second = threads.create(), threads.create()
    assert isinstance(first, Thread) and (first.id, second.id) == ("THR-0001", "THR-0002")
    assert threads.get("THR-0002").id == second.id


def test_attachment_group_holds_ordered_files_and_the_first_is_primary():
    repo = AttachmentRepo()
    group = repo.create_group()
    assert isinstance(group, AttachmentGroup) and group.id == "AG-0001"
    a = repo.add(group.id, "user-form-field", "living.jpg", "uploads/IDP-001/living.jpg", "image/jpeg", 2048)
    b = repo.add(group.id, "user-form-field", "kitchen.jpg", "uploads/IDP-001/kitchen.jpg", "image/jpeg", 4096,
                 caption="Kitchen")
    assert isinstance(a, Attachment)
    assert [x.file_name for x in repo.for_group(group.id)] == ["living.jpg", "kitchen.jpg"]
    assert a.is_primary and not b.is_primary and (a.sort_order, b.sort_order) == (0, 1)
    assert repo.primary_of(group.id).id == a.id


def test_set_primary_moves_the_primary_flag():
    repo = AttachmentRepo()
    group = repo.create_group()
    a = repo.add(group.id, "u", "a.jpg", "p/a.jpg")
    b = repo.add(group.id, "u", "b.jpg", "p/b.jpg")
    repo.set_primary(group.id, b.id)
    assert [x.is_primary for x in repo.for_group(group.id)] == [False, True]


def test_adding_to_an_unknown_group_is_refused():
    with pytest.raises(LookupError):
        AttachmentRepo().add("AG-9999", "u", "a.jpg", "p/a.jpg")


def test_attachment_needs_a_file_name_and_path():
    repo = AttachmentRepo()
    group = repo.create_group()
    with pytest.raises(ValueError):
        repo.add(group.id, "u", "", "p/a.jpg")
