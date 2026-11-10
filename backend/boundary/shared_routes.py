"""Boundary: shared HTTP routes — Contact Support, Report IDP, the helpdesk ticket queue, the ticket page,
project status, record history and notifications (S-04, S-05, S-07, S-15, S-17, S-20).

`shared` is the namespace of shared services built in server.py (app.extensions["shared"]).
"""
from flask import Blueprint, current_app, jsonify, request

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.enums import ProjectStatus
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

REQUESTERS = (UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)
STAFF = (UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN, UserAccount.ROLE_PLATFORM_MANAGER)


def helpdesk():
    """The helpdesk's control classes (HD stories), built in server.py after the shared parts."""
    return current_app.extensions["helpdesk"]


def customer():
    """The customer's control classes (C stories), built in server.py."""
    return current_app.extensions["customer"]


def create_shared_blueprint(shared):
    login = shared.login
    bp = Blueprint("shared", __name__)

    # ---- error mapping (see backend/CONVENTIONS.md) ----
    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(AuthenticationError)
    def unauthenticated(err):
        return jsonify(error=str(err)), 401

    @bp.errorhandler(PermissionError)
    def forbidden(err):
        return jsonify(error=str(err)), 403

    @bp.errorhandler(LookupError)
    def not_found(err):
        return jsonify(error=str(err).strip("'\"")), 404

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON request body.")
        return data

    # ---- Open Support Request (ContactSupportForm) ----
    @bp.post("/api/support/tickets")
    @require_role(login, *REQUESTERS)
    def open_support_request():
        data = body()
        ticket = shared.submit_ticket.submit_ticket(login.current_user(), data.get("type"), data.get("details"))
        return jsonify(ticket=ticket.public_view()), 201

    @bp.get("/api/support/tickets/mine")
    @require_role(login, *REQUESTERS)
    def my_tickets():
        tickets = shared.requests.list_for_requester(login.current_user().id)
        return jsonify(tickets=[t.public_view() for t in tickets])

    # ---- Helpdesk ticket queue (ListPage, S-05):
    #      ?scope=active|done&status=&type=<type>|REPORTS&handler=me|none&q=&page=&page_size= ----
    @bp.get("/api/support/tickets")
    @require_role(login, UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN)
    def ticket_queue():
        """HD-03 / HD-06 (UA-12: the User Admin sees the tickets escalated to them)."""
        return jsonify(helpdesk().view_ticket_queue_controller.queue(login.current_user(), request.args))

    def name_of(user_id, cache):
        """Display name of an account (cached per request)."""
        if not user_id:
            return None
        if user_id not in cache:
            account = shared.user_accounts.get(user_id)
            cache[user_id] = account.name if account else user_id
        return cache[user_id]

    # ---- Ticket page for requesters and agents (RecordPage, S-20) ----
    def ticket_page(ticket):
        user = login.current_user()
        is_agent = user.role == UserAccount.ROLE_HELPDESK
        messages = shared.messages.list_messages(ticket.thread_id, user) if ticket.thread_id else []
        history = shared.ticket_lifecycle.history_of(ticket.id)
        reported = shared.message_repo.get(ticket.related_message_id) if ticket.related_message_id else None
        names = {}
        for person in [ticket.requester_id, ticket.handler_id] + [m.author_id for m in messages] +                 [e.actor_id for e in history] + ([reported.author_id] if reported else []):
            name_of(person, names)
        feedback = shared.ticket_feedback.for_ticket(ticket.id)   # HD-13: private to helpdesk staff
        return jsonify(ticket=ticket.public_view(),
                       messages=[m.public_view() for m in messages],
                       history=[e.public_view() for e in history], names=names,
                       reported_message=reported.public_view() if reported else None,
                       allowed_statuses=shared.ticket_lifecycle.allowed_for(ticket.id, user),
                       feedback=feedback.public_view() if feedback and is_agent else None,
                       feedback_given=feedback is not None,
                       can_give_feedback=(ticket.requester_id == user.id and feedback is None
                                          and ticket.status == SupportTicket.STATUS_CLOSED))

    def find_ticket(ticket_id):
        ticket = shared.tickets.get(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket {ticket_id} was not found.")
        return ticket

    @bp.get("/api/support/tickets/<ticket_id>")
    @require_role(login, *REQUESTERS, UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN)
    def view_ticket(ticket_id):
        ticket = find_ticket(ticket_id)
        user = login.current_user()
        if user.role == UserAccount.ROLE_USER_ADMIN:
            if not shared.ticket_lifecycle.was_escalated(ticket.id):   # UA-12: escalated tickets only
                raise PermissionError("The User Admin sees tickets escalated by the helpdesk.")
        elif user.role != UserAccount.ROLE_HELPDESK and not ticket.can_access(user.id):
            raise PermissionError("You can only view your own requests.")
        return ticket_page(ticket)

    # ---- Request page for its requester and handler: enquiries, verification requests, tickets (S-19, S-20) ----
    @bp.get("/api/requests/<request_id>")
    @require_role(login)
    def view_request(request_id):
        user = login.current_user()
        found = shared.requests.find_for(user, request_id)
        kind = shared.requests.type_of(found)
        if kind == "SUPPORT_TICKET":
            return ticket_page(found)
        found = shared.requests.ensure_thread(found)
        messages = shared.messages.list_messages(found.thread_id, user)
        history = shared.status_change.history_of(kind, found.id)
        record = {"id": found.id, "kind": kind, "status": found.status, "created_at": found.created_at,
                  "requester_id": found.requester_id, "handler_id": found.handler_id, "thread_id": found.thread_id}
        extra = {}
        if kind == "ENQUIRY":
            record.update(title="Enquiry", summary=found.requirements, budget=found.budget,
                          client_name=found.client_name, decided_at=found.decided_at,
                          decision_reason=found.decision_reason, questions=found.questions)
            review = shared.reviews.reviews.for_request(found.id)
            extra = {"can_review": shared.reviews.can_review(user, found),
                     "review": {"rating": review.rating, "comment": review.comment, "date": review.date}
                     if review else None}
        else:
            record.update(title="Verification request", summary=f"{len(found.documents)} document(s)",
                          **found.public_view())
        names = {}
        for person in [found.requester_id, found.handler_id] + [m.author_id for m in messages] + \
                [e.actor_id for e in history]:
            name_of(person, names)
        return jsonify(request=record, messages=[m.public_view() for m in messages],
                       history=[e.public_view() for e in history], names=names, **extra)

    # ---- C-07: review the designer of a completed enquiry (RatingForm, S-11) ----
    @bp.post("/api/requests/<request_id>/review")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def review_designer(request_id):
        data = body()
        review = shared.reviews.submit(login.current_user(), request_id, data.get("score"), data.get("comment"))
        return jsonify(review={"id": review.id, "rating": review.rating, "comment": review.comment,
                               "company": review.company, "date": review.date}), 201

    # ---- HD-13: the requester rates the help on a closed ticket (RatingForm, S-11) ----
    @bp.post("/api/support/tickets/<ticket_id>/feedback")
    @require_role(login, *REQUESTERS)
    def ticket_feedback(ticket_id):
        data = body()
        shared.ticket_feedback.give(login.current_user(), ticket_id, data.get("score"), data.get("comment"))
        return jsonify(thanks=True), 201

    # ---- Claim a ticket: the agent becomes its handler ----
    @bp.post("/api/support/tickets/<ticket_id>/assign")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def claim_ticket(ticket_id):
        find_ticket(ticket_id)
        return ticket_page(shared.requests.assign_handler(ticket_id, login.current_user().id))

    # ---- HD-01: set a ticket's priority and assignee (any helpdesk agent) ----
    @bp.get("/api/support/agents")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def helpdesk_agents():
        return jsonify(agents=shared.ticket_triage.agents())

    @bp.post("/api/support/tickets/<ticket_id>/triage")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def triage_ticket(ticket_id):
        data = body()
        return ticket_page(shared.ticket_triage.update(ticket_id, login.current_user(), data.get("priority"),
                                                       data.get("assignee_id")))

    # ---- Move a ticket (ConfirmWithReasonDialog -> TicketLifecycle -> StatusChangeService) ----
    @bp.post("/api/support/tickets/<ticket_id>/status")
    @require_role(login, UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN)
    def move_ticket(ticket_id):
        data = body()
        status, user, reason = data.get("status"), login.current_user(), data.get("reason")
        hd = helpdesk()
        if status == SupportTicket.STATUS_AWAITING_INFO:      # HD-04
            ticket = hd.request_more_info_controller.request_more_info(ticket_id, user, reason)
        elif status == SupportTicket.STATUS_ESCALATED:        # HD-11
            ticket = hd.escalate_ticket_controller.escalate(ticket_id, user, reason)
        elif status == SupportTicket.STATUS_CLOSED:           # HD-13
            ticket = hd.close_ticket_controller.close(ticket_id, user)
        else:                                                 # resolve, reopen (shared, UA-12)
            ticket = shared.ticket_lifecycle.move_to(ticket_id, status, user, reason)
        return ticket_page(ticket)

    # ---- Project status: publish / unpublish (ID-03), hide / restore (HD-09) ----
    @bp.post("/api/projects/<project_id>/status")
    @require_role(login, UserAccount.ROLE_DESIGNER, UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN)
    def change_project_status(project_id):
        data = body()
        user, status = login.current_user(), data.get("status")
        if user.role == UserAccount.ROLE_HELPDESK and status == ProjectStatus.HIDDEN:       # HD-09
            project = helpdesk().hide_project_controller.hide(user, project_id, data.get("reason"))
        elif user.role == UserAccount.ROLE_HELPDESK and status == ProjectStatus.PUBLISHED:  # HD-09: show again
            project = helpdesk().hide_project_controller.unhide(user, project_id, data.get("reason"))
        else:                                                 # publish / unpublish (ID-03.4), UA-12
            project = shared.project_status.change(user, project_id, status, data.get("reason"))
        return jsonify(project=project,
                       history=[e.public_view() for e in shared.project_status.history_of(project_id)])

    # ---- Record history (HistoryTimeline, S-04) ----
    @bp.get("/api/history/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def record_history(target_type, target_id):
        return jsonify(history=[e.public_view() for e in shared.status_change.history_of(target_type, target_id)])

    # ---- Report IDP (ReportAction) ----
    @bp.post("/api/reports/projects/<project_id>")
    @require_role(login, *REQUESTERS)
    def report_project(project_id):
        data = body()
        ticket = shared.submit_ticket.submit_ticket(login.current_user(), SupportTicket.TYPE_REPORT_IDP,
                                                    data.get("reason"), related_project_id=project_id,
                                                    related_project_title=data.get("title"))
        return jsonify(ticket=ticket.public_view()), 201

    # ---- Report a message (ReportAction, S-15 / S-16) ----
    @bp.post("/api/reports/messages/<message_id>")
    @require_role(login, *REQUESTERS)
    def report_message(message_id):
        ticket = shared.submit_ticket.report_message(login.current_user(), message_id, body().get("reason"))
        return jsonify(ticket=ticket.public_view()), 201

    # ---- View Notifications (NotificationBell) ----
    @bp.get("/api/notifications")
    @require_role(login)
    def list_notifications():
        user_id = login.current_user().id
        limit = request.args.get("limit")
        if limit is not None and (not limit.isdigit() or not 1 <= int(limit) <= 100):
            raise ValueError("limit must be a number from 1 to 100.")
        items = shared.notifications.list_for(user_id, unread_only=request.args.get("unread") == "1",
                                              limit=int(limit) if limit else None)
        return jsonify(items=[n.public_view() for n in items], unread=shared.notifications.unread_count(user_id))

    @bp.post("/api/notifications/<notification_id>/read")
    @require_role(login)
    def mark_read(notification_id):
        notification = shared.notifications.mark_read(notification_id, login.current_user().id)
        return jsonify(notification=notification.public_view())

    @bp.post("/api/notifications/read-all")
    @require_role(login)
    def mark_all_read():
        user_id = login.current_user().id
        shared.notifications.mark_all_read(user_id)
        return jsonify(unread=shared.notifications.unread_count(user_id))

    # ---- Message threads (MessageThread, S-01) ----
    @bp.get("/api/threads/<thread_id>/messages")
    @require_role(login)
    def list_messages(thread_id):
        messages = shared.messages.list_messages(thread_id, login.current_user())
        return jsonify(messages=[m.public_view() for m in messages])

    @bp.post("/api/threads/<thread_id>/messages")
    @require_role(login)
    def post_message(thread_id):
        message = shared.messages.post_message(thread_id, login.current_user(), body().get("body"))
        return jsonify(message=message.public_view()), 201

    # ---- Public company list (who customers can message; no owner details) ----
    @bp.get("/api/companies")
    def companies():
        return jsonify(companies=customer().browse_company_profiles_controller.list_companies())   # C-05

    @bp.get("/api/companies/<company_id>")
    def company_profile(company_id):
        try:
            return jsonify(customer().browse_company_profiles_controller.profile(company_id))       # C-05
        except LookupError as err:
            return jsonify(error=str(err)), 404

    # ---- Public reviews of a company (C-07, RatingDisplay S-11) ----
    @bp.get("/api/companies/<company_id>/reviews")
    def company_reviews(company_id):
        return jsonify(shared.reviews.for_company(company_id))

    # ---- A shared moodboard, read-only, for anyone with the link (C-13) ----
    @bp.get("/api/moodboards/shared/<token>")
    def shared_moodboard(token):
        return jsonify(shared.collections.shared_view(token))

    # ---- Private conversations with a designer (MessageDesignerButton, S-16) ----
    @bp.post("/api/conversations")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def start_conversation():
        conversation = shared.conversations.start_conversation(login.current_user(), body().get("company_id"))
        return jsonify(conversation=conversation.public_view()), 201

    @bp.get("/api/conversations")
    @require_role(login, UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)
    def list_conversations():
        return jsonify(conversations=[c.public_view() for c in
                                      shared.conversations.list_conversations(login.current_user())])

    # ---- Inbox (InboxPage, S-14) ----
    @bp.get("/api/inbox")
    @require_role(login)
    def inbox():
        return jsonify(shared.inbox.inbox_for(login.current_user()))

    # ---- Notification preferences (C-12) ----
    @bp.get("/api/notification-preferences")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def notification_preferences():
        return jsonify(preferences=customer().update_notification_preference_controller.list_for(login.current_user()))

    @bp.put("/api/notification-preferences")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def update_notification_preference():
        data = body()
        return jsonify(preferences=customer().update_notification_preference_controller.update(
            login.current_user(), data.get("event_type"), data.get("is_enabled")))

    # ---- The client's answer to offers (OfferPage, S-21) ----
    @bp.get("/api/offers")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def my_offers():
        return jsonify(shared.offers.offers_for(login.current_user()))

    @bp.post("/api/offers/quotations/<offer_id>/accept")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def accept_quotation(offer_id):
        quotation = shared.offers.accept(offer_id, login.current_user())
        return jsonify(quotation=shared.offers.quotation_view(quotation))

    @bp.post("/api/offers/quotations/<offer_id>/adjustment")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def request_quotation_adjustment(offer_id):
        quotation = shared.offers.request_adjustment(offer_id, login.current_user(), body().get("note"))
        return jsonify(quotation=shared.offers.quotation_view(quotation))

    @bp.post("/api/offers/proposals/<offer_id>/accept")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def accept_proposal(offer_id):
        return jsonify(proposal=shared.offers.accept_proposal(offer_id, login.current_user()).public_view())

    @bp.post("/api/offers/proposals/<offer_id>/feedback")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def proposal_feedback(offer_id):
        proposal = shared.offers.give_feedback(offer_id, login.current_user(), body().get("feedback"))
        return jsonify(proposal=proposal.public_view())

    # ---- Failed-upload log (S-03, HD-08): ?q=&page=&page_size= ----
    @bp.get("/api/uploads/failures")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def upload_failures():
        return jsonify(helpdesk().view_upload_error_controller.list_failures(request.args))   # HD-08

    # ---- Internal notes (NotesPanel, S-02): target_type REQUEST or USER_ACCOUNT ----
    @bp.get("/api/notes/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def list_notes(target_type, target_id):
        notes = shared.notes.list_notes(target_type, target_id, login.current_user())
        return jsonify(notes=[n.public_view() for n in notes])

    @bp.post("/api/notes/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def add_note(target_type, target_id):
        note = shared.notes.add_note(target_type, target_id, login.current_user(), body().get("text"))
        return jsonify(note=note.public_view()), 201

    return bp
