import random

IDPS = ("google", "microsoft")


def scale_seed(tickets=10_000, msgs_per=20, notes_per=5, rng_seed=314):
    """Deterministic bulk data in the same key shape as seed(). Doc ids are globally unique.

    Tickets 2k and 2k+1 share requester and IDP, so mergeable pairs exist at every scale.
    BIG1 and BIG2 are open, same requester/IDP, and carry 250 and 400 items: merging them
    needs 801 writes, over Firestore's 500-write batch limit.
    """
    rng = random.Random(rng_seed)
    docs, n = {}, 0

    def add(kind, tid, label, body):
        nonlocal n
        n += 1
        ts = f"2026-01-01T{(n // 3600) % 24:02}:{(n // 60) % 60:02}:{n % 60:02}.{n:07}"
        docs[(kind, tid, f"{tid}-{label}")] = {"body": body, "timestamp": ts}

    def add_ticket(tid, requester, idp, status, n_msgs, n_notes):
        docs[("tickets", tid)] = {
            "requester": requester, "idp": idp, "subject": f"Login issue ({requester})",
            "status": status, "readOnly": status == "merged"}
        for j in range(n_msgs):
            add("messages", tid, f"m{j}", f"message {j}")
        for j in range(n_notes):
            add("notes", tid, f"n{j}", f"note {j}")

    for i in range(tickets):
        pair = i // 2
        status = rng.choices(("open", "closed", "merged"), weights=(80, 10, 10))[0]
        add_ticket(f"T{i:05}", f"user{pair % 500}", IDPS[pair % 2], status,
                   rng.randint(1, msgs_per), rng.randint(0, notes_per))
        if status == "merged":  # point at the pair partner, as a real merge would
            docs[("tickets", f"T{i:05}")]["mergedIntoTicketId"] = f"T{i ^ 1:05}"

    add_ticket("BIG1", "bigco", "google", "open", 150, 100)
    add_ticket("BIG2", "bigco", "google", "open", 250, 150)
    return docs
