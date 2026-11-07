"""<<entity>> 仓库 — ProposalRepo（shared: offers；接 Firestore 前的内存替身）。
注意：ID-05 与 ID-06 的控制器必须共享同一个 ProposalRepo 实例。"""
from app.entities.design_proposal import DesignProposal
import re

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

class ProposalRepo:
    def __init__(self, proposals=None):
        self.items = {p.id: p for p in (proposals or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([DesignProposal(**row) for row in rows])

    def get(self, proposal_id):
        return self.items.get(proposal_id)

    def save(self, proposal):
        self.items[proposal.id] = proposal
        return proposal

    def all(self):
        return list(self.items.values())

    def next_reference(self):
        """续接种子序号：取现有 PROP-<数字> 引用的最大值 +1（空仓回退 PROP-801）。"""
        nums = [int(m.group(1)) for key in self.items
                for m in [re.match(r"PROP-(\d+)$", key)] if m]
        return "PROP-{}".format((max(nums) if nums else 800) + 1)

