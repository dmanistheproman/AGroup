"""<<control>> CreateMoodboardController — C-11.1 the customer creates a moodboard (shared CollectionService, S-22)."""


class CreateMoodboardController:
    KIND = "MOODBOARD"

    def __init__(self, collections):
        self.collections = collections

    def create_moodboard(self, customer, name):
        return self.collections.create(customer, name, self.KIND)
