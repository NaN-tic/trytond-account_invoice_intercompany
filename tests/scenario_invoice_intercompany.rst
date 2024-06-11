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
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install account_invoice_intercompany::

    >>> config = activate_modules('account_invoice_intercompany')
    >>> Party = Model.get('party.party')
    >>> Company = Model.get('company.company')
    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')

    >>> admin, = User.find([('login', '=', 'admin')], limit=1)
    >>> account_group, = Group.find([('name', '=', 'Account')])

Create companies::

    >>> party1 = Party(name='Company1')
    >>> party1.save()
    >>> party2 = Party(name='Company2')
    >>> party2.save()
    >>> _ = create_company(party=party1)
    >>> _ = create_company(party=party2)
    >>> company1, company2 = Company.find([])
    >>> admin.companies.append(Company(company2.id))
    >>> admin.save()

Create chart of accounts::

    >>> _ = create_chart(company1)
    >>> accounts = get_accounts(company1)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> tax_customer = create_tax(Decimal('.10'), company=company1)
    >>> tax_customer.save()
    >>> tax_supplier = create_tax(Decimal('.10'), company=company1)
    >>> tax_supplier.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company1))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax_customer)
    >>> account_category.supplier_taxes.append(tax_supplier)
    >>> account_category.save()

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
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('25')
    >>> product.save()

Create company1 user::

    >>> company_user = User(companies=[company1, company2])
    >>> company_user.name = 'company1'
    >>> company_user.login = 'company1'
    >>> company_user.company = company1
    >>> company_user.groups.append(account_group)
    >>> company_user.save()
    >>> company1.intercompany_user = company_user
    >>> company1.save()

Create company2 user::

    >>> target_user_id, = User.copy([company_user], {'name': 'company2', 'login': 'company2', 'company': company2}, config.context)
    >>> target_user = User(target_user_id)
    >>> company2.intercompany_user = target_user
    >>> company2.save()

Create chart of accounts::

    >>> admin.company = company2
    >>> admin.save()
    >>> admin = User(1)
    >>> set_user(admin)
    >>> config._context = User.get_preferences(True, config.context)

    >>> _ = create_chart(company2)
    >>> accounts = get_accounts(company2)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

    >>> tax_customer2 = create_tax(Decimal('.20'), company=company2)
    >>> tax_customer2.save()
    >>> tax_supplier2 = create_tax(Decimal('.20'), company=company2)
    >>> tax_supplier2.save()
    >>> tax_customer3 = create_tax(Decimal('.0'), company=company2)
    >>> tax_customer3.save()
    >>> tax_supplier3 = create_tax(Decimal('.0'), company=company2)
    >>> tax_supplier3.save()

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company2))
    >>> fiscalyear.click('create_period')

    >>> account_category = ProductCategory(account_category.id)
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax_customer2)
    >>> account_category.supplier_taxes.append(tax_supplier2)
    >>> account_category.save()

Create invoice::

    >>> set_user(company_user)
    >>> config._context = User.get_preferences(True, config.context)

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party2
    >>> invoice.target_company = company2
    >>> invoice.description = 'Invoice'
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal(10)
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.save()

Post Invoice::

    >>> Invoice.post([invoice], config.context)
    >>> invoice.reload()
    >>> invoice.company == company1
    True
    >>> invoice.state == 'posted'
    True
    >>> invoice.untaxed_amount == Decimal('70.00')
    True
    >>> invoice.tax_amount == Decimal('7.00')
    True
    >>> invoice.total_amount == Decimal('77.00')
    True
    >>> invoice.number == '1'
    True
    >>> len(invoice.taxes) == 1
    True
    >>> [t.rec_name for t in invoice.taxes] == ['Tax 0.10']
    True

Check company2 supplier invoice::

    >>> set_user(target_user)
    >>> config._context = User.get_preferences(True, config.context)

    >>> invoice2, = Invoice.find([])
    >>> invoice2.reference == '1'
    True
    >>> invoice2.company == company2
    True
    >>> invoice2.type == 'in'
    True
    >>> invoice2.party == party1
    True
    >>> invoice2.state == 'posted'
    True
    >>> invoice.untaxed_amount == Decimal('70.00')
    True
    >>> len(invoice2.taxes) == 1
    True
    >>> [t.rec_name for t in invoice2.taxes] == ['Tax 0.20']
    True

Account Tax rule::

    >>> set_user(admin)
    >>> config._context = User.get_preferences(True, config.context)

    >>> TaxRule = Model.get('account.tax.rule')
    >>> tax_rule = TaxRule()
    >>> tax_rule.name = 'Tax Rule'
    >>> tax_rule.kind = 'both'
    >>> line = tax_rule.lines.new()
    >>> line.origin_tax = tax_supplier2
    >>> line.tax = tax_supplier3
    >>> tax_rule.save()

Set Party Tax Rule in party company1::

    >>> party1 = Party(party1.id)
    >>> party1.supplier_tax_rule = tax_rule
    >>> party1.save()
    >>> party2 = Party(party2.id)
    >>> party2.supplier_tax_rule = tax_rule
    >>> party2.save()

Create new invoice and post::

    >>> set_user(company_user)
    >>> config._context = User.get_preferences(True, config.context)

    >>> invoice = Invoice()
    >>> invoice.party = party2
    >>> invoice.target_company = company2
    >>> invoice.description = 'Invoice'
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal(10)
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.save()

    >>> Invoice.post([invoice], config.context)
    >>> invoice.reload()
    >>> invoice.company == company1
    True
    >>> invoice.state == 'posted'
    True
    >>> len(invoice.taxes) == 1
    True
    >>> [t.rec_name for t in invoice.taxes] == ['Tax 0.10']
    True

Check company2 supplier new invoice::

    >>> set_user(target_user)
    >>> config._context = User.get_preferences(True, config.context)

    >>> invoice3, _ = Invoice.find([])
    >>> invoice3.reference == '2'
    True
    >>> invoice3.company == company2
    True
    >>> invoice3.type == 'in'
    True
    >>> invoice3.party == party1
    True
    >>> invoice3.state == 'posted'
    True
    >>> invoice3.untaxed_amount == Decimal('70.00')
    True
    >>> len(invoice3.taxes) == 1
    True
    >>> [t.rec_name for t in invoice3.taxes] == ['Tax 0.0']
    True
