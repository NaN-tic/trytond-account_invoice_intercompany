=============================
Intercompany Invoice Scenario
=============================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install account_invoice_intercompany::

    >>> config = activate_modules('account_invoice_intercompany')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> current_user, = User.find([('login', '=', 'admin')])
    >>> current_user.main_company = company 
    >>> current_user.company = company 
    >>> current_user.save()
    >>> config._context = User.get_preferences(True, config.context)


Create user::

    >>> User = Model.get('res.user')
    >>> company_user = User()
    >>> company_user.name = 'main'
    >>> company_user.login = 'main'
    >>> company_user.main_company = company
    >>> company_user.company = company
    >>> company_user.save()
    >>> company.intercompany_user = company_user
    >>> company.save()


Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Update accounts on target party for company::

    >>> Party = Model.get('party.party')
    >>> target_party = Party(name='Dunder Filial')
    >>> target_party.account_receivable = receivable
    >>> target_party.account_payable = payable
    >>> target_party.save()
    
Create tax::

    >>> tax = create_tax(Decimal('.10'), company=company)
    >>> tax.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Set default values::

    >>> AccountConfig = Model.get('account.configuration')
    >>> account_config = AccountConfig(1)
    >>> account_config.default_product_account_expense = expense
    >>> account_config.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> #template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('25')
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta, = line.relativedeltas
    >>> delta.days = 20
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()


Create a another company::

    >>> _ = create_company(target_party)
    >>> Company = Model.get('company.company')
    >>> target_company, = Company.find([('rec_name', '=', 'Dunder Filial')])
    >>> target_company.parent = company
    >>> target_company.save()

    >>> User = Model.get('res.user')
    >>> target_user = User()
    >>> target_user.name = 'target'
    >>> target_user.login = 'target'
    >>> target_user.main_company = target_company
    >>> target_user.company = target_company
    >>> target_user.save()
    >>> target_company.intercompany_user = target_user
    >>> target_company.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> # invoice.account = receivable
    >>> invoice.party = target_party
    >>> invoice.target_company = target_company
    >>> invoice.payment_term = payment_term
    >>> invoice.description = 'Invoice'
    >>> line = invoice.lines.new()
    >>> line.invoice = invoice
    >>> line.product = product
    >>> # line.account = expense
    >>> # line.intercompany_account = expense.template
    >>> line.quantity = 5
    >>> line.unit_price = Decimal(10)
    >>> line = invoice.lines.new()
    >>> line.invoice = invoice
    >>> line.product = product
    >>> #line.account = expense
    >>> #line.intercompany_account = expense.template
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.save()

Reload the context::

    >>> current_user.main_company = target_company
    >>> current_user.company = target_company
    >>> current_user.save()
    >>> config.context['user'] = current_user
    >>> config.context['company'] = target_company
    >>> config._context = User.get_preferences(True, config.context)
    >>> config.context['company'] =  target_company

Create chart for the new company::

    >>> _ = create_chart(target_company)
    >>> target_accounts = get_accounts(target_company)
    >>> target_receivable = target_accounts['receivable']
    >>> target_payable = target_accounts['payable']
    >>> target_revenue = target_accounts['revenue']
    >>> target_expense = target_accounts['expense']
    >>> target_account_tax = target_accounts['tax']
    >>> target_account_cash = target_accounts['cash']


Create tax for the new company::

    >>> target_tax = create_tax(Decimal('.10'), target_company)

Create fiscal year::

    >>> target_fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(target_company))
    >>> target_fiscalyear.click('create_period')


Update accounts for target_party and main_party::
    
    >>> cp = Party(company.party.id)
    >>> cp.account_receivable = target_receivable
    >>> cp.account_payable = target_payable
    >>> cp.save()
    >>> tp = Party(target_company.party.id)
    >>> tp.account_receivable = target_receivable
    >>> tp.account_payable = target_payable
    >>> tp.save()



Set taxes for target company::

    >>> template = ProductTemplate(template.id)
    >>> template.customer_taxes.append(target_tax)
    >>> #template.supplier_taxes.append(target_tax)
    >>> template.save()

Set User to main company::

    >>> current_user.main_company = company
    >>> current_user.company = company
    >>> current_user.save()
    >>> config.context['company'] = company
    >>> config._context = User.get_preferences(True, config.context)
    >>> config._context['company'] = company



Post Invoice::
    >>> Invoice.post([invoice], config.context)
    >>> invoice.reload()
    True
    >>> invoice.state
    u'posted'
    >>> invoice.untaxed_amount
    Decimal('220.00')
    >>> invoice.tax_amount
    Decimal('22.00')
    >>> invoice.total_amount
    Decimal('242.00')
    >>> invoice.number
    u'1'

Set User to target company::

    >>> current_user.main_company = target_company
    >>> current_user.save()
    >>> config._context = User.get_preferences(True, config.context)

Check that the intercompany invoice had been created::

    >>> target_invoice, = Invoice.find([('company', '=', target_company.id)])
    >>> target_invoice.type
    u'in'
    >>> target_invoice.company == target_company
    True
    >>> target_invoice.state
    u'posted'
    >>> target_invoice.untaxed_amount, target_invoice.tax_amount
    (Decimal('220.00'), Decimal('22.00'))
    >>> target_invoice.number, target_invoice.reference
    (u'FR1', u'1')
    >>> target_invoice.description
    u'Invoice'

Set User to main company::

    >>> current_user.main_company = company
    >>> current_user.save()
    >>> config._context = User.get_preferences(True, config.context)


Credit the original invoice with refund::

    >>> invoice, = Invoice.find([('company', '=', company.id)])
    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    u'paid'

Set User to target company::

    >>> current_user.main_company = target_company
    >>> current_user.save()
    >>> config._context = User.get_preferences(True, config.context)

    >>> target_invoice.reload()
    >>> target_invoice.state
    u'paid'
