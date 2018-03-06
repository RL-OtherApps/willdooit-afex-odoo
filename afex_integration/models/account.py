# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError


RATE_DISPLAY_MESSAGE = \
"""Foreign Exchange Transactions are powered and provided by Associated Foreign Exchange Pty Limited.
Rates provided are indicative, for information purposes only, and are subject to change.
"""

AFEX_TERMS_AND_COND = '''<p>
The foreign exchange transaction service is provided by Associated Foreign Exchange Australia Pty Limited ABN 119 392 586 and AFSL 305246 (trading as "AFEX"). 
Where foreign exchange transaction information is provided on this website, it has been prepared by AFEX without considering the investment objectives, financial situation and particular needs of any person. 
Before acting on any general advice on this website, you should consider its appropriateness to your circumstances. 
To the extent permitted by law, AFEX makes no warranty as to the accuracy or suitability of this information and accepts no responsibility for errors or misstatements, negligent or otherwise. 
Any quotes given are indicative only. The information may be based on assumptions or market conditions and may change without notice. 
No part of the information is to be construed as solicitation to make a financial investment.  
For further details, refer to AFEX's <a target="_blank" href="https://www.afex.com/docs/australia/australian_financial_services_guide.pdf">Financial Services Guide</a>.
</p>
'''


class AccountJournal(models.Model):
    _inherit = "account.journal"

    afex_journal = fields.Boolean(
        string="AFEX Journal", default=False, copy=False)
    afex_api = fields.Char(string="AFEX API", copy=False)
    afex_difference_account_id = fields.Many2one(
        'account.account',
        string="AFEX Difference Account", copy=False)

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
            if journal.type != 'bank':
                raise UserError(_('AFEX Journals must be of type - Bank'))
            if journal.inbound_payment_method_ids:
                raise UserError(
                    _('AFEX Journals must not have any associated Inbound'
                      ' Payment Methods (Debit Methods)'))


class AccountRegisterPayments(models.Model):
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

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        self.afex_check()
        self.create_afex_trade()
        return res

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

            partner_id = payment.invoice_ids.mapped('partner_id')
            if len(partner_id) > 1:
                raise UserError(_('Invoices contain different Vendors'))
            if not partner_id.afex_unique_id:
                raise UserError(_('Partner [%s] has not been synced with AFEX' % (partner_id.name)))
            if not partner_id.afex_currency_id:
                raise UserError(_('Vendor has no AFEX currency id'))

            if any(i.currency_id != partner_id.afex_currency_id
                   for i in payment.invoice_ids):
                raise UserError(
                    _('Invoice currencies must match Vendor AFEX currency'))

    @api.multi
    def refresh_quote(self):
        for payment in self:
            payment.request_afex_quote()
        return {
                "type": "ir.actions.do_nothing",
        }

    @api.multi
    def request_afex_quote(self):
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

            payment.afex_os_curr = payment.invoice_ids[0].currency_id
            to_curr = payment.afex_os_curr.name
            payment.afex_os_amount = sum(
                x.residual for x in payment.invoice_ids)
            currencypair = "%s%s" % (to_curr, payment.currency_id.name)

            url = "valuedates?currencypair=%s" % (currencypair)
            response_json = self.env['afex.connector'].afex_response(
                    url, payment=payment)
            if response_json.get('ERROR', True):
                raise UserError(
                    _('Error with value date: %s') %
                    (response_json.get('message', ''),))
            valuedate = response_json.get('items', fields.Date.today())
            url = "quote?currencypair=%s&valuedate=%s" \
                % (currencypair, valuedate)
            response_json = self.env['afex.connector'].afex_response(
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
            payment_amount = payment.afex_os_amount / payment.afex_rate
            payment.amount = payment_amount

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
            to_curr = payment.invoice_ids[0].currency_id.name
            partner_id = payment.invoice_ids[0].partner_id
            data = {"Amount": payment.afex_os_amount,
                    "TradeCcy": to_curr,
                    "SettlementCcy": payment.currency_id.name,
                    "QuoteId": payment.afex_quote_id,
                    "VendorId": partner_id.afex_unique_id,
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
                        len(payment.journal_id.afex_api) > 8 and
                        self.journal_id.afex_api[0:8] or '',
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
            url = "ssi/GetSSI?Currency=%s" % (inv.afex_ssi_currency,)
            response_json = self.env['afex.connector'].afex_response(url)
            if not response_json.get('ERROR', True):
                instructions = [x['PaymentInstructions']
                                for x in response_json.get('items', [])
                                if x.get('PaymentInstructions')]
                if instructions:
                    inv.afex_ssi_details = '<br/>'.join(instructions)
                    inv.afex_ssi_details = inv.afex_ssi_details.replace(
                        '\r', '<br/>')
            inv.afex_ssi_details = \
                "%s<p>Please remember to include the AFEX Account Number <%s>"\
                " in remittance information.</p>" % \
                (inv.afex_ssi_details or '', inv.afex_ssi_account_number or '')
            inv.afex_ssi_details_display = \
                " ".join(
                    [inv.afex_ssi_details,
                     "<img src='/afex_integration/static/image/"
                     "afex_logo.png'/><br/>",
                     AFEX_TERMS_AND_COND])
