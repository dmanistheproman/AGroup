from flask import Blueprint, jsonify, request, current_app

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/api/customer/<customer_id>/favourites', methods=['GET'])
def get_favourites(customer_id):
    ctrl = current_app.favourites_ctrl
    return jsonify(ctrl.get_favourites(customer_id))

@customer_bp.route('/api/customer/<customer_id>/favourites', methods=['POST'])
def add_favourite(customer_id):
    data = request.get_json() or {}
    project_id = data.get('project_id')
    ctrl = current_app.favourites_ctrl
    return jsonify(ctrl.add_favourite(customer_id, project_id))

@customer_bp.route('/api/customer/<customer_id>/favourites/<project_id>', methods=['DELETE'])
def remove_favourite(customer_id, project_id):
    ctrl = current_app.favourites_ctrl
    return jsonify(ctrl.remove_favourite(customer_id, project_id))
