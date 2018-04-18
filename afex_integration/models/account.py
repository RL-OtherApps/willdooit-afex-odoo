# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError


RATE_DISPLAY_MESSAGE = '''
Foreign Exchange Transactions are powered and provided by Associated Foreign
Exchange Pty Limited. Rates provided are indicative, for information purposes
only, and are subject to change.
'''

AFEX_TERMS_AND_COND = '''
<p>
The foreign exchange transaction service is provided by Associated Foreign
Exchange Australia Pty Limited ABN 119 392 586 and AFSL 305246 (trading as
"AFEX"). Where foreign exchange transaction information is provided on this
website, it has been prepared by AFEX without considering the investment
objectives, financial situation and particular needs of any person. Before
acting on any general advice on this website, you should consider its
appropriateness to your circumstances. To the extent permitted by law, AFEX
makes no warranty as to the accuracy or suitability of this information and
accepts no responsibility for errors or misstatements, negligent or otherwise.
Any quotes given are indicative only. The information may be based on
assumptions or market conditions and may change without notice. No part of the
information is to be construed as solicitation to make a financial investment.
For further details, refer to AFEX's
<a target="_blank" href="https://www.afex.com/docs/australia/australian_financial_services_guide.pdf">Financial Services Guide</a>.
</p>
'''


class AccountJournal(models.Model):
    _inherit = "account.journal"

    afex_journal = fields.Boolean(
        string='AFEX Journal', default=False, copy=False)
    afex_partner_id = fields.Many2one(
        'res.partner',
        string="AFEX Invoicing Partner",
        copy=False)
    afex_fee_account_id = fields.Many2one(
        'account.account',
        string="AFEX Fees Expense Account",
        domain=[('deprecated', '=', False)],
        copy=False)

    @api.model
    def create(self, vals):
        res = super(AccountJournal, self).create(vals)
        res.afex()
        return res

    @api.multi
    def write(self, vals):
        res = super(AccountJournal, self).write(vals)
        self.afex()
        return res

    @api.multi
    def afex(self):
        for journal in self.filtered(lambda j: j.afex_journal):
            if journal.type != 'cash':
                raise UserError(_('AFEX Journals must be of type - Cash'))
            if journal.inbound_payment_method_ids:
                raise UserError(
                    _('AFEX Journals must not have any associated Inbound'
                      ' Payment Methods (Debit Methods)'))


class AccountAbstractPayment(models.AbstractModel):
    _inherit = "account.abstract.payment"

# Cannot be done like this in v9
#     is_afex = fields.Boolean(
#         related=['journal_id', 'afex_journal'], readonly=True)
#     afex_quote_id = fields.Integer(copy=False)
#     afex_trade_no = fields.Char(string="AFEX Trade#", copy=False)
#     afex_rate = fields.Float()
#     afex_rate_display = fields.Html(
#         string="AFEX Rate", compute="_afex_rate_display")
#
#     afex_stl_currency_id = fields.Many2one('res.currency')
#     afex_stl_amount = fields.Monetary(
#         string='Settlement Amount', currency_field='afex_stl_currency_id'
#         )
#
#     afex_fee_amount = fields.Monetary(
#         string='AFEX Fee Amount', currency_field='afex_fee_currency_id')
#     afex_fee_currency_id = fields.Many2one(
#         'res.currency', string='Fee Currency')

    @api.multi
    def _afex_rate_display(self, obj):
        for payment in obj:
            if payment.afex_quote_id and payment.afex_rate:
                payment.afex_rate_display = \
                    '<p>Exchange Rate: %s to %s: %s</p>' \
                    '<p>%s</p>' %\
                    (payment.afex_stl_currency_id.name,
                     payment.currency_id.name,
                     payment.afex_rate,
                     RATE_DISPLAY_MESSAGE,
                     )
            else:
                payment.afex_rate_display = ''

    @api.multi
    def request_afex_quote(self, obj):
        payment = obj
        payment.ensure_one()

        Connector = self.env['afex.connector']
        if payment.is_afex:
            afex_quote_id = False
            afex_rate = False

            stl_currency = payment.journal_id.currency_id or \
                payment.company_id.currency_id
            currencypair = "%s%s" % (
                payment.currency_id.name, stl_currency.name)

            url = "valuedates?currencypair=%s" % (currencypair)
            response_json = Connector.afex_response(
                    url, payment=payment)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error with value date: %s') %
                    (response_json.get('message', ''),))
            valuedate = response_json.get('items', fields.Date.today())

            url = "quote?currencypair=%s&valuedate=%s" \
                % (currencypair, valuedate)
            response_json = Connector.afex_response(
                url, payment=payment)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error with quote: %s') %
                    (response_json.get('message', ''),))
            for item in response_json:
                if item == 'QuoteId':
                    afex_quote_id = response_json[item]
                if item == 'Rate':
                    afex_rate = response_json[item]
            if not afex_quote_id or not afex_rate:
                raise UserError(_('Could not retrieve a valid AFEX quote'))
            payment_amount = payment.amount / afex_rate

            url = "fees"
            afex_bank = payment.partner_id.afex_bank_for_currency(
                payment.currency_id)
            data = {"Amount": payment.amount,
                    "AccountNumber": "",
                    "SettlementCcy": stl_currency.name,
                    "TradeCcy": payment.currency_id.name,
                    "VendorId": afex_bank.afex_unique_id,
                    "ValueDate": valuedate,
                    }
            response_json = Connector.afex_response(
                url, data=data, payment=payment, post=True)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error while retrieving AFEX Fees: %s') %
                    (response_json.get('message', ''),))
            # Grab and use first fee - Multiple fees not sent at this time.
            fee_details = response_json.get('items', [{}])[0]
            fee_amount = fee_details.get('Amount')
            afex_fee_currency = \
                self.env['res.currency'].search(
                    [('name', '=', fee_details.get('Currency', ''))],
                    limit=1)

            payment.write(
                {'afex_quote_id': afex_quote_id,
                 'afex_rate': afex_rate,
                 'afex_stl_currency_id': stl_currency.id,
                 'afex_stl_amount': payment_amount,
                 'afex_fee_amount': fee_amount,
                 'afex_fee_currency_id': afex_fee_currency.id,
                 }
                )

    @api.multi
    def afex_check(self, obj):
        for payment in obj.filtered(lambda p: p.is_afex):
            afex_bank = payment.partner_id.afex_bank_for_currency(
                payment.currency_id)

            if not afex_bank.afex_unique_id:
                raise UserError(
                    _('Partner [%s] currency [%s] has not been synced with '
                      'AFEX') % (payment.partner_id.name,
                                 payment.currency_id.name))


class AccountRegisterPayments(models.TransientModel):
    _inherit = "account.register.payments"

    # Defined here for v9
    # ==============================================================
    is_afex = fields.Boolean(
        related=['journal_id', 'afex_journal'], readonly=True)
    afex_quote_id = fields.Integer(copy=False)
    afex_trade_no = fields.Char(string="AFEX Trade#", copy=False)
    afex_rate = fields.Float()
    afex_rate_display = fields.Html(
        string="AFEX Rate", compute="_afex_rate_display")

    afex_stl_currency_id = fields.Many2one('res.currency')
    afex_stl_amount = fields.Monetary(
        string='Settlement Amount', currency_field='afex_stl_currency_id')

    afex_fee_amount = fields.Monetary(
        string='AFEX Fee Amount', currency_field='afex_fee_currency_id')
    afex_fee_currency_id = fields.Many2one(
        'res.currency', string='Fee Currency')

    @api.multi
    def _afex_rate_display(self):
        return self.env['account.abstract.payment']._afex_rate_display(self)

    @api.multi
    def request_afex_quote(self):
        return self.env['account.abstract.payment'].request_afex_quote(self)
    # Defined here for v9
    # ==============================================================

    @api.onchange('amount', 'currency_id', 'journal_id')
    def _onchange_afex(self):
        self.afex_quote_id = False

    @api.multi
    def refresh_quote(self):
        for payment in self:
            self.env['account.abstract.payment'].afex_check(self)
            payment.request_afex_quote()

        return {
                "type": "ir.actions.do_nothing",
        }

    def get_payment_vals(self):
        result = super(AccountRegisterPayments, self).get_payment_vals()
        result.update({
            'afex_quote_id': self.afex_quote_id,
            'afex_rate': self.afex_rate,
            'afex_stl_currency_id': self.afex_stl_currency_id.id,
            'afex_stl_amount': self.afex_stl_amount,
            'afex_fee_amount': self.afex_fee_amount,
            'afex_fee_currency_id': self.afex_fee_currency_id.id,
            })
        return result


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Defined here for v9
    # ==============================================================
    is_afex = fields.Boolean(
        related=['journal_id', 'afex_journal'], readonly=True)
    afex_quote_id = fields.Integer(copy=False)
    afex_trade_no = fields.Char(string="AFEX Trade#", copy=False)
    afex_rate = fields.Float()
    afex_rate_display = fields.Html(
        string="AFEX Rate", compute="_afex_rate_display")

    afex_stl_currency_id = fields.Many2one('res.currency')
    afex_stl_amount = fields.Monetary(
        string='Settlement Amount', currency_field='afex_stl_currency_id'
        )

    afex_fee_amount = fields.Monetary(
        string='AFEX Fee Amount', currency_field='afex_fee_currency_id')
    afex_fee_currency_id = fields.Many2one(
        'res.currency', string='Fee Currency')

    @api.multi
    def _afex_rate_display(self):
        return self.env['account.abstract.payment']._afex_rate_display(self)

    @api.multi
    def request_afex_quote(self):
        return self.env['account.abstract.payment'].request_afex_quote(self)
    # Defined here for v9
    # ==============================================================

    afex_invoice_id = fields.Many2one(
        'account.invoice',
        string='AFEX Invoice', readonly=True)
    afex_fee_invoice_id = fields.Many2one(
        'account.invoice',
        string='AFEX Fee Invoice', readonly=True)

    afex_ssi_account_number = fields.Char(copy=False)
    afex_ssi_details = fields.Html(copy=False)
    afex_ssi_details_display = fields.Html(
        compute="afex_ssi", string="SSI Details")

    @api.onchange('amount', 'currency_id', 'journal_id')
    def _onchange_afex(self):
        self.afex_quote_id = False

    @api.multi
    def refresh_quote(self):
        for payment in self:
            self.env['account.abstract.payment'].afex_check(self)
            payment.request_afex_quote()

        return {
                "type": "ir.actions.do_nothing",
        }

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        self.env['account.abstract.payment'].afex_check(self)
        self.create_afex_trade()
        return res

    def create_afex_trade(self):
        for payment in self.filtered(lambda p: p.is_afex):

            inv_head = self.env['account.invoice'].with_context(
                type='in_invoice').create(
                {'partner_id': payment.journal_id.afex_partner_id.id,
                 'user_id': self.env.user.id,
                 'company_id': payment.company_id.id,
                 'currency_id': payment.afex_stl_currency_id.id,
                 })
            inv_head._onchange_partner_id()
            inv_head._onchange_payment_term_date_invoice()
            self.env['account.invoice.line'].create(
                {'invoice_id': inv_head.id,
                 'account_id': payment.journal_id.default_debit_account_id.id,
                 'name': 'AFEX Settlement',
                 'price_unit': payment.afex_stl_amount,
                 'quantity': 1,
                 })

            inv_fee = False
            if payment.afex_fee_amount:
                if payment.afex_fee_currency_id != \
                        payment.afex_stl_currency_id:
                    inv_fee = self.env['account.invoice'].with_context(
                        type='in_invoice').create(
                        {'partner_id': payment.journal_id.afex_partner_id.id,
                         'user_id': self.env.user.id,
                         'company_id': payment.company_id.id,
                         'currency_id': payment.afex_fee_currency_id.id,
                         })
                    inv_fee._onchange_partner_id()
                    inv_fee._onchange_payment_term_date_invoice()
                self.env['account.invoice.line'].create(
                    {'invoice_id': inv_fee and inv_fee.id or inv_head.id,
                     'account_id': payment.journal_id.afex_fee_account_id.id,
                     'name': 'AFEX Transaction Fee',
                     'price_unit': payment.afex_fee_amount,
                     'quantity': 1,
                     })

            if not payment.afex_rate or \
                    not payment.afex_quote_id or \
                    payment.afex_quote_id < 1:
                raise UserError(
                    _('Invalid AFEX Quote - Please re-quote before attempting'
                      ' payment.'))
            url = "trades/create"
            afex_bank = payment.partner_id.afex_bank_for_currency(
                payment.currency_id)
            data = {"Amount": payment.amount,
                    "TradeCcy": payment.currency_id.name,
                    "SettlementCcy": payment.afex_stl_currency_id.name,
                    "QuoteId": payment.afex_quote_id,
                    "VendorId": afex_bank.afex_unique_id,
                    "PurposeOfPayment": payment.communication,
                    }
            response_json = self.env['afex.connector'].afex_response(
                url, data=data, payment=payment, post=True)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error while creating AFEX Trade: %s') %
                    (response_json.get('message', ''),))
            trade_number = response_json.get('TradeNumber', False)
            if trade_number:
                payment.afex_trade_no = trade_number
                payment.afex_ssi_account_number = \
                    len(payment.company_id.afex_api_key) > 8 and \
                    payment.company_id.afex_api_key[0:8] or ''

                ssi_details = ''
                url = "ssi/GetSSI?Currency=%s" % (
                    payment.afex_stl_currency_id.name,)
                response_json = self.env['afex.connector'].afex_response(url)
                if not response_json.get('ERROR', True):
                    instructions = [x['PaymentInstructions']
                                    for x in response_json.get('items', [])
                                    if x.get('PaymentInstructions')]
                    if instructions:
                        ssi_details = '<br/>'.join(instructions).replace(
                            '\r', '<br/>')
                    payment.afex_ssi_details = \
                        "%s<p>Please remember to include the AFEX Account"\
                        " Number <%s> in remittance information.</p>" % \
                        (ssi_details or '',
                         payment.afex_ssi_account_number or '')

                inv_head.reference = 'AFEX-%s' % (trade_number,)
                if inv_fee:
                    inv_fee.reference = 'AFEX Fee-%s' % (trade_number,)

            inv_head.signal_workflow('invoice_open')
            payment.afex_invoice_id = inv_head
            if inv_fee:
                inv_fee.signal_workflow('invoice_open')
                payment.afex_fee_invoice_id = inv_fee

    def afex_ssi(self):
        for payment in self:
            if not payment.afex_ssi_details:
                payment.afex_ssi_details_display = False
            else:
                payment_amounts = '<br/>'
                payment_amounts = '%s<p>Payment Amount (%s): %.2f</p>' %\
                    (payment_amounts,
                     payment.currency_id.name,
                     payment.amount,
                     )
                payment_amounts = '%s<p>Settlement Amount (%s): %.2f</p>' %\
                    (payment_amounts,
                     payment.afex_stl_currency_id.name,
                     payment.afex_stl_amount,
                     )
                if payment.afex_fee_amount:
                    payment_amounts = '%s<p>Fee Amount (%s): %.2f</p>' %\
                        (payment_amounts,
                         payment.afex_fee_currency_id.name,
                         payment.afex_fee_amount,
                         )
                payment.afex_ssi_details_display = \
                    " ".join(
                        [payment_amounts,
                         payment.afex_ssi_details,
                         "<img src='/afex_integration/static/image/"
                         "afex_logo.png'/><br/>",
                         AFEX_TERMS_AND_COND])


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    afex_source_ids = fields.One2many(
        'account.payment', 'afex_invoice_id',
        string='AFEX Source',
        readonly=True)
    is_afex = fields.Boolean(
        related=['afex_source_ids',
                 'is_afex'],
        readonly=True)
    afex_ssi_details_display = fields.Html(
        related=['afex_source_ids',
                 'afex_ssi_details_display'],
        string="SSI Details", readonly=True)
