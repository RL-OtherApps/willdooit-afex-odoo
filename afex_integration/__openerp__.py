# -*- coding: utf-8 -*-

{
    "name": "AFEX International Payments",
    "version": "9.0.1.0",
    "summary": "Integration with AFEX Foreign Exchange, by WilldooIT",
    "description": """
Odoo AFEX International Payments
================================

This module allows vendors to be synchronised with AFEX to create AFEX
Beneficiaries. It also allows payments within Odoo to book payments to vendors
through AFEX.

You must have an AFEX account, and request/receive an API Key from AFEX before
this module can be used. AFEX's terms and conditions apply.

AFEX homepage: https://www.afex.com/

NOTE:

    If a Beneficiary is setup within AFEX with the same name as a new Odoo
    partner, then the Odoo AFEX sync will link the Odoo partner to the existing
    AFEX Beneficiary without creating a new one.

    Odoo partners which are synced with AFEX must have unique names.


Setup
-----

- *Accounting > Configuration > Journals*

    A new Cash Journal can be created which will be used for AFEX payments.

    * **Journal Entries**

      - **Default Debit / Credit Account** - G/L account for AFEX clearing.
          Should be set up as a reconcilable liability account for easy
          reconciliation with the bank statement.

      - **Currency** - Leave blank - Journal will use the company currency when
          posting to the General Ledger.

      - **AFEX Journal** - Enabled.

      - **AFEX API Key** - Supplied by AFEX and entered here.

      - **AFEX Difference Account** - Select an account.

    * **Advanced Settings**

      - **Debit Methods** - None should be selected.

      - **Payment Methods** - Enable manual.

- *Partner Screen > Sales and Purchases Tab > Bank Accounts(s)*

    Vendors have an option available against their bank accounts to allow
    each of them them to mark **one** of their bank accounts to be associated
    with AFEX.

    * **AFEX Beneficiary**

- *Partner Screen*

    Partners have an **AFEX Sync** option available in their **Action Drop
    Down** to allow the Partner and their Bank Account to be uploaded to AFEX,
    which will create an **AFEX Beneficiary**.

    * **Action**

      - **AFEX Sync**

    The **AFEX Beneficiary** should be confirmed **by AFEX** before any
    payments are made.

- *Settings > Technical > System Parameters*

    If a URL is not specified in the System Paramaters then a default demo URL
    will be used.

    A different URL may be specified in the System Parameters.

    * **Key** - afex.url

    * **Value** - the URL *(e.g. https://demo.api.afex.com:7890/api/)*


Usage
-----

- *Accounting > Purchases > Vendor Bills > [Open Bill] > Register Payment*

    When a payment is made using an **AFEX Journal** for a vendor who has an
    associated **confirmed AFEX Beneficiary**, the system will retrieve the
    exchange rate from AFEX, update the **payment amount** using the exchange
    rate, and display quote information on the payment screen.

    Each **Payment Quote** is valid for 30 seconds.

    The **Re-Quote** button on the payment screen can be used to refresh the
    quote.

    When the payment is **Validated**, the system will send information to AFEX
    to book a payment with the vendor.

    Information about the booked payment will be displayed on the bill.

    AFEX will require payment within a required time bracket *(which is
    affected by Currency)* in order to make payment to the vendor.

    Upon AFEX receiving payment, the booked payment to the vendor will be
    confirmed for the scheduled time.
""",

    "depends": [
        'account',
    ],
    "author": "WilldooIT",
    "contributors": [
        'Matthew Palmieri',
        'Richard deMeester',
    ],
    'website': 'https://www.willdooit.com',
    "license": "AGPL-3",
    "category": "Accounting & Finance",

    'data': [
        "views/account_view.xml",
        "views/partner_view.xml",
        "security/ir.model.access.csv",
        "data/ir_config_data.xml",
    ],
    'images': [
        'static/description/banner.png',
    ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
    "application": True,
}
