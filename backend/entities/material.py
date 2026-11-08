"""<<entity>> Material — a material used in a project (S-17)."""


class Material:
    def __init__(self, material_id, project_id, name, description=""):
        self.id = material_id
        self.project_id = project_id
        self.name = name
        self.description = description

    @classmethod
    def parse(cls, project_id, materials):
        """Project records keep materials as "Oak veneer, limewash walls" or as a list of names."""
        if isinstance(materials, str):
            materials = materials.split(",")
        names = [str(m).strip() for m in (materials or []) if str(m).strip()]
        return [cls(f"{project_id}-M{index}", project_id, name) for index, name in enumerate(names, start=1)]

    def public_view(self):
        return {"id": self.id, "name": self.name, "description": self.description}
