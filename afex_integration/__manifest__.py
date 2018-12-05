# -*- coding: utf-8 -*-

{
    "name": "AFEX Global Vendor Payments for Businesses",
    "version": "10.0.1.4",
    "summary": "Make payments to vendors in a foreign currency using AFEX, "
               "by WilldooIT",
    "description": """
Global Vendor Payments for Businesses
=====================================

This module allows vendor banks to be synchronised with AFEX to create AFEX
Beneficiaries. It also allows payments within Odoo to book payments to vendors
through AFEX.

You must have an AFEX account, and request/receive an API Key from AFEX before
this module can be used. AFEX's terms and conditions apply.

AFEX homepage: https://www.afex.com/

Setup
-----

- *Accounting > Configuration > Settings > Configure your company data >
    General Information Tab* or *Settings > Users > Companies >
    General Information Tab*

    For each Odoo defined company which will trade with AFEX:

      - **AFEX API Key** - Supplied by AFEX and entered here.

- *Accounting > Configuration > Journals*

    A new Cash Journal can be created which will be used for AFEX payments. A
    single journal will suffice if settlement will always be in the local
    currency. If settlement will be made in other currencies, then a journal
    will be required per currency. The settlement currency is the currency
    used to pay AFEX, not the currency used to pay the vendor.

    * **Journal Entries**

      - **Default Debit / Credit Account** - G/L account for AFEX clearing.
          Should be set up as a non reconcilable liability account which is
          reviewed periodically. It could also be a revenue or expense account.
          The balance which accumulates in here will be the difference between
          the Odoo anticipated settlement from stored currency rates, and the
          actual settlement value to AFEX. It may be treated as a straight
          expense, or it may be allocated to other areas of the accounts.

      - **Currency** - Leave blank for settlement in the company currency,
          or enter a currency if settling in another in-between currency. The
          payment will use the currency from here when posting to the clearing
          account defined above.

      - **AFEX Journal** - Enabled.

      - **AFEX Invoicing Partner** - This is the partner to which the liability
          will be posted when making an AFEX trade.

      - **AFEX Fees Account** - Select an account for expensing AFEX fees.

    * **Advanced Settings**

      - **Debit Methods** - None should be selected.

      - **Payment Methods** - Enable manual.

- *Partner > Sales and Purchases Tab > Bank Account(s)*

    Vendors have an option available against their bank accounts to allow
    them to be marked as bank accounts to be associated with AFEX.  There
    should only be one for any currency for a given vendor.

    * **AFEX Beneficiary**

    * **Currency**

    Other values will depend on the beneficiary.  Generally, attempting to sync
    beneficiaries with incomplete information will tell you of missing required
    data, but it varies due to many factors.

    * **AFEX Corporate** - If the beneficiary is not an individual.

    * **AFEX Bank Country**

    * **AFEX Intermediary Bank Country**

    * **AFEX Sync Information** - Various values.

    Other required values are picked up from the partner address area.

- *Partner*

    Partners have an **AFEX Sync** option available in their **Action Drop
    Down** to allow the Partner and their Bank Accounts to be synced to AFEX,
    which will create **AFEX Beneficiaries**.

    * **Action**

      - **AFEX Sync**

    The **AFEX Beneficiary** should be confirmed **by AFEX** before any
    payments are made.

    A general indication of the status is shown  on the *Sales and Purchases*
    Tab.

    * **AFEX Status** - Either *Sync Needed* or *Synchronised*.

- *Settings > Technical > System Parameters*

    The URL defaults to the live URL (https://api.afex.com:7890/api/).  If
    need be, it can be changed in the System Parameters.

    * **Key** - afex.url

    * **Value** - the URL *(e.g. https://demo.api.afex.com:7890/api/)*


Usage
-----

- *Accounting > Purchases > Vendor Bills > [Open Bill] > Register Payment* or
    *Accounting > Purchases > Vendor Bills > [Select Multiple] > [Action Drop
    Down and Register Payment]

    To make a foreign currency payment using an **AFEX Journal** for a vendor
    who has an associated **confirmed AFEX Beneficiary**.  Choose the correct
    payment journal, which will determine the settlement currency. The payment
    amount and currency can be chosen. If part or overpaying a single bill, an
    option will be given to choose if the balance is to be kept open or if
    it is to be written off.

    Retrieving a quote, the system will retrieve the exchange rate from AFEX
    and display the **payment amount** conversion using the exchange rate.
    Quote information is displayed on the payment screen.

    If applicable, the AFEX fee amount(s) and currency will be displayed as
    well.

    Each **Payment Quote** is valid for 30 seconds.

    The **Re-Quote** button on the payment screen can be used to refresh the
    quote.

    When the payment is **Validated**, the system will send information to AFEX
    to book and schedule a payment to the vendor.

    The vendor will be marked as paid to the level selected, and a bill will be
    raised to the AFEX partner. Any fee(s) in the same currency as the
    settlement currency will be included in the same bill. Otherwise, separate
    bill(s) will be raised for the fee(s).

    Information about the booked payment will be displayed on the AFEX bill,
    and on the Odoo payment record.

    To ensure the foreign currency payment can be sent to the vendor on the
    scheduled date, you must remit settlement funding for the payment to AFEX
    within 24 hours of booking the payment.

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
