import os
from flask import Flask, request, jsonify, send_from_directory
from app.controllers.merge_ticket_controller import MergeFailed, MergeNotAllowed, MergeTicketController
from app.repositories.ticket_memory_repo import TicketMemoryRepo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "Portal"), static_url_path="")

ticket_repo = TicketMemoryRepo()  # swap for the Firestore repo, see HD05_HANDOVER.md
merge_controller = MergeTicketController(ticket_repo)


@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/tickets")
def api_list_tickets():
    return jsonify([
        {"id": k[1], "requester": d["requester"], "subject": d["subject"], "status": d["status"],
         "messages": len(ticket_repo.children(k[1], "messages")), "notes": len(ticket_repo.children(k[1], "notes"))}
        for k, d in ticket_repo.docs.items() if k[0] == "tickets"
    ])


@app.route("/api/tickets/merge", methods=["POST"])
def api_merge_tickets():
    body = request.get_json(silent=True) or {}
    main_id, other_id = body.get("mainTicketId"), body.get("otherTicketId")
    if not main_id or not other_id:
        return jsonify(error="mainTicketId and otherTicketId are required"), 400
    try:
        merge_controller.merge_tickets(main_id, other_id)
    except MergeNotAllowed as err:
        return jsonify(error=str(err)), 400
    except MergeFailed as err:
        return jsonify(error=str(err)), 500
    return jsonify(message="Merge complete")


if __name__ == "__main__":
    app.run(debug=True, port=8000)
