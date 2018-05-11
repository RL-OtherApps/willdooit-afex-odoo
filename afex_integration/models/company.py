# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    afex_api_key = fields.Char(
        string='AFEX API Key', copy=False,
        oldname='afex_api')
