"""<<control>> FindPotentialClientsController — named as in the task list."""

class FindPotentialClientsController:
    def __init__(self, customer_repo):
        self.customers = customer_repo

    def find(self, user_id, styles=None):
        # user_id is kept for the role check (simulated login at this stage, see the PROJECT_CONTEXT convention)
        return [c.public_view() for c in self.customers.find_by_styles(styles)]
