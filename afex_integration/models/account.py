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
    afex_api_key = fields.Char(
        string='AFEX API Key', copy=False,
        oldname='afex_api')
    afex_difference_account_id = fields.Many2one(
        'account.account',
        string="AFEX Difference Account", copy=False)
    afex_fee_account_id = fields.Many2one(
        'account.account',
        string="AFEX Fees Expense Account", copy=False)

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


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Due to the lack of programming hooks in register payment, we use the
    # context as a work around....
    @api.multi
    def post(self):
        if self.env.context.get('additional_line_data'):
            self.ensure_one()
            self.write(
                {'line_ids': [(0, 0, l) for l in
                              self.env.context['additional_line_data']]
                 })
        return super(AccountMove, self).post()


class AccountRegisterPayments(models.TransientModel):
    _inherit = 'account.register.payments'

    @api.multi
    def create_payment(self):
        for payment in self:
            if payment.journal_id.afex_journal:
                raise UserError(
                    _('AFEX Journals cannot be used for Multi Payments'))
        return super(AccountRegisterPayments, self).create_payment()


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_afex = fields.Boolean(
        related=['journal_id', 'afex_journal'], readonly=True)
    afex_rate = fields.Float(copy=False)
    afex_rate_display = fields.Html(
        string="AFEX Rate", compute="_afex_rate_display")
    afex_quote_id = fields.Integer(copy=False)
    afex_os_curr = fields.Many2one('res.currency', copy=False)
    afex_os_amount = fields.Float(copy=False)
    afex_trade_no = fields.Char(string="AFEX Trade#", copy=False)
    afex_fee_account_id = fields.Many2one(
        'account.account',
        string="AFEX Fees Account", copy=False)
    afex_fee_amount = fields.Monetary(
        string='AFEX Fee Amount', currency_field='afex_fee_currency_id')
    afex_fee_currency_id = fields.Many2one(
        'res.currency', string='Fee Currency')

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        self.afex_check()
        self.create_afex_trade()
        return res

    def _create_payment_entry(self, amount):
        if self.afex_fee_amount and self.afex_fee_currency_id == self.currency_id:
            #
            # we want to use the super routine
            # pass som extra data to the only place where
            # we can hook in!
            #
            additional_line_data = []

            # Code purloined from base _create_payment_entry
            # ===============================================================================================
            aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
            invoice_currency = False
            debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(self.afex_fee_amount, self.currency_id, self.company_id.currency_id, invoice_currency)

            counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, 0, False, False)
            counterpart_aml_dict.update({
                'name': 'AFEX Fee',
                'account_id': self.afex_fee_account_id.id,
                'journal_id': self.journal_id.id,
                'currency_id': False,
                'payment_id': self.id,
                })
            additional_line_data.append(counterpart_aml_dict)

            #Write counterpart lines
            liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, 0, False, False)
            liquidity_aml_dict.update({
                'name': 'AFEX Fee',
                'account_id': self.payment_type in ('outbound','transfer') and self.journal_id.default_debit_account_id.id or self.journal_id.default_credit_account_id.id,
                'journal_id': self.journal_id.id,
                'currency_id': False,
                'payment_id': self.id,
                })
            additional_line_data.append(liquidity_aml_dict)
            # ===============================================================================================

            ctx = {'additional_line_data': additional_line_data}
        else:
            ctx = {}
        return super(AccountPayment, self.with_context(ctx))._create_payment_entry(amount)

    @api.multi
    @api.depends('is_afex', 'currency_id', 'afex_quote_id', 'afex_rate')
    def _afex_rate_display(self):
        for payment in self:
            if payment.is_afex and payment.afex_quote_id and payment.afex_rate:
                disp_rate = "%s" % payment.afex_rate
                payment.afex_rate_display = \
                    "<p>Exchange Rate: %s to %s: %s</p><p>%s</p>" %\
                    (payment.currency_id.name,
                     payment.afex_os_curr.name,
                     disp_rate,
                     RATE_DISPLAY_MESSAGE,
                     )
            else:
                payment.afex_rate_display = ''

    @api.multi
    def afex_check(self):
        for payment in self.filtered(lambda p: p.is_afex):
            if not payment.invoice_ids:
                raise UserError(_('No associated Invoices'))

            partner = payment.invoice_ids.mapped('partner_id')
            if len(partner) > 1:
                raise UserError(_('Invoices contain different Vendors'))

            currency = payment.invoice_ids.mapped('currency_id')
            if len(currency) > 1:
                raise UserError(_('Invoices contain different Currencies'))

            afex_bank = partner.afex_bank_for_currency(currency)
            if not afex_bank.afex_unique_id:
                raise UserError(
                    _('Partner [%s] currency [%s] has not been synced with '
                      'AFEX') % (partner.name, currency.name))

            if any(i.currency_id != afex_bank.currency_id
                   for i in payment.invoice_ids):
                raise UserError(
                    _('Invoice currencies must match Vendor AFEX currency'))

            if payment.afex_fee_amount and not payment.afex_fee_currency_id:
                raise UserError(
                    _('AFEX fee currency error'))

            if payment.afex_fee_amount and not payment.afex_fee_account_id:
                raise UserError(
                    _('No account provided for AFEX fees'))

    @api.multi
    def refresh_quote(self):
        for payment in self:
            payment.request_afex_quote()
        return {
                "type": "ir.actions.do_nothing",
        }

    @api.multi
    def request_afex_quote(self):
        Connector = self.env['afex.connector']
        for payment in self:
            payment.afex_quote_id = 0
            if not payment.is_afex:
                continue
            if not payment.invoice_ids:
                continue

            payment.afex_check()
            payment.payment_difference_handling = 'reconcile'
            payment.writeoff_account_id = \
                payment.journal_id.afex_difference_account_id
            payment.afex_fee_account_id = \
                payment.journal_id.afex_fee_account_id

            payment.afex_os_curr = payment.invoice_ids[0].currency_id
            to_curr = payment.afex_os_curr.name
            payment.afex_os_amount = sum(
                x.residual for x in payment.invoice_ids)
            currencypair = "%s%s" % (to_curr, payment.currency_id.name)

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
                    payment.afex_quote_id = response_json[item]
                if item == 'Rate':
                    payment.afex_rate = response_json[item]
            if not payment.afex_quote_id or not payment.afex_rate:
                raise UserError(_('Could not retrieve an AFEX quote'))
            payment.amount = payment.afex_os_amount / payment.afex_rate

            url = "fees"
            partner = payment.invoice_ids[0].partner_id
            afex_bank = partner.afex_bank_for_currency(payment.afex_os_curr)
            data = {"Amount": payment.afex_os_amount,
                    "AccountNumber": "",
                    "SettlementCcy": payment.currency_id.name,
                    "TradeCcy": payment.afex_os_curr.name,
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
            payment.afex_fee_amount = fee_details.get('Amount')
            payment.afex_fee_currency_id = \
                self.env['res.currency'].search(
                    [('name', '=', fee_details.get('Currency', ''))],
                    limit=1)

    def create_afex_trade(self):
        for payment in self.filtered(lambda p: p.is_afex):
            if not payment.afex_rate_display or \
                    not payment.afex_quote_id or \
                    payment.afex_quote_id < 1:
                raise UserError(
                    _('Invalid AFEX Quote - Please re-quote before attempting'
                      ' payment.'))
            payment.afex_check()
            url = "trades/create"
            currency = payment.invoice_ids[0].currency_id
            partner = payment.invoice_ids[0].partner_id
            afex_bank = partner.afex_bank_for_currency(currency)
            data = {"Amount": payment.afex_os_amount,
                    "TradeCcy": currency.name,
                    "SettlementCcy": payment.currency_id.name,
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
                payment.invoice_ids.write({
                    'afex_ssi_currency': payment.currency_id.name,
                    'afex_ssi_account_number':
                        len(payment.journal_id.afex_api_key) > 8 and
                        self.journal_id.afex_api_key[0:8] or '',
                    })


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    afex_ssi_currency = fields.Char(copy=False)
    afex_ssi_account_number = fields.Char(copy=False)
    afex_ssi_details = fields.Html(copy=False)
    afex_ssi_details_display = fields.Html(
        compute="update_afex_ssi", string="SSI Details")

    @api.depends('afex_ssi_currency')
    def update_afex_ssi(self):
        for inv in self:
            if not inv.afex_ssi_currency:
                continue

            ssi_details = ''
            url = "ssi/GetSSI?Currency=%s" % (inv.afex_ssi_currency,)
            response_json = self.env['afex.connector'].afex_response(url)
            if not response_json.get('ERROR', True):
                instructions = [x['PaymentInstructions']
                                for x in response_json.get('items', [])
                                if x.get('PaymentInstructions')]
                if instructions:
                    ssi_details = '<br/>'.join(instructions).replace(
                        '\r', '<br/>')

            payment_amounts = '<br/>'
            for payment in self.payment_ids.filtered(lambda p: p.is_afex):
                payment_amounts = '%s<p>Payment Amount (%s): %.2f</p>' %\
                    (payment_amounts,
                     payment.currency_id.name,
                     payment.amount,
                     )
                if payment.afex_fee_amount:
                    payment_amounts = '%s<p>Fee Amount (%s): %.2f</p>' %\
                        (payment_amounts,
                         payment.afex_fee_currency_id.name,
                         payment.afex_fee_amount,
                         )

            inv.afex_ssi_details = \
                "%s<p>Please remember to include the AFEX Account Number <%s>"\
                " in remittance information.</p>" % \
                (ssi_details or '', inv.afex_ssi_account_number or '')
            inv.afex_ssi_details_display = \
                " ".join(
                    [payment_amounts,
                     inv.afex_ssi_details,
                     "<img src='/afex_integration/static/image/"
                     "afex_logo.png'/><br/>",
                     AFEX_TERMS_AND_COND])
