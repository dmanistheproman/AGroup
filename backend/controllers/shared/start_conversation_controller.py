"""<<control>> StartConversationController — find or start a customer's conversation with a company (S-16).
Sequence diagram: Seq_15_Message_Designer. Messages are then posted through PostMessageController (S-01)."""
from backend.entities.user_account import UserAccount


class StartConversationController:
    def __init__(self, conversation_repo, company_repo, thread_repo):
        self.conversations = conversation_repo
        self.companies = company_repo
        self.threads = thread_repo

    def start_conversation(self, customer, company_id):
        if customer is None or customer.role != UserAccount.ROLE_CUSTOMER:
            raise PermissionError("Only customers can start a conversation with a designer.")
        if self.companies.get(company_id) is None:
            raise LookupError(f"Company {company_id} was not found.")
        existing = self.conversations.find(customer.id, company_id)
        if existing is not None:
            return existing
        return self.conversations.create(customer.id, company_id, self.threads.create().id)

    def list_conversations(self, user):
        return self.conversations.find_by_user(user.id)
