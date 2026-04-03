from odoo import models, fields,api
from odoo.exceptions import ValidationError
from datetime import timedelta
from odoo import http
from odoo.http import request
import json
import logging
import requests
_logger = logging.getLogger(__name__)
from odoo.tools import config

class Task(models.Model):
    _name = 'robot_fleet.task'
    _description = 'Robot Task'
    _inherit = ['mail.thread','mail.activity.mixin']
    #Archiving
    active = fields.Boolean(default=True)

    tags_ids = fields.Many2many('task_tag')

    # add ref to present a sequences
    ref=fields.Char(default='New',readonly=1)

    name=fields.Char(string='Task Name')
    description = fields.Text(string='Task Description', tracking=1 )
    task_begins = fields.Datetime(tracking=1)
    task_ends = fields.Datetime()

    # TODO In state umbenennen und Model aktualisieren
    status = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], string='Status', default='new',tracking=1)

    robot_id = fields.Many2one('robot', string='Assigned Robot',tracking=1)
    task_owner_id = fields.Many2one('task.owner',tracking=1)

    robot_ids = fields.One2many('robot','task_id',tracking=1)

    source_station_id = fields.Many2one('station', string='Source Station',tracking=1)
    destination_station_id = fields.Many2one('station', string='Destination Station',tracking=1)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        help="Company this task belongs to"
    )

    shipment_ids = fields.One2many(
        'robot_fleet.shipment',
        'task_id',
        string='Shipment Items'
    )

    total_shipment_weight = fields.Float(
        string="Total Shipment Weight (kg)",
        compute="_compute_total_shipment_weight",
        store=True
    )

    waiting_station_id = fields.Many2one(
        'station',
        string='Waiting Area',
        tracking=1,
        domain="[('station_type', '=', 'waiting')]",
    )


    def action_new(self):
        for rec in self:
            rec.status='new'

    def action_in_progres(self):
        for rec in self:
            if not rec.robot_ids:
                raise ValidationError("Please assign Robot/s")
            rec.status = 'in_progress'
            for robot in rec.robot_ids:
                robot.status_robot = 'active'
                robot.current_task_id = rec.id
                rec.task_begins = fields.Datetime.now()

    def action_done(self):
        for rec in self:
            rec.status = 'done'
            rec.task_ends = fields.Datetime.now()
            for robot in rec.robot_ids:
                robot.status_robot = 'idle'
                robot.current_task_id = False
                robot.completed_task_ids |= rec



    @api.model
    def create (self,vals):
        res = super(Task,self).create(vals)
        if res.ref == 'New':
            res.ref = self.env['ir.sequence'].next_by_code('task_seq')

        try:
            self.send_task_to_middleware(res)
        except Exception as e:
            _logger.error(f"Webhook-Aufruf für Task {res.ref} ist fehlgeschlagen (wird ignoriert): {e}")
        print(res.ref)
        return res

    """
    For each robot assigned to the task:
    It checks if status_robot == 'active'
    Then checks if robot.current_task_id.ref != task.ref (i.e., robot is active and working on a different task)
    If such robots exist, it blocks the assignment and gives their names
    """
    @api.constrains('robot_ids')
    def _check_robot_not_active(self):
        for task in self:
            active_robots = []
            for robot in task.robot_ids:
                if robot.status_robot == 'active':
                    if not robot.current_task_id or robot.current_task_id.ref != task.ref:
                        if robot.name not in active_robots:
                            active_robots.append(robot.name)
            # if active_robots:
            #     robot_names = ', '.join(active_robots)
            #     raise ValidationError(f"Cannot assign active robot(s) to a task: {robot_names}")

    def send_task_to_middleware(self, task_record):
        """
        Bereitet die Task-Daten vor und sendet sie per Webhook an die Middleware.
        """
        #MIDDLEWARE_WEBHOOK_URL = "https://webhook.site/7684436f-8832-41a0-bafb-6632308b8c5e"

        mw_host = config.get('middleware_api_host')
        mw_port = config.get('middleware_api_port')
        _logger.info(f"mw_host: {mw_host}, mw_port: {mw_port}")

        if not mw_host or not mw_port:
            _logger.warning(
                f"Middleware-Wexycvxcyvxcvxyvxcbhook-URL ist nicht konfiguriert. Überspringe Sendung für Task {task_record.ref}.")
            return

        try:
            # Daten für die Middleware zusammenstellen
            task_data = {
                    "id": task_record.id,
                    "name" : task_record.name,
                    "ref" : task_record.ref,
                    "description" : task_record.description,
                    "begins" : task_record.task_begins,
                    "ends" : task_record.task_ends,
                    "state" : task_record.status,
                    "source_station_id" : task_record.source_station_id.id,
                    "destination_station_id" : task_record.destination_station_id.id,
                    "owner" : task_record.task_owner_id.id,
                    "waiting_station_id": task_record.waiting_station_id.id,
                    "map_id": 1,
                    "assigned_robots": [{
                        "id": robot.id,
                        "name": robot.name,
                        "serial_number": robot.serial_number,
                        "robot_type": robot.robot_type,
                        "state": robot.status_robot,
                        "capacity": robot.capacity,
                        "current_location_id": robot.current_location_id.id,
                        "company_id": robot.company_id.id,
                        "current_task_id": task_record.id,
                        "battery_low_threshold": robot.battery_low_threshold,
                        "charging_station_id": robot.charging_station_id.id,
                    } for robot in task_record.robot_ids]
                }

            headers = {'Content-Type': 'application/json'}
            url = f"http://{mw_host}:{mw_port}/api/v1/webhooks/new_task"
            # Senden des POST-Requests
            _logger.info(f"Sende Task {task_record.ref} an Middleware: {url}")
            response = requests.post(
                url,
                data=json.dumps(task_data, default=str),
                headers=headers,
                timeout=10  # Timeout von 10 Sekunden
            )

            # Fehler auslösen, wenn der HTTP-Status ein Fehler
            response.raise_for_status()


            _logger.info(f"Task {task_record.ref} erfolgreich an Middleware gesendet. Status: {response.status_code}")

        except requests.exceptions.RequestException as e:

            _logger.error(f"Fehler beim Senden von Task {task_record.ref} an Middleware: {e}")
            _logger.info(response.data)
        except Exception as e:

            _logger.error(f"Unerwarteter Fehler beim Senden des Webhook für Task {task_record.ref}: {e}")

    @api.constrains('robot_id', 'company_id')
    def _check_robot_company(self):
        for task in self:
            if task.robot_id and task.robot_id.company_id != task.company_id:
                raise ValidationError((
                    f"Robot {task.robot_id.name} belongs to company {task.robot_id.company_id.name} "
                    f"while task belongs to {task.company_id.name}. "
                    "Please select a robot from the correct company."
                ))



    @api.depends('shipment_ids.weight', 'shipment_ids.quantity')
    def _compute_total_shipment_weight(self):
        for task in self:
            task.total_shipment_weight = sum(
                item.weight * item.quantity for item in task.shipment_ids
            )


    @api.constrains('shipment_ids', 'robot_ids')
    def _check_capacity(self):
        for task in self:
            total_weight = sum(item.weight * item.quantity for item in task.shipment_ids)
            total_capacity = sum((robot.capacity or 0) for robot in task.robot_ids)

            if total_capacity and total_weight > total_capacity:
                raise ValidationError(
                    f"Total shipment weight is {total_weight}kg, but the assigned robots "
                    f"can only carry {total_capacity}kg."
                )