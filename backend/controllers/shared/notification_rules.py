"""<<control>> NotificationRules — decides who is notified when something changes (S-07).

    on_status_changed    support tickets (opened, moved, reopened), projects (hidden, restored),
                         enquiries (decided), verification requests (opened, decided) and offers (sent, answered)
    on_handler_assigned  a designer is told about a new enquiry they handle
    on_message_posted    a new message in a ticket's, an enquiry's or a private conversation's thread goes to the
                         other side
    on_payment_reminder  the customer is reminded about a payment milestone (ID-09)
    notify               any other update a controller wants to send (for example a designer's answer)
A customer's notification preferences (C-12) are checked before anything is sent to them, and nothing is sent
to an ID that is not an account (some seeded records name a customer without one).
"""
from backend.entities.enums import ProjectStatus
from backend.entities.user_account import UserAccount

PREVIEW = 120
CUSTOMER_REQUESTS = "inbox.html#requests"
CUSTOMER_OFFERS = "inbox.html#offers"


class NotificationRules:
    TARGET_SUPPORT_TICKET = "SUPPORT_TICKET"
    TARGET_PROJECT = "PROJECT"
    TARGET_THREAD = "THREAD"
    TARGET_ENQUIRY = "ENQUIRY"
    TARGET_VERIFICATION = "VERIFICATION_REQUEST"
    TARGET_QUOTATION = "QUOTATION"
    TARGET_PROPOSAL = "DESIGN_PROPOSAL"

    def __init__(self, notification_service, account_repo, ticket_repo, project_repo=None):
        self.notifications = notification_service
        self.accounts = account_repo
        self.tickets = ticket_repo
        self.projects = project_repo
        self.conversations = None    # ConversationRepo (S-16), set in server.py
        self.preferences = None      # NotificationPreferenceRepo (C-12), set in server.py
        # ID records, set in server.py once the designer repositories exist
        self.enquiries = self.verifications = self.quotations = self.proposals = self.companies = None

    # ---- status changes (S-04) ----

    def on_status_changed(self, target_type, target_id, new_status, from_status=None, reason=None):
        """from_status is None when the record has just been opened (RequestService.open)."""
        handler = {self.TARGET_PROJECT: self._project_changed, self.TARGET_ENQUIRY: self._enquiry_changed,
                   self.TARGET_VERIFICATION: self._verification_changed,
                   self.TARGET_QUOTATION: self._offer_changed, self.TARGET_PROPOSAL: self._offer_changed,
                   self.TARGET_SUPPORT_TICKET: self._ticket_changed}.get(target_type)
        if handler is not None:
            handler(target_id, new_status, from_status, reason, target_type)

    def on_handler_assigned(self, target_type, request):
        if target_type == self.TARGET_ENQUIRY and request.handler_id:
            self._send(request.handler_id, "NEW_ENQUIRY",
                       f"New enquiry from {request.client_name}: {self._preview(request.requirements)}",
                       "portal.html#designer/enquiries", target_type, request.id)

    def _ticket_changed(self, target_id, new_status, from_status, reason, target_type):
        ticket = self.tickets.get(target_id)
        if ticket is None:
            return
        if new_status == ticket.STATUS_OPEN and from_status is None:
            self._ticket_opened(ticket)
            return
        if new_status == ticket.STATUS_OPEN:
            text = f"Your request {ticket.id} has been reopened."
        else:
            text = f"Your request {ticket.id} is now {self._words(new_status)}."
        self._send(ticket.requester_id, "TICKET_STATUS", self._with(text, reason),
                   self._requester_link(ticket), *self._target(ticket))

    def _project_changed(self, project_id, new_status, from_status, reason, target_type):
        project = self.projects.get(project_id) if self.projects is not None else None
        if project is None or not project.get("owner_id"):
            return
        if new_status == ProjectStatus.HIDDEN:
            kind, text = "PROJECT_HIDDEN", f'Your project "{project["title"]}" was hidden by the helpdesk.'
        elif from_status == ProjectStatus.HIDDEN:
            kind, text = "PROJECT_RESTORED", f'Your project "{project["title"]}" is visible to customers again.'
        else:
            return
        self._send(project["owner_id"], kind, self._with(text, reason), "portal.html#designer/projects",
                   self.TARGET_PROJECT, project_id)

    def _enquiry_changed(self, enquiry_id, new_status, from_status, reason, target_type):
        enquiry = self._get(self.enquiries, enquiry_id)
        if enquiry is None or from_status is None:
            return
        who = self._designer_name(enquiry.handler_id)
        text = {"CONFIRMED": f"{who} accepted your enquiry and will prepare a quotation.",
                "DECLINED": f"{who} declined your enquiry.",
                "COMPLETED": f"Your project with {who} is marked as completed."}.get(
            new_status, f"Your enquiry is now {self._words(new_status)}.")
        self._send(enquiry.customer_id, "ENQUIRY_UPDATE", self._with(text, reason),
                   f"{CUSTOMER_REQUESTS}/{enquiry.id}", target_type, enquiry.id)

    def _verification_changed(self, request_id, new_status, from_status, reason, target_type):
        request = self._get(self.verifications, request_id)
        if request is None:
            return
        if from_status is None or new_status == request.STATUS_PENDING:
            company = self._get(self.companies, request.company_id)
            text = f"Verification request {request.id} from {company.name if company else request.company_id}."
            for admin in self._accounts_with(UserAccount.ROLE_USER_ADMIN):
                self._send(admin, "NEW_VERIFICATION", text, "portal.html#admin/verification", target_type, request.id)
            return
        verdict = "approved" if new_status == request.STATUS_APPROVED else "not approved"
        self._send(request.requested_by, "VERIFICATION_STATUS",
                   self._with(f"Your verification request {request.id} was {verdict}.", reason),
                   "portal.html#designer/company", target_type, request.id)

    def _offer_changed(self, offer_id, new_status, from_status, reason, target_type):
        repo = self.quotations if target_type == self.TARGET_QUOTATION else self.proposals
        offer = self._get(repo, offer_id)
        if offer is None:
            return
        name = "quotation" if target_type == self.TARGET_QUOTATION else "design proposal"
        customer, designer = self.offer_parties(offer)
        if new_status in ("WAITING_CLIENT_CONFIRMATION", "UNDER_REVIEW"):
            again = " (revised)" if from_status not in (None, "DRAFT") else ""
            self._send(customer, "OFFER_SENT", f"{self._designer_name(designer)} sent you a {name}{again}: {offer.id}.",
                       CUSTOMER_OFFERS, target_type, offer.id)
        elif new_status in ("ACCEPTED", "ADJUSTMENT_REQUESTED", "CONFIRMED"):
            verb = "asked for changes to" if new_status == "ADJUSTMENT_REQUESTED" else "accepted"
            self._send(designer, "OFFER_ANSWERED", self._with(f"{offer.client_name} {verb} {name} {offer.id}.", reason),
                       "portal.html#designer/quotations" if target_type == self.TARGET_QUOTATION
                       else "portal.html#designer/proposals", target_type, offer.id)

    # ---- messages (S-01, S-16) ----

    def on_message_posted(self, thread_id, author_id, body=""):
        preview = self._preview(body)
        conversation = self.conversations.find_by_thread(thread_id) if self.conversations is not None else None
        if conversation is not None:
            recipient = conversation.other_participant(author_id)
            if recipient == conversation.customer_id:
                text, link = f"New message from {conversation.company_name}: {preview}", "inbox.html#messages"
            else:
                text, link = f"New message from {conversation.customer_name}: {preview}", "portal.html#designer/messages"
            if recipient:
                self._send(recipient, "NEW_MESSAGE", text, link, self.TARGET_THREAD, thread_id)
            return
        enquiry = self.enquiries.find_by_thread(thread_id) if self.enquiries is not None else None
        if enquiry is not None:
            if author_id == enquiry.handler_id:
                recipient, link = enquiry.customer_id, f"{CUSTOMER_REQUESTS}/{enquiry.id}"
                text = f"New message from {self._designer_name(author_id)} about your enquiry: {preview}"
            else:
                recipient, link = enquiry.handler_id, "portal.html#designer/messages"
                text = f"New message from {enquiry.client_name} about enquiry {enquiry.id}: {preview}"
            if recipient and recipient != author_id:
                self._send(recipient, "NEW_MESSAGE", text, link, self.TARGET_THREAD, thread_id)
            return
        ticket = self.tickets.find_by_thread(thread_id) if hasattr(self.tickets, "find_by_thread") else None
        if ticket is None:
            return
        if author_id == ticket.requester_id:
            recipients = [ticket.handler_id] if ticket.handler_id else self._accounts_with(UserAccount.ROLE_HELPDESK)
            link = "portal.html#helpdesk/tickets"
        else:
            recipients, link = [ticket.requester_id], self._requester_link(ticket)
        for recipient in recipients:
            if recipient and recipient != author_id:
                self._send(recipient, "NEW_MESSAGE", f"New message on {ticket.id}: {preview}", link,
                           self.TARGET_THREAD, thread_id)

    # ---- payments (ID-09) ----

    def on_payment_reminder(self, milestone):
        quotation = self._get(self.quotations, milestone.quotation_id)
        if quotation is None:
            return None
        customer, designer = self.offer_parties(quotation)
        return self._send(customer, "PAYMENT_REMINDER",
                          f"Reminder from {self._designer_name(designer)}: \"{milestone.name}\" "
                          f"(S${milestone.amount:,.0f}) was due on {milestone.due_date}.",
                          CUSTOMER_OFFERS, self.TARGET_QUOTATION, quotation.id)

    # ---- shared helpers ----

    def notify(self, recipient_id, kind, text, link="", target_type=None, target_id=None):
        """Send one notification through the same checks as the rules (preferences, real recipient)."""
        return self._send(recipient_id, kind, text, link, target_type, target_id)

    def offer_parties(self, offer):
        """(customer ID, designer ID) of a quotation or proposal, through the enquiry it answers."""
        enquiry = self._get(self.enquiries, getattr(offer, "enquiry_id", None) or getattr(offer, "request_id", None))
        if enquiry is not None:
            return enquiry.customer_id, enquiry.handler_id
        customer = next((a.id for a in self.accounts.all()
                         if a.role == UserAccount.ROLE_CUSTOMER and a.name == offer.client_name), None)
        return customer, None

    def _ticket_opened(self, ticket):
        self._send(ticket.requester_id, "TICKET_OPENED",
                   f"We received your request {ticket.id}. The helpdesk will reply soon.",
                   self._requester_link(ticket), *self._target(ticket))
        if ticket.is_report():
            what = ticket.related_project_title or ticket.related_project_id or "a message"
            kind, text, link = "NEW_REPORT", f"Reported: {what} ({ticket.id}).", "portal.html#helpdesk/complaints"
        else:
            requester = self.accounts.get(ticket.requester_id)
            who = requester.name if requester else ticket.requester_id
            kind, text, link = "NEW_TICKET", f"New support ticket {ticket.id} from {who}: {ticket.label()}.", "portal.html#helpdesk/tickets"
        for agent_id in self._accounts_with(UserAccount.ROLE_HELPDESK):
            self._send(agent_id, kind, text, link, *self._target(ticket))

    def _send(self, recipient_id, kind, text, link="", target_type=None, target_id=None):
        if not recipient_id or self.accounts.get(recipient_id) is None:
            return None
        if self.preferences is not None and not self.preferences.allows(recipient_id, kind):
            return None
        return self.notifications.send(recipient_id, kind, text, link, target_type, target_id)

    def _accounts_with(self, role):
        return [a.id for a in self.accounts.all() if a.role == role and a.is_active()]

    def _designer_name(self, designer_id):
        company = self.companies.get_by_owner(designer_id) if self.companies is not None and designer_id else None
        if company is not None:
            return company.name
        account = self.accounts.get(designer_id) if designer_id else None
        return account.name if account else "Your designer"

    @staticmethod
    def _get(repo, record_id):
        return repo.get(record_id) if repo is not None and record_id else None

    @staticmethod
    def _preview(body):
        body = body or ""
        return body if len(body) <= PREVIEW else body[:PREVIEW - 1] + "…"

    @staticmethod
    def _words(status):
        return str(status).replace("_", " ").lower()

    @staticmethod
    def _with(text, reason):
        return f"{text} {reason}" if reason else text

    @classmethod
    def _target(cls, ticket):
        return cls.TARGET_SUPPORT_TICKET, ticket.id

    @staticmethod
    def _requester_link(ticket):
        return "portal.html#designer/overview" if ticket.requester_type == UserAccount.ROLE_DESIGNER else "inbox.html#requests"
