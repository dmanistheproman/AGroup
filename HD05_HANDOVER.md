# HD05 Merge Tickets: Firestore handover

Built and tested with an in-memory store (`backend/repositories/ticket_memory_repo.py`). Only the store changes for Firestore; `backend/server.py`, `backend/boundary/helpdesk_routes.py`, the controller and the entity stay as they are.

## Steps
1. `pip install google-cloud-firestore` and set credentials (`GOOGLE_APPLICATION_CREDENTIALS`).
   For safe local runs, use the emulator: set `FIRESTORE_EMULATOR_HOST=localhost:8080`.
2. Add `firestore_store.py` with a class implementing the three methods `TicketMemoryRepo` has. Keys are tuples:
   `("tickets", id)` or `("messages"|"notes", ticket_id, doc_id)`.
   - `get_ticket(id)`: read `tickets/{id}`, return the dict or `None`.
   - `children(id, kind)`: read `tickets/{id}/{kind}` ordered by `timestamp`, return `[(key, dict)]`.
   - `commit(writes)`: writes are `("set", key, doc)` or `("delete", key)`. Apply them all in one batch (`db.batch()`).
3. Layout: `tickets/{id}` has `requester, idp, subject, status, readOnly, mergedIntoTicketId`.
   Subcollections `messages` and `notes` hold `body, timestamp`.
4. Port `seed()` in `ticket_memory_repo.py`: write the same documents to Firestore, wiping first so it can be rerun.
5. In `backend/server.py`, replace `TicketMemoryRepo()` with the Firestore store. In `backend/tests/helpdesk/test_merge_tickets.py`, replace the `store` fixture so it reseeds Firestore before each test.
6. Run `pytest`. Expect 7 passed, and `backend/tests/helpdesk/test_results.md` showing 7 PASS rows.

## Watch out
- A batch holds at most 500 writes. Each moved message or note costs 2 writes (set and delete), so a merge handles about 250 items. Larger merges would fail and report "Merge failed".
- `GET /tickets` counts messages and notes with one query per ticket. This is fine for a demo, but a stored counter would be needed at scale.
