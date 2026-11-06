"""<<control>> FindPotentialClientsController — 命名与任务列表一致。"""

class FindPotentialClientsController:
    def __init__(self, customer_repo):
        self.customers = customer_repo

    def find(self, user_id, styles=None):
        # user_id 预留给角色校验（此阶段模拟登录，见 PROJECT_CONTEXT 约定）
        return [c.public_view() for c in self.customers.find_by_styles(styles)]
