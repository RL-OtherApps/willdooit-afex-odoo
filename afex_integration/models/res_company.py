from odoo import api, fields, models

VALUE_DATE_TYPES = [
    ('SPOT', 'SPOT'),
    ('CASH', 'CASH'),
    ('TOM', 'TOM'),
    ]


class ResCompany(models.Model):
    _inherit = 'res.company'

    afex_api_key = fields.Char(
        string="AFEX API Key", copy=False,
        oldname='afex_api')
    afex_allow_earliest_value_date = fields.Boolean(
        string="Allow Earliest Value Date", copy=False)
    afex_value_date_type = fields.Selection(
        selection=VALUE_DATE_TYPES, string="Default Value Date",
        default='SPOT', copy=False)

    @api.onchange('afex_allow_earliest_value_date')
    def onchange_value_date(self):
        self.afex_value_date_type = 'SPOT'
