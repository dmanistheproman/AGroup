"""Boundary: HTTP routes for the Customer role — C-04 favourites and S-22 folders.
The customer comes from the login session."""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import role_error
from backend.entities.user_account import UserAccount


def create_customer_blueprint(favourites_ctrl, login, collections=None, recommendations_controller=None):
    bp = Blueprint("customer", __name__)

    @bp.before_request
    def check_role():
        return role_error(login, UserAccount.ROLE_CUSTOMER)

    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(LookupError)
    def not_found(err):
        return jsonify(error=str(err).strip("'\"")), 404

    @bp.errorhandler(PermissionError)
    def forbidden(err):
        return jsonify(error=str(err)), 403

    def customer_id():
        return login.current_user().id

    @bp.get("/api/favourites")
    def get_favourites():
        return jsonify(favourites_ctrl.get_favourites(customer_id()))

    @bp.post("/api/favourites")
    def add_favourite():
        data = request.get_json(silent=True) or {}
        return jsonify(favourites_ctrl.add_favourite(customer_id(), data.get("project_id")))

    @bp.delete("/api/favourites/<project_id>")
    def remove_favourite(project_id):
        return jsonify(favourites_ctrl.remove_favourite(customer_id(), project_id))

    # ---- S-22 collections: folders that organise favourites ----
    def collection_view(collection):
        view = collection.public_view()
        view["items"] = [collections.item_view(i) for i in collections.items(login.current_user(), collection.id)]
        view["shared"] = bool(collection.share_token)
        view["share_token"] = collection.share_token
        return view

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON request body.")
        return data

    @bp.get("/api/collections")
    def list_collections():
        user = login.current_user()
        return jsonify(collections=[collection_view(c) for c in collections.list_for(user)])

    @bp.post("/api/collections")
    def create_collection():
        data = body()
        collection = collections.create(login.current_user(), data.get("name"), data.get("kind", "FOLDER"))
        return jsonify(collection=collection_view(collection)), 201

    @bp.patch("/api/collections/<collection_id>")
    def rename_collection(collection_id):
        collection = collections.rename(login.current_user(), collection_id, body().get("name"))
        return jsonify(collection=collection_view(collection))

    @bp.delete("/api/collections/<collection_id>")
    def delete_collection(collection_id):
        collections.delete(login.current_user(), collection_id)
        return jsonify(deleted=collection_id)

    @bp.post("/api/collections/<collection_id>/items")
    def add_collection_item(collection_id):
        data = body()
        item = collections.add_item(login.current_user(), collection_id, data.get("item_type", "PROJECT"),
                                    project_id=data.get("project_id"), colour=data.get("colour"), note=data.get("note"))
        return jsonify(item=collections.item_view(item)), 201

    @bp.post("/api/collections/<collection_id>/images")
    def add_collection_image(collection_id):
        upload = request.files.get("image")
        if upload is None:
            raise ValueError("Choose an image to add.")
        item = collections.add_image(login.current_user(), collection_id,
                                     {"filename": upload.filename, "content": upload.read()})
        return jsonify(item=collections.item_view(item)), 201

    @bp.post("/api/collections/<collection_id>/share")
    def share_collection(collection_id):
        token = collections.share(login.current_user(), collection_id)
        return jsonify(share_token=token, url=f"/moodboard.html#{token}")

    @bp.delete("/api/collections/<collection_id>/share")
    def revoke_collection_share(collection_id):
        collections.revoke(login.current_user(), collection_id)
        return jsonify(shared=False)

    @bp.delete("/api/collections/<collection_id>/items/<item_id>")
    def remove_collection_item(collection_id, item_id):
        collections.remove_item(login.current_user(), collection_id, item_id)
        return jsonify(deleted=item_id)

    @bp.put("/api/collections/<collection_id>/order")
    def reorder_collection(collection_id):
        collections.reorder(login.current_user(), collection_id, body().get("item_ids"))
        return jsonify(collection=collection_view(collections.collections.get(collection_id)))

    # ---- C-09: data-driven personalised recommendations ----
    @bp.get("/api/recommendations")
    def recommendations():
        if recommendations_controller is None:
            return jsonify(error="Recommendations are not available."), 404
        limit = request.args.get("limit", 5, type=int)
        return jsonify(recommendations=recommendations_controller.recommend(customer_id(), limit))

    @bp.get("/api/recommendations/evaluate")
    def evaluate_recommendations():
        if recommendations_controller is None:
            return jsonify(error="Recommendations are not available."), 404
        limit = request.args.get("limit", 5, type=int)
        return jsonify(recommendations_controller.evaluate(customer_id(), limit))

    return bp
