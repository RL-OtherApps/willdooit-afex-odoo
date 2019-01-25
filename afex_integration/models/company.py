# -*- coding: utf-8 -*-

from odoo import api, fields, models

VALUE_DATE_TYPES = [
    ('CASH', 'Today'),
    ('TOM', 'Next business day'),
    ('SPOT', 'Two business days'),
    ]


class ResCompany(models.Model):
    _inherit = "res.company"

    afex_api_key = fields.Char(
        string='AFEX API Key', copy=False,
        oldname='afex_api')
    afex_allow_earliest_value_date = fields.Boolean(
        string="Allow Earliest Value Date", copy=False,
        help=("Leave this disabled if your trade requests should always"
              " choose the 'Two business days' rate. If you wish users to"
              " to be able to choose 'Today' or 'Next business day' rate,"
              " then enable this option."))
    afex_value_date_type = fields.Selection(
        selection=VALUE_DATE_TYPES, string="Default Value Date",
        default='SPOT', copy=False,
        help=("If users can choose rates other than 'Two business days',"
              " then this will be required to be the default rate."))

    @api.onchange('afex_allow_earliest_value_date')
    def onchange_value_date(self):
        self.afex_value_date_type = 'SPOT'

    @api.multi
    def write(self, values):
        if 'afex_allow_earliest_value_date' in values and not values['afex_allow_earliest_value_date']:
            values['afex_value_date_type'] = 'SPOT'
        return super(ResCompany, self).write(values)
