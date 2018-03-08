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

    AFEX Beneficiaries/Partners should all contain unique names.

When creating a new Beneficiary:

    Currency comes from the selected bank's currency.
    The Beneficiary name is the name of this Partner.
    Template Type will always be 1.
    The Notification Email will be the Partners Email Address.
    Beneficiary Address Details come from this Partner (address line 2 is optional).
    The Bank Name is the name of the Partners Bank Account.
    Bank Account Number is the Partners Bank Account Number.
    Remittance Lines and Other Important Additional Information will come from the Partners Bank 'AFEX Sync Information'.
    (If remittance line 1 is not entered, your company name will be sent).
"""


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    is_afex = fields.Boolean(
        string="AFEX Bank Account", default=False,
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
        copy=False)
    add_afex_info_ids = fields.One2many(
        'afex.additional.sync.fields', 'bank_id',
        string="AFEX Sync Information",
        copy=False)

    _sql_constraints = [
        ('uniq_afex_bank', 'UNIQUE (is_afex,partner_id)',
         'You can only have 1 AFEX bank account per vendor')
    ]

    @api.multi
    def write(self, vals):
        for bank in self:
            if 'currency_id' in vals and bank.partner_id.afex_unique_id:
                raise UserError(
                    _('Cannot change Bank Currency for a Partner who is'
                      ' already syncronised with AFEX'))
        return super(ResPartnerBank, self).write(vals)


class AFEXAddFields(models.Model):
    _name = "afex.additional.sync.fields"

    bank_id = fields.Many2one('res.partner.bank', required=True)
    field = fields.Selection(AFEX_ADD_SYNC_FIELDS, required=True)
    value = fields.Char(required=True)


class ResPartner(models.Model):
    _inherit = "res.partner"

    afex_unique_id = fields.Char(copy=False)
    afex_bank_id = fields.Many2one(
        'res.partner.bank',
        string='AFEX Bank',
        compute='_compute_afex_bank')
    afex_currency_id = fields.Many2one(
        'res.currency',
        string="AFEX Currency",
        compute='_compute_afex_currency')

    @api.multi
    def _compute_afex_bank(self):
        for partner in self:
            bank = partner.bank_ids.filtered(lambda b: b.is_afex)
            partner.afex_bank_id = bank and bank[0] or False

    @api.multi
    def _compute_afex_currency(self):
        for partner in self:
            partner.afex_currency_id = partner.afex_bank_id.currency_id

    @api.multi
    def create_beneficiary_afex(self):
        for partner in self:
            if not partner.name:
                continue
            if not partner.supplier:
                raise UserError(_('AFEX is currently only used for Vendors'))
            if not partner.company_id:
                raise UserError(_('Vendor is not linked to a company'))

            bank = partner.bank_ids.filtered(lambda z: z.is_afex)
            if not bank:
                raise UserError(
                    _('Vendor requires an AFEX Bank Account'))
            if len(bank) > 1:
                raise UserError(
                    _('Vendor can only have one AFEX Bank Account'))

            if not bank.currency_id:
                raise UserError(
                    _('AFEX Bank Account does not contain a Currency'))

            # if no afex id, first see if there is one
            if not partner.afex_unique_id:
                partner.update_beneficiary_afex_id()

            # if partner has afex id or just linked, then send updated details
            if partner.afex_unique_id:
                partner.update_beneficiary_afex()
                continue

            url = "beneficiarycreate"
            data = partner.return_afex_data()
            # create new beneficiary
            response_json = self.env['afex.connector'].afex_response(
                url, data=data, post=True)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error while creating beneficiary: %s %s') %
                    (response_json.get('message', ''),
                     _(PARTNER_AFEX_DESC_TEXT))
                    )

            # currently the vendor ID is passed within the success message.
            # retrieve Vendor ID using get and compare name instead of
            # attempting to cut string.
            partner.update_beneficiary_afex_id()
            # error if we cannot retrieve the details from afex
            if not partner.afex_unique_id:
                raise UserError(
                    _('Error while attempting to retrieve beneficiary'
                      ' details from AFEX'))

    def update_beneficiary_afex(self):
        # update afex with new details
        for partner in self:
            url = "beneficiaryupdate"
            data = partner.return_afex_data()
            data['Vendorid'] = partner.afex_unique_id
            response_json = self.env['afex.connector'].afex_response(
                url, data=data, post=True)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error while updating beneficiary: %s%s') %
                    (response_json.get('message', ''),
                     _(PARTNER_AFEX_DESC_TEXT))
                    )

    def update_beneficiary_afex_id(self):
        # update the partner's afex ID with get from afex
        for partner in self:
            url = "beneficiary"
            response_json = self.env['afex.connector'].afex_response(url)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error while checking existing beneficiaries: %s') %
                    (response_json.get('message', ''),)
                    )
            for item in response_json.get('items', []):
                if item.get('Name', '') == partner.name:
                    partner.afex_unique_id = item.get('VendorId', False)
                    if not partner.afex_unique_id:
                        raise UserError(_("Error with AFEX's Vendor ID"))

    def return_afex_data(self):
        self.ensure_one()

        # data returned for creation and updates
        if not self.afex_bank_id:
            raise ValidationError(
                _('Call to return_afex_data for partner without bank'))
        data = {'Currency': self.afex_currency_id.name or '',
                'BeneficiaryName': self.name or '',
                'TemplateType': 1,
                'NotificationEmail': self.email or '',
                'BeneficiaryAddressLine1': self.street or '',
                'BeneficiaryCity': self.city or '',
                'BeneficiaryCountrycode': self.country_id.code or '',
                'BeneficiaryPostalCode': self.zip or '',
                'BeneficiaryRegion': self.state_id.code or '',
                'BankName': self.afex_bank_id.bank_id.name or '',
                'BankAccountNumber': self.afex_bank_id.acc_number or '',
                'RemittanceLine1': self.company_id.name or '',
                'HighLowValue': '1',  # default as high value
                }

        # optional data - only provided if entered
        if self.street2:
            data['BeneficiaryAddressLine2'] = self.street2
        if self.afex_bank_id.afex_bank_country_id:
            data['BankCountryCode'] = \
                self.afex_bank_id.afex_bank_country_id.code
        if self.afex_bank_id.afex_int_bank_country_id:
            data['IntermediaryBankCountryCode'] = \
                self.afex_bank_id.afex_int_bank_country_id.code
        if self.afex_bank_id.afex_corporate:
            data['Corporate'] = self.afex_bank_id.afex_corporate
        for line in self.afex_bank_id.add_afex_info_ids:
            data[line.field] = line.value
        return data
