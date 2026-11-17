# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

# Segundos máximos por llamada a Telegram: sin timeout un Telegram colgado retiene el worker (p. ej. el que
# valida una recepción en purchase_cost_validator) hasta limit_time_real.
TELEGRAM_TIMEOUT = 10



class TelegramAlertsConfig(models.Model):
    _name = 'telegram.alerts.config'
    _description = 'Telegram Alerts Configuration'

    name = fields.Char(string="Name", required=True, help="Name")
    identifier = fields.Char(string="Custom ID", required=True, help="Field to easy identify the telegram connector")
    # groups: el token solo lo lee y escribe Administración / Ajustes (TELEGRAM-SEC-0001). El envío corre con
    # sudo() en los llamadores (product_template, purchase_cost_validator) y en el cron.
    token = fields.Char(string="Telegram Bot Token", required=True, help="Access Token", groups="base.group_system")
    user_ids = fields.Text(string="User IDs (comma-separated)", required=True, help="Set user/group id to send messages, separated by comma")
    msg_test = fields.Text(string="Testing Message", required=True, help='This message woul be sent when you use "Send Telegram Alert" action')

    def send_message(self, user_id, text):
        for record in self:
            url = f'https://api.telegram.org/bot{record.token}/sendMessage'
            params = {
                "chat_id": user_id,
                "text": text,
            }
            # La URL lleva el token: ni HTTPError ni ConnectionError de requests pueden llegar al log ni al
            # diálogo de error (su mensaje incluye la URL). Se relanza sin la causa (from None) y sin el chat id.
            try:
                resp = requests.get(url, params=params, timeout=TELEGRAM_TIMEOUT)
                resp.raise_for_status()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                raise UserError(self.env._(
                    "Telegram rejected the message from connector %(connector)s (HTTP %(status)s).",
                    connector=record.identifier, status=status,
                )) from None
            except requests.RequestException as exc:
                raise UserError(self.env._(
                    "Could not reach Telegram from connector %(connector)s (%(error)s).",
                    connector=record.identifier, error=type(exc).__name__,
                )) from None

    def send_alert(self, message):
        for record in self:
            user_ids = record.user_ids.split(',')
            for user_id in user_ids:
                self.send_message(user_id.strip(), message)
                
    def send_alert_test(self):
        for record in self:
            record.send_alert(record.msg_test)
