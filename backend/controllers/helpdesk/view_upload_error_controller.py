"""<<control>> ViewUploadErrorController — HD-08 the error details of IDP uploads that failed.

Reads the shared failed-upload log (S-03): file name, reason, designer and project; searched and paged with the
shared PagedQuery (S-11).
"""
from backend.entities.paged_query import PagedQuery


class ViewUploadErrorController:
    def __init__(self, upload_failures):
        self.failures = upload_failures

    def list_failures(self, args):
        """args: q, user_id, page, page_size."""
        rows = [f.public_view() for f in self.failures.all()]
        query = PagedQuery.create(args.get("q", ""), {"user_id": args.get("user_id")}, page=args.get("page", 1),
                                  page_size=args.get("page_size", 20))
        return query.run(rows, search_fields=("file_name", "reason", "user_id", "project_id"))
