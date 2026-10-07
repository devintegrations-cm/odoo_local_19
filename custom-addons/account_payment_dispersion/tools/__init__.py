# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
_logger = logging.getLogger(__name__)


def _column_name_field(names, ws):
    letters = get_excel_column_letters(len(names))
    for index, name in enumerate(names, start=0):
        ws[f'{letters[index]}4'] = name
    return ws

def get_excel_column_letters(num_columns) -> list:
    letters = []
    for i in range(num_columns):
        # Convertir el índice a letras de columna (0-indexed)
        letter = ""
        n = i
        while n >= 0:
            # Agregar la letra correspondiente al valor actual de n
            letter = chr(ord('A') + n % 26) + letter
            # Reducir n teniendo en cuenta que las letras de Excel son 1-indexed
            n = n // 26 - 1
        letters.append(letter)
    return letters