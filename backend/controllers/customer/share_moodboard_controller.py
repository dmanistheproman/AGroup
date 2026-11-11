"""<<control>> ShareMoodboardController — C-13 share a moodboard by a read-only link, and stop sharing it.
The link and its token are kept by the shared CollectionService (S-22)."""


class ShareMoodboardController:
    def __init__(self, collections):
        self.collections = collections

    def share(self, customer, collection_id):
        return self.collections.share(customer, collection_id)

    def revoke(self, customer, collection_id):
        return self.collections.revoke(customer, collection_id)
