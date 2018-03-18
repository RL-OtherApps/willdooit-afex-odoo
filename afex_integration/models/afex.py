# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError
import requests
import json


class AFEX(models.TransientModel):
    _name = 'afex.connector'

    def afex_response(self, para_url,
                      payment=False, head=False, data=False, post=False):
        base_web = self.env['ir.config_parameter'].get_param('afex.url') \
            or "https://demo.api.afex.com:7890/api/"
        if base_web[-1:] != '/':
            base_web += '/'
        url = "%s%s" % (base_web, para_url)
        if payment:
            key = payment.journal_id.afex_api_key
        else:
            journal = self.env['account.journal'].search(
                [('afex_journal', '=', True)], limit=1)
            if not journal:
                raise UserError(_('No AFEX Account Journals Exist.'))
            key = journal.afex_api_key
        headers = {'API-key': key,
                   'Content-Type': 'application/json'
                   }
        if head:
            headers.update(head)
        if post:
            response = requests.post(
                url, headers=headers, data=json.dumps(data or {}))
        else:
            response = requests.get(url, headers=headers)
        ok = response.ok
        try:
            to_ret = response.json()
        except:
            to_ret = ''
        if ok and para_url == 'beneficiarycreate':
            ok = False
            if isinstance(to_ret, list):
                ok = all(i.get('Code', 1) == 0 for i in to_ret)
        if not ok:
            if isinstance(to_ret, list):
                to_ret = '\n\n' +\
                        '\n'.join(x.get('Name') or '' for x in to_ret
                                  if x.get('Code') != 0)
            return {
                "ERROR": True,
                "code": response,
                "message": to_ret
                }

        if not isinstance(to_ret, dict):
            to_ret = {'items': to_ret}
        to_ret['ERROR'] = False
        return to_ret
