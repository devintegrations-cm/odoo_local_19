# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import models, fields

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    face_details = fields.Char(string="Detalles de caras", help="Detalles de las caras")
    #img_raw = fields.Char(string="Imagen Original", help="Imagen base64 original", readonly=False)
    #img_bounding = fields.Char(string="Imagen con recuadros", help="Imagen procesada", readonly=False)

    def _process_order(self, order, existing_order):
        # face_details lo escribe solo el servicio de cámaras (XML-RPC). En 17
        # el POS no lo enviaba (export_as_JSON no lo incluía); en 19 el POS
        # carga y serializa todos los campos almacenados de pos.order
        # (related_models/serialization.js: lo que no tiene valor viaja como
        # False) y _process_order hace write(order) sobre la orden existente,
        # así que una resincronización borraría lo que ya escribió el servicio.
        order.pop('face_details', None)
        return super()._process_order(order, existing_order)

    def split_and_add_underscore(self, text):
        result = re.sub(r'(?<!^)(?=[A-Z])', '_', text).lower()
        return result
    
    def quitar_letras_y_espacios(self, cadena):
        return re.sub(r'[a-zA-Z\s]', '', cadena)

    def flatten_dict(self, d, parent_key='', sep='_'):
        items = {}
        for k, v in d.items():
            new_key = self.split_and_add_underscore(k)
            if parent_key:
                new_key = f"{parent_key}{sep}{new_key}"        
            if isinstance(v, dict):
                items.update(self.flatten_dict(v, new_key, sep=sep))
            else:
                items[new_key] = v
        return items

    def process_emotions(self, emotions_list):
        map_emotions = {}
        for k in emotions_list:
            name, conf = k.get('Type',''), k.get('Confidence',0)
            key_name = f'emotions_{name.lower()}'
            key_conf = f'{key_name}_confidence'
            map_emotions[key_name+'_value'] = True
            map_emotions[key_conf] = conf
        return map_emotions

    def update_face_details_model(self, uid_order, data):
        face_details_mapped = []
        
        for d in data:
            info = self.flatten_dict(d)
            emo = info.pop('emotions', [])
            mapped_emotions = self.process_emotions(emo)
            info.update(mapped_emotions)
            info['pos_order_uid'] = uid_order
            face_details_mapped.append(info)

        if face_details_mapped:
            try:
                # Verificar si ya existe el registro en base a 'pos_order_uid' y otra clave única (ejemplo: bounding_box)
                existing_record = self.env['face.details'].search([
                    ('pos_order_uid', '=', uid_order),
                ], limit=1)
                if existing_record:
                    _logger.info("El registro ya existe para pos_order_uid: %s", uid_order)
                else:
                    # Crear los registros nuevos en el modelo face.details
                    self.env['face.details'].create(face_details_mapped)
                    _logger.info("Se han creado %s registros nuevos en face.details.", len(face_details_mapped))
            except Exception as e:
                _logger.exception("Error al actualizar face details: %s", e)

    def update_face_details_action(self):
        # Filtrar solo los registros que tienen face_details seteado
        orders_with_face_details = self.filtered(lambda order: bool(order.face_details))
        
        for order in orders_with_face_details:
            if order.face_details:
                try:
                    face_data = json.loads(order.face_details)
                    self.update_face_details_model(self.quitar_letras_y_espacios(order.pos_reference), face_data)
                except Exception as e:
                    _logger.exception("Error al procesar face_details: %s", e)
