import json

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class SyncAFEXBeneficiary(models.TransientModel):
    _name = 'sync.afex.beneficiary'
    _description = "AFEX Beneficiary Sync"

    name = fields.Text(string="AFEX Beneficiary Data", readonly=True)
    data_original = fields.Text(string="AFEX Beneficiary Data (Original)")
    bank_id = fields.Many2one('res.partner.bank', string="Bank")

    @api.model
    def default_get(self, default_fields):
        result = super(SyncAFEXBeneficiary, self).default_get(default_fields)

        if len(self.env.context.get('active_ids', [])) != 1:
            raise ValidationError(_("Please sync only one partner bank."))

        bank = self.env['res.partner.bank'].browse(
            self.env.context['active_id'])
        if not bank.afex_unique_id:
            raise ValidationError(_("No VendorID found for vendor name "
                                    "and currency. Try AFEX Sync first."))

        # Get/Find beneficiary
        url = 'beneficiary/find?VendorID=%s' % bank.afex_unique_id
        response_json = self.env['afex.connector'].afex_response(url)
        if response_json.get('ERROR', True):
            raise UserError(
                _("Error while getting/finding the beneficiary: %s") %
                  (response_json.get('message', ''))
            )
        result.update({
            'name': json.dumps(response_json, indent=4, sort_keys=True),
            'data_original': response_json,
            'bank_id': bank.id,
        })
        return result

    @api.multi
    def action_sync(self):
        self.ensure_one()
        data = safe_eval(self.data_original)
        self.bank_id.sync_from_afex_beneficiary_find(data)
