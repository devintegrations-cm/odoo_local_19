# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api



class TelegramAlertsConfig(models.Model):
    _name = 'telegram.alerts.config'
    _description = 'Telegram Alerts Configuration'

    name = fields.Char(string="Name", required=True, help="Name")
    identifier = fields.Char(string="Custom ID", required=True, help="Field to easy identify the telegram connector")
    token = fields.Char(string="Telegram Bot Token", required=True, help="Access Token")
    user_ids = fields.Text(string="User IDs (comma-separated)", required=True, help="Set user/group id to send messages, separated by comma")
    msg_test = fields.Text(string="Testing Message", required=True, help='This message woul be sent when you use "Send Telegram Alert" action')

    def send_message(self, user_id, text):
        for record in self:
            url = f'https://api.telegram.org/bot{record.token}/sendMessage'
            params = {
                "chat_id": user_id,
                "text": text,
            }
            resp = requests.get(url, params=params)
            resp.raise_for_status()

    def send_alert(self, message):
        for record in self:
            user_ids = record.user_ids.split(',')
            for user_id in user_ids:
                self.send_message(user_id.strip(), message)
                
    def send_alert_test(self):
        for record in self:
            record.send_alert(record.msg_test)
