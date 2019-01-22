from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


AFEX_ADD_SYNC_DEFINITION = {
    'RemittanceLine1': {
        'name': 'Remittance Line 1',
        'length': 35,
        },
    'RemittanceLine2': {
        'name': 'Remittance Line 2',
        'length': 35,
        },
    'RemittanceLine3': {
        'name': 'Remittance Line 3',
        'length': 35,
        },
    'RemittanceLine4': {
        'name': 'Remittance Line 4',
        'length': 35,
        },
    'BankSWIFTBIC': {
        'name': 'Bank SWIFT BIC',
        },
    'BankRoutingcode': {
        'name': 'Bank Routing Code',
        },
    'IntermediaryBankSWIFTBIC': {
        'name': 'Intermediary Bank SWIFT BIC',
        },
    'IntermediaryBankName': {
        'name': 'Intermediary Bank Name',
        },
    'IntermediaryBankRoutingCode': {
        'name': 'Intermediary Bank Routing Code',
        },
    'IntermediaryBankAccountNumber': {
        'name': 'Intermediary Bank Account Number',
        },
    }
AFEX_ADD_SYNC_FIELDS = [
    (k, v['name']) for k, v in AFEX_ADD_SYNC_DEFINITION.items()
    ]


# This message is included when an error occurs, and is intended to help users
# determine odoo fields vs AFEX fields

PARTNER_AFEX_DESC_TEXT = """

NOTES:

    A new Partner will be linked to an existing AFEX Beneficiary if the Beneficiary has already been setup in AFEX with the exact same name.

When creating a new Beneficiary:

    Currency comes from the selected bank's currency.
    The Beneficiary name is the name of this Partner.
    All payments to the beneficiary will be via wire.
    The Notification Email will be the Partner's Email Address.
    Beneficiary Address Details come from this Partner (address line 2 is optional).
    The Bank Name is the name of the Partner's Bank Account.
    Bank Account Number is the Partner's Bank Account Number.
    Remittance Lines and Other Important Additional Information will come from the Partner's Bank "AFEX Sync Information".
    (If remittance line 1 is not entered, your company name will be sent).
"""


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    is_afex = fields.Boolean(
        string="AFEX Beneficiary", default=False,
        copy=False)
    afex_bank_country_id = fields.Many2one(
        'res.country',
        string="AFEX Bank Country",
        copy=False)
    afex_int_bank_country_id = fields.Many2one(
        'res.country',
        string="AFEX Intermediary Bank Country",
        copy=False)
    afex_corporate = fields.Boolean(
        string="AFEX Corporate", default=False,
        help='This must be checked if the beneficiary is a Corporation and '
        'left blank if the beneficiary is an Individual',
        copy=False)
    add_afex_info_ids = fields.One2many(
        'afex.additional.sync.fields', 'bank_id',
        string="AFEX Sync Information",
        copy=False)
    afex_unique_id = fields.Char(
        copy=False
    )
    afex_sync_status = fields.Selection(
        [('needed', 'Sync Needed'),
         ('done', 'Synchronised'),
         ],
        string='AFEX Status',
        default='needed',
        readonly=True
        )

    @api.multi
    def write(self, vals):
        for bank in self:
            if 'currency_id' in vals and bank.afex_unique_id:
                raise UserError(
                    _('Cannot change Bank Currency for a Bank which is'
                      ' already synchronised with AFEX'))
        if 'afex_sync_status' not in vals:
            vals['afex_sync_status'] = 'needed'
        return super(ResPartnerBank, self).write(vals)

    def sync_beneficiary_afex(self):
        for bank in self:
            if not bank.currency_id:
                raise UserError(
                        _('AFEX Beneficiary Bank Account does not contain '
                          'a Currency'))

            # if no afex id, first see if there is one
            if not bank.afex_unique_id:
                bank.update_beneficiary_afex_id()

            # if bank has afex id or just linked, then send details
            if bank.afex_unique_id:
                bank.update_beneficiary_afex()
            else:
                new_afex_id = '%s%s%s' % \
                    (bank.partner_id.id, bank.currency_id.name or 'x', bank.id)

                url = "beneficiarycreate"
                data = bank.return_afex_data()
                data['VendorId'] = new_afex_id
                # create new beneficiary
                response_json = self.env['afex.connector'].afex_response(
                        url, data=data, post=True)
                if response_json.get('ERROR', True):
                    raise UserError(
                        _('Error while creating beneficiary: %s %s') %
                        (response_json.get('message', ''),
                         _(PARTNER_AFEX_DESC_TEXT))
                    )

                bank.afex_unique_id = new_afex_id
            bank.afex_sync_status = 'done'

    def update_beneficiary_afex_id(self):
        self.ensure_one()
        # update the bank afex ID with get from afex
        url = "beneficiary"
        response_json = self.env['afex.connector'].afex_response(url)
        if response_json.get('ERROR', True):
            raise UserError(
                    _('Error while checking existing beneficiaries: %s') %
                    (response_json.get('message', ''),)
                    )
        for item in response_json.get('items', []):
            if item.get('Name', '') == self.partner_id.name \
                    and item.get('Currency', '') == self.currency_id.name:
                if not item.get('VendorId'):
                    raise UserError(
                        _('Vendor name and currency exists on AFEX but'
                          " it doesn't have a Vendor Id")
                        )
                if self.search(
                        [('afex_unique_id', '=', item['VendorId'])]):
                    raise UserError(
                        _('Vendor name and currency exists on AFEX but'
                          ' already linked on Odoo to another beneficiary')
                        )
                self.afex_unique_id = item['VendorId']
                break

    def update_beneficiary_afex(self):
        self.ensure_one()
        # update afex with new details
        url = "beneficiaryupdate"
        data = self.return_afex_data()
        data['VendorId'] = self.afex_unique_id
        response_json = self.env['afex.connector'].afex_response(
                url, data=data, post=True)
        if response_json.get('ERROR', True):
            raise UserError(
                _('Error while updating beneficiary: %s%s') %
                (response_json.get('message', ''),
                 _(PARTNER_AFEX_DESC_TEXT))
                )

    def return_afex_data(self):
        self.ensure_one()

        partner = self.partner_id
        # data returned for creation and updates
        data = {'Currency': self.currency_id.name or '',
                'BeneficiaryName': partner.name or '',
                'TemplateType': 1,
                'NotificationEmail': partner.email or '',
                'BeneficiaryAddressLine1': partner.street or '',
                'BeneficiaryCity': partner.city or '',
                'BeneficiaryCountrycode': partner.country_id.code or '',
                'BeneficiaryPostalCode': partner.zip or '',
                'BeneficiaryRegion': partner.state_id.code or '',
                'BankName': self.bank_id.name or '',
                'BankAccountNumber': self.acc_number or '',
                'RemittanceLine1': partner.company_id.name or '',
                'HighLowValue': '1',  # default as high value

                'Corporate': self.afex_corporate,
                'BeneficiaryAddressLine2': partner.street2 or '',
                'BankCountryCode': self.afex_bank_country_id.code or '',
                'IntermediaryBankCountryCode':
                self.afex_int_bank_country_id.code or '',
                }

        # optional data - only provided if entered
        for line in self.add_afex_info_ids:
            error, value = line.validate_value()
            if value:
                data[line.field] = value

        return data


class AFEXAddFields(models.Model):
    _name = "afex.additional.sync.fields"
    _description = "AFEX Additional Sync Fields"

    bank_id = fields.Many2one('res.partner.bank', required=True)
    field = fields.Selection(AFEX_ADD_SYNC_FIELDS, required=True)
    value = fields.Char(required=True)

    @api.multi
    @api.constrains('field', 'value')
    def _constrain_values(self):
        for addl in self:
            error, value = addl.validate_value()
            if error:
                raise UserError(error)

    @api.model
    def create(self, vals):
        result = super(AFEXAddFields, self).create(vals)
        result.mapped('bank_id').write({})
        return result

    @api.multi
    def write(self, vals):
        self.mapped('bank_id').write({})
        return super(AFEXAddFields, self).write(vals)

    @api.multi
    def unlink(self):
        self.mapped('bank_id').write({})
        return super(AFEXAddFields, self).unlink()

    def validate_value(self):
        definition = AFEX_ADD_SYNC_DEFINITION.get(self.field, {})
        max_length = definition.get('length')
        if self.value and max_length and len(self.value) > max_length:
            return (
                _('Value for "%s" is over %s chars long.')
                % (definition['name'], max_length)),\
                self.value[:max_length]
        return False, self.value or ''

    @api.onchange('field', 'value')
    def onchange_value(self):
        warnings = []
        error, value = self.validate_value()
        if error:
            warnings.append(error)
            self.value = value

        result = {}
        if warnings:
            result['warning'] = {
                'title': _('WARNING'),
                'message': '\n'.join(warnings),
                }
        return result


class ResPartner(models.Model):
    _inherit = "res.partner"

    afex_bank_ids = fields.One2many(
        'res.partner.bank',
        compute='_compute_afex_banks')
    afex_sync_status = fields.Selection(
        [('needed', 'Sync Needed'),
         ('done', 'Synchronised'),
         ('na', 'Not Applicable'),
         ],
        string='AFEX Status',
        compute='_compute_afex_sync_status'
        )

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if set(vals.keys()) &\
                set(['name', 'email', 'street', 'city',
                    'country_id', 'state_id', 'company_id']):
            for partner in self:
                partner.afex_bank_ids.write({'afex_sync_status': 'needed'})
        return res

    @api.one
    def _compute_afex_banks(self):
        self.afex_bank_ids = self.bank_ids.filtered(lambda b: b.is_afex)

    @api.one
    def _compute_afex_sync_status(self):
        if self.afex_bank_ids:
            self.afex_sync_status = any(
                b.afex_sync_status == 'needed' for b in self.afex_bank_ids) \
                and 'needed' or 'done'
        else:
            self.afex_sync_status = 'na'

    def afex_bank_for_currency(self, currency):
        self.ensure_one()
        return self.env['res.partner.bank'].search(
            [('partner_id', '=', self.id),
             ('is_afex', '=', True),
             ('currency_id', '=', currency.id)
             ],
            limit=1
            )

    @api.multi
    def sync_partners_afex(self):

        bank_accounts = self.env['res.partner.bank']

        for partner in self:
            if not partner.name:
                raise UserError(_(
                    'Vendor encountered with no name'))
            if not partner.supplier:
                raise UserError(_(
                    'Partner %s is not a vendor')
                    % (partner.name,))
            if not partner.company_id:
                raise UserError(_(
                    'Vendor %s is not linked to a company')
                    % (partner.name,))
            if not partner.afex_bank_ids:
                raise UserError(_(
                    'Vendor %s does not have any AFEX Beneficiary Bank'
                    ' accounts')
                    % partner.name)
            partner_banks = partner.bank_ids.filtered(
                    lambda b: b.is_afex and b.afex_sync_status == 'needed')
            if not partner_banks:
                raise UserError(_(
                    'Vendor %s does not have any Beneficiary Bank accounts'
                    ' which need to be synchronised')
                    % partner.name)
            bank_accounts |= partner_banks

        bank_accounts.sync_beneficiary_afex()
