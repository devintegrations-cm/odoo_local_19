# -*- coding: utf-8 -*-
# from odoo import http


# class L10nCoEdiFxJorelsPosLoyalty(http.Controller):
#     @http.route('/l10n_co_edi_fx_jorels_pos_loyalty/l10n_co_edi_fx_jorels_pos_loyalty', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_co_edi_fx_jorels_pos_loyalty/l10n_co_edi_fx_jorels_pos_loyalty/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_co_edi_fx_jorels_pos_loyalty.listing', {
#             'root': '/l10n_co_edi_fx_jorels_pos_loyalty/l10n_co_edi_fx_jorels_pos_loyalty',
#             'objects': http.request.env['l10n_co_edi_fx_jorels_pos_loyalty.l10n_co_edi_fx_jorels_pos_loyalty'].search([]),
#         })

#     @http.route('/l10n_co_edi_fx_jorels_pos_loyalty/l10n_co_edi_fx_jorels_pos_loyalty/objects/<model("l10n_co_edi_fx_jorels_pos_loyalty.l10n_co_edi_fx_jorels_pos_loyalty"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_co_edi_fx_jorels_pos_loyalty.object', {
#             'object': obj
#         })
