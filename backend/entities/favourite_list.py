class FavouriteList:
    def __init__(self, customer_id: str, project_ids: list[str] = None):
        self.customer_id = customer_id
        self.project_ids = project_ids if project_ids is not None else []

    def add_project(self, project_id: str) -> bool:
        if project_id not in self.project_ids:
            self.project_ids.append(project_id)
            return True
        return False

    def remove_project(self, project_id: str) -> bool:
        if project_id in self.project_ids:
            self.project_ids.remove(project_id)
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "project_ids": self.project_ids
        }