# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError, ValidationError


AFEX_ADD_SYNC_FIELDS = [
    ('RemittanceLine1', 'Remittance Line 1'),
    ('RemittanceLine2', 'Remittance Line 2 (PoP)'),
    ('RemittanceLine3', 'Remittance Line 3'),
    ('RemittanceLine4', 'Remittance Line 4'),
    ('BankSWIFTBIC', 'Bank SWIFT BIC'),
    ('BankRoutingcode', 'Bank Routing Code'),
    ('IntermediaryBankSWIFTBIC', 'Intermediary Bank SWIFT BIC'),
    ('IntermediaryBankName', 'Intermediary Bank Name'),
    ('IntermediaryBankRoutingCode', 'Intermediary Bank Routing Code'),
    ('IntermediaryBankAccountNumber', 'Intermediary Bank Account Number'),
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

    def afex_partner_reset(self):
        self.filtered(lambda b: b.is_afex).mapped('partner_id').write(
            {'afex_sync_status': 'needed'})

    @api.model
    def create(self, vals):
        result = super(ResPartnerBank, self).create(vals)
        if vals.get('is_afex'):
            result.afex_partner_reset()
        return result

    @api.multi
    def write(self, vals):
        for bank in self:
            if 'currency_id' in vals and bank.afex_unique_id:
                raise UserError(
                    _('Cannot change Bank Currency for a Bank which is'
                      ' already synchronised with AFEX'))
        # old mappings
        self.afex_partner_reset()
        result = super(ResPartnerBank, self).write(vals)
        if 'is_afex' in vals or 'partner_id' in vals:
            self.afex_partner_reset
        return result

    @api.multi
    def unlink(self):
        self.afex_partner_reset()
        return super(ResPartnerBank, self).unlink()

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
                continue

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
                            _('Vendor name and currency exists on AFEX but '
                              "it doesn't have a Vendor Id")
                            )
                    if self.search(
                            [('afex_unique_id', '=', item['VendorId'])]):
                        raise UserError(
                            _('Vendor name and currency exists on AFEX but '
                              'already linked on Odoo to another beneficiary')
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
                }

        # optional data - only provided if entered
        if partner.street2:
            data['BeneficiaryAddressLine2'] = partner.street2
        if self.afex_bank_country_id:
            data['BankCountryCode'] = \
                self.afex_bank_country_id.code
        if self.afex_int_bank_country_id:
            data['IntermediaryBankCountryCode'] = \
                self.afex_int_bank_country_id.code
        if self.afex_corporate:
            data['Corporate'] = self.afex_corporate
        for line in self.add_afex_info_ids:
            data[line.field] = line.value
        return data


class AFEXAddFields(models.Model):
    _name = "afex.additional.sync.fields"

    bank_id = fields.Many2one('res.partner.bank', required=True)
    field = fields.Selection(AFEX_ADD_SYNC_FIELDS, required=True)
    value = fields.Char(required=True)

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


class ResPartner(models.Model):
    _inherit = "res.partner"

    afex_banks = fields.Boolean(compute='_compute_afex_banks')
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
        if set(vals.keys()) &\
                set(['name', 'email', 'street', 'city',
                    'country_id', 'state_id', 'company_id']):
            vals['afex_sync_status'] = 'needed'
        return super(ResPartner, self).write(vals)

    @api.one
    def _compute_afex_banks(self):
        self.afex_banks = self.bank_ids.filtered(lambda b: b.is_afex)

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
        partners = self.browse(self.env.context.get('active_ids') or
                               self.env.context.get('active_id'))
        if partners.filtered(lambda p: not p.afex_banks or not p.bank_ids):
            raise UserError(_(
                'Vendor %s does not have an AFEX Beneficiary Bank account')
                % partners.filtered(lambda p: not p.afex_banks)[0].name)
        for partner in partners:
            if not partner.name:
                continue
            if not partner.supplier:
                raise UserError(_('AFEX is currently only used for Vendors'))
            if not partner.company_id:
                raise UserError(_('Vendor is not linked to a company'))

            banks = partner.bank_ids.filtered(lambda z: z.is_afex)
            banks.sync_beneficiary_afex()
            partner.afex_sync_status = 'done'
