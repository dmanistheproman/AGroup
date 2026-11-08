"""<<entity>> Conversation — a private conversation between a customer and an interior design company (S-16).

One conversation per customer–company pair; its messages are in an S-01 thread. Only the customer and the
company's designer take part.
"""


class Conversation:
    def __init__(self, conversation_id, customer_id, company_id, thread_id, last_message_at=None,
                 designer_id=None, company_name=None, customer_name=None):
        self.id = conversation_id
        self.customer_id = customer_id
        self.company_id = company_id
        self.thread_id = thread_id
        self.last_message_at = last_message_at
        self.designer_id = designer_id          # the company owner's account
        self.company_name = company_name
        self.customer_name = customer_name

    def can_access(self, user_id):
        return user_id is not None and user_id in (self.customer_id, self.designer_id)

    def other_participant(self, user_id):
        return self.designer_id if user_id == self.customer_id else self.customer_id

    def public_view(self):
        return {"id": self.id, "customer_id": self.customer_id, "customer_name": self.customer_name,
                "company_id": self.company_id, "company_name": self.company_name, "thread_id": self.thread_id,
                "last_message_at": self.last_message_at}
