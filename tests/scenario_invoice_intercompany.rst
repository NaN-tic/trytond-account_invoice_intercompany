=============================
Intercompany Invoice Scenario
=============================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice::

    >>> Module = Model.get('ir.module.module')
    >>> account_invoice_module, = Module.find(
    ...     [('name', '=', 'account_invoice_intercompany')])
    >>> account_invoice_module.click('install')
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> account_tax, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Tax'),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create tax template::

    >>> TaxCode = Model.get('account.tax.code.template')
    >>> TaxTemplate = Model.get('account.tax.template')
    >>> AccountTemplate = Model.get('account.account.template')
    >>> account_tax_template, = AccountTemplate.find([
    ...         ('kind', '=', 'other'),
    ...         ('name', '=', 'Main Tax'),
    ...         ])
    >>> tax = TaxTemplate()
    >>> tax.account = account_template
    >>> tax.name = 'Tax'
    >>> tax.description = 'Tax'
    >>> tax.type = 'percentage'
    >>> tax.rate = Decimal('.10')
    >>> tax.invoice_account = account_tax_template
    >>> tax.credit_note_account = account_tax_template
    >>> invoice_base_code = TaxCode(name='invoice base',
    ...     account=account_template)
    >>> invoice_base_code.save()
    >>> tax.invoice_base_code = invoice_base_code
    >>> invoice_tax_code = TaxCode(name='invoice tax',
    ...     account=account_template)
    >>> invoice_tax_code.save()
    >>> tax.invoice_tax_code = invoice_tax_code
    >>> credit_note_base_code = TaxCode(name='credit note base',
    ...     account=account_template)
    >>> credit_note_base_code.save()
    >>> tax.credit_note_base_code = credit_note_base_code
    >>> credit_note_tax_code = TaxCode(name='credit note tax',
    ...     account=account_template)
    >>> credit_note_tax_code.save()
    >>> tax.credit_note_tax_code = credit_note_tax_code
    >>> tax.save()

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create a another company::

    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> target_company = company_config.form
    >>> target_party = Party(name='Dunder Filial')
    >>> target_party.save()
    >>> target_company.parent = company
    >>> target_company.party = target_party
    >>> target_company.currency = currency
    >>> company_config.execute('add')
    >>> target_company, = Company.find([('rec_name', '=', 'Dunder Filial')])

Create chart for the new company::

    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = target_company
    >>> with config.set_context(company=target_company.id):
    ...     create_chart.execute('create_account')
    >>> target_receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', target_company.id),
    ...         ])
    >>> target_payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', target_company.id),
    ...         ])
    >>> target_revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', target_company.id),
    ...         ])
    >>> target_expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', target_company.id),
    ...         ])
    >>> create_chart.form.account_receivable = target_receivable
    >>> create_chart.form.account_payable = target_payable
    >>> create_chart.execute('create_properties')
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

    >>> syncronize = Wizard('account.chart.syncronize')
    >>> syncronize.execute('syncronize')

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

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
    >>> tax, = Tax.find([
    ...         ('name', '=', 'Tax'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> template.customer_taxes.append(tax)
    >>> template.supplier_taxes.append(Tax(tax.id))
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> with config.set_context(company=target_company.id):
    ...     template = ProductTemplate(template.id)
    ...     tax, = Tax.find([
    ...         ('name', '=', 'Tax'),
    ...         ('company', '=', target_company.id),
    ...         ])
    ...     template.customer_taxes.append(tax)
    ...     template.supplier_taxes.append(Tax(tax.id))
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
