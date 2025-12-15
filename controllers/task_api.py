from urllib.parse import parse_qs

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)
# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

class TaskApi(http.Controller):
    # Get Task by id to the robot
    @http.route("/v1/task/<int:task_id>",methods=["GET"], type="http", auth="none", csrf=False)
    def get_task(self, task_id):
        try:
            task_id = request.env['robot_fleet.task'].sudo().search([('id', '=', task_id)])
            if task_id:
                return request.make_json_response({
                    "id": task_id.id,
                    "name" : task_id.name,
                    "ref" : task_id.ref,
                    "description" : task_id.description,
                    "begins" : task_id.task_begins,
                    "ends" : task_id.task_ends,
                    "status" : task_id.status,
                    "source_station_id" : task_id.source_station_id.id,
                    "destination_station_id" : task_id.destination_station_id.id,
                    "owner" : task_id.task_owner_id.id,
                    "assigned_robots": [{
                        "id": robot.id,
                        "name": robot.name,
                        "serial_number": robot.serial_number,
                        "robot_type": robot.robot_type,
                        "status": robot.status_robot,
                        "capacity": robot.capacity,
                        "current_location_id": robot.current_location_id.id,
                        "company_id": robot.company_id.id,
                        "current_task_id": robot.current_task_id
                    } for robot in task_id.robot_ids]
                }, status=200)

            else:
                return request.make_json_response({
                    "success": False,
                    "message": "Task IDs didn't found"}, status=400)

        except Exception as error:
            error_msg = f"Server error: {str(error)}"
            _logger.error(f"{CYAN}{error_msg}{RESET}")
            return request.make_json_response({
                "success": False,
                "message": error_msg}, status=400)

    @http.route("/v1/task/update/<int:task_id>", methods=["PUT"], type="http", auth="none", csrf=False)
    def update_task(self, task_id):
        """
        Updates a task's status in Odoo.
        Expects JSON payload: {}
        Returns: {'success': bool, 'message': str}
        """
        try:
            task_id = request.env['robot_fleet.task'].sudo().search([('id', '=', task_id)])
            # Parse incoming JSON data
            args = request.httprequest.data.decode()
            vals = json.loads(args)
            _logger.info(f"{GREEN}Received data: {vals}{RESET}")

            if task_id:
                task_status = vals.get("status")
                if task_status:
                    if task_status == 'new':
                        task_id.action_new()
                    elif task_status == 'in_progress':
                        task_id.action_in_progres()
                    # Würde bei beliebiegen task_status ausgeführt werden...
                    else:
                        task_id.action_done()
                if task_id.write(vals):
                    return request.make_json_response({
                        "success": True,
                        "message": "Task updated successfully"}, status=201)

            else:
                return request.make_json_response({
                    "success": False,
                    "message": "Task IDs didn't found"}, status=400)

        except Exception as error:
            error_msg = f"Server error: {str(error)}"
            _logger.error(f"{CYAN}{error_msg}{RESET}")
            return request.make_json_response({
                "success": False,
                "message": error_msg}, status=400)

        # Get Task by id to the robot
    @http.route("/v1/tasks", methods=["GET"], type="http", auth="none", csrf=False)
    def get_all_tasks(self):
        try:
            """
            1. Parse query string (?status=new&company_id=3) into a dict where each key has a list of values.
            2. Build an Odoo search domain list based on available parameters.
            3. If 'status' is present, add ('status', '=', <value>) to the domain.
            4. If 'company_id' is present, convert it to int and add ('company_id', '=', <value>) to the domain.
            5. Search 'robot_fleet.task' with the built domain using sudo() to ignore record rules.
            """
            params = parse_qs(request.httprequest.query_string.decode('utf-8'))
            task_search_domain = []
            if params.get('status'):
                task_search_domain += [('status','=',params.get('status')[0])]
            if params.get('company_id'):
             #   print(params.get('company_id'))
                task_search_domain += [('company_id','=',int(params.get('company_id')[0]))]
              #  print(task_search_domain)
            task_ids = request.env['robot_fleet.task'].sudo().search(task_search_domain)
            if task_ids:
                return request.make_json_response([{
                    "id": task_id.id,
                    "name": task_id.name,
                    "ref": task_id.ref,
                    "description": task_id.description,
                    "begins": task_id.task_begins,
                    "ends": task_id.task_ends,
                    "status": task_id.status,
                    "source_station_id": task_id.source_station_id.id,
                    "destination_station_id": task_id.destination_station_id.id,
                    "owner": task_id.task_owner_id.id,
                    "company_id":task_id.company_id.id,
                    "assigned_robots": [{
                        "id": robot.id,
                        "name": robot.name,
                        "serial_number": robot.serial_number,
                        "robot_type": robot.robot_type,
                        "status": robot.status_robot,
                        "capacity": robot.capacity,
                        "current_location_id": robot.current_location_id.id,
                        "company_id": robot.company_id.id,
                        "current_task_id": robot.current_task_id
                    } for robot in task_id.robot_ids]
                } for task_id in task_ids], status=200)

            else:
                return request.make_json_response({
                    "success": False,
                    "message": "Task IDs didn't found"}, status=400)

        except Exception as error:
            error_msg = f"Server error: {str(error)}"
            _logger.error(f"{CYAN}{error_msg}{RESET}")
            return request.make_json_response({
                "success": False,
                "message": error_msg}, status=400)