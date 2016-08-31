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
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice_intercompany::

    >>> Module = Model.get('ir.module')
    >>> account_invoice_module, = Module.find(
    ...     [('name', '=', 'account_invoice_intercompany')])
    >>> account_invoice_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create company user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> company_user = User()
    >>> company_user.name = 'Company User'
    >>> company_user.login = 'company_user'
    >>> company_user.main_company = company
    >>> company_groups = Group.find([])
    >>> company_user.groups.extend(company_groups)
    >>> company_user.save()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> Tax = Model.get('account.tax')
    >>> tax = set_tax_code(create_tax(Decimal('.10'), company=company))
    >>> tax.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create a another company::

    >>> Party = Model.get('party.party')
    >>> Company = Model.get('company.company')
    >>> target_party = Party(name='Dunder Filial')
    >>> target_party.save()
    >>> _ = create_company(target_party)
    >>> target_company, = Company.find([('rec_name', '=', 'Dunder Filial')])
    >>> target_company.parent = company
    >>> target_company.save()

Create company user::

    >>> target_company_user = User()
    >>> target_company_user.name = 'Dunder Filial Company User'
    >>> target_company_user.login = 'target_company_user'
    >>> target_company_user.main_company = target_company
    >>> target_company_groups = Group.find([])
    >>> target_company_user.groups.extend(target_company_groups)
    >>> target_company_user.save()

Reload the context::

    >>> config._context = User.get_preferences(True, config.context)

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

    >>> config.user = target_company_user.id
    >>> Tax = Model.get('account.tax')
    >>> target_tax = Tax()
    >>> rate = Decimal('.10')
    >>> target_tax.name = 'Tax %s' % rate
    >>> target_tax.company = target_company
    >>> target_tax.description = target_tax.name
    >>> target_tax.type = 'percentage'
    >>> target_tax.rate = rate
    >>> target_tax.invoice_account = target_account_tax
    >>> target_tax.credit_note_account = target_account_tax
    >>> target_tax.save()
    >>> target_tax = set_tax_code(target_tax)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = target_company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=target_company)
    >>> with config.set_context(company=target_company.id):
    ...     post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=target_company, prefix='FR')
    >>> with config.set_context(company=target_company.id):
    ...     invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> with config.set_context(company=target_company.id):
    ...     fiscalyear.click('create_period')

Sincronize chart between companies::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> account_template, = AccountTemplate.find([
    ...     ('parent', '=', None),
    ...     ('name', '=', 'Minimal Account Chart'),
    ...     ], limit=1)
    >>> syncronize = Wizard('account.chart.syncronize')
    >>> syncronize.form.account_template = account_template
    >>> syncronize.form.default_companies()
    >>> syncronize.execute('syncronize')

Create product::

    >>> Tax = Model.get('account.tax')
    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.supplier_taxes.append(Tax(tax.id))
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> with config.set_context(company=target_company.id):
    ...     template = ProductTemplate(template.id)
    ...     template.customer_taxes.append(target_tax)
    ...     template.supplier_taxes.append(Tax(target_tax.id))
    ...     template.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Term')
    >>> payment_term_line = PaymentTermLine(type='percent', days=20,
    ...     percentage=Decimal(50))
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term_line = PaymentTermLine(type='remainder', days=40)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = target_party
    >>> invoice.payment_term = payment_term
    >>> invoice.target_company = target_company
    >>> invoice.description = 'Invoice'
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.account = revenue
    >>> line.intercompany_account == expense.template
    True
    >>> line.quantity = 5
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.click('post')
    >>> invoice.reload()
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

Check that the intercompany invoice had been created::


    >>> with config.set_context(company=target_company.id):
    ...      target_invoice, = Invoice.find([('company', '=', target_company.id)])
    ...      target_invoice.type
    u'in'
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.company == target_company
    True
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.state
    u'posted'
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.untaxed_amount, target_invoice.tax_amount
    (Decimal('220.00'), Decimal('22.00'))
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.number, target_invoice.reference
    (u'FR1', u'1')
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.description
    u'Invoice'

Credit the original invoice with refund::

    >>> invoice, = Invoice.find([('company', '=', company.id)])
    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    u'paid'
    >>> with config.set_context(company=target_company.id):
    ...      target_invoice.reload()
    ...      target_invoice.state
    u'paid'
