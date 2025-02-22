# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from collections import defaultdict
from trytond.model import fields, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Equal, Eval, If, Bool
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    _intercompany_excluded_fields = ['id', 'company', 'party', 'lines', 'line_lines',
        'account', 'type', 'state', 'create_date', 'create_uid', 'write_date',
        'write_uid', 'target_company', 'taxes', 'invoice_report_cache',
        'invoice_report_format', 'move', 'additional_moves', 'cancel_move',
        'payment_lines', 'number', 'taxes']

    target_company = fields.Many2One('company.company', 'Target company',
        domain=[
            ('party', '=', Eval('party')),
            ],
        states={
            'invisible': Eval('type', '') != 'out',
            'readonly': Eval('state') != 'draft',
            })
    intercompany_invoices = fields.Function(fields.One2Many('account.invoice',
            None, 'Intercompany Invoice'),
        'get_intercompany_invoices')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'create_intercompany_invoices': {
                    'invisible': (~Eval('state').in_(['posted', 'paid'])
                        | Equal(Eval('type'), 'in')),
                    },
                })

    def get_intercompany_invoices(self, name):
        if not self.target_company or not self.target_company.intercompany_user:
            return

        with Transaction().set_user(self.target_company.intercompany_user.id), \
                Transaction().set_context(company=self.target_company.id,
                _check_access=False):
            return [i.id for i in self.search([
                        ('lines.origin.invoice.id', '=', self.id,
                            'account.invoice.line'),
                        ('company', '=', self.target_company.id),
                        ('type', '=', self.intercompany_type),
                        ])]

    @classmethod
    def post(cls, invoices):
        super().post(invoices)
        cls.create_intercompany_invoices(invoices)

    @classmethod
    @ModelView.button
    def create_intercompany_invoices(cls, invoices):
        intercompany_invoices = defaultdict(list)

        for invoice in invoices:
            intercompany_invoice = invoice.get_intercompany_invoice()
            if intercompany_invoice:
                company = intercompany_invoice.company
                intercompany_invoices[company].append(
                    intercompany_invoice)

        for company, new_invoices in intercompany_invoices.items():
            # Company must be set on context to avoid domain errors
            with Transaction().set_user(company.intercompany_user.id), \
                    Transaction().set_context(company=company.id,
                    _check_access=False):
                to_write, to_create, to_post = [], [], []
                # XXX: Use save multi on version 3.6
                for new_invoice in new_invoices:
                    if new_invoice.id is None or invoice.id < 0:
                        to_create.append(new_invoice._save_values())
                    elif new_invoice._save_values():
                        to_write.append(new_invoice)
                    else:
                        to_post.append(new_invoice)
                to_post += cls.create(to_create)
                if to_write:
                    cls.write(*sum(
                            (([i], i._save_values()) for i in to_write),
                            ()))
                    # We must reload invoices
                    to_post += cls.browse(to_write)

                cls.post(to_post)

    @classmethod
    def draft(cls, invoices):
        to_delete = defaultdict(list)
        for invoice in invoices:
            with Transaction().set_user(0):
                intercompany = cls.browse(invoice.intercompany_invoices)
            for iinvoice in intercompany:
                to_delete[iinvoice.company.id].append(iinvoice)

        if to_delete:
            for company, delete in to_delete.items():
                if not company.intercompany_user:
                    continue

                with Transaction().set_user(company.intercompany_user.id), \
                        Transaction().set_context(company=company.id,
                        _check_access=False):
                    cls.draft(delete)
                    cls.delete(delete)
        super().draft(invoices)

    @classmethod
    def credit(cls, invoices, refund=False, **values):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        new_invoices = super().credit(invoices, refund, **values)
        if refund:
            for invoice, new_invoice in zip(invoices, new_invoices):
                if new_invoice.state == 'paid':
                    for source, target in zip(invoice.intercompany_invoices,
                            new_invoice.intercompany_invoices):
                        if not source.company.intercompany_user:
                            continue

                        with Transaction().set_user(0):
                            source, = cls.browse([source])
                            target, = cls.browse([target])
                            company_id = source.company.id
                            user_id = source.company.intercompany_user.id

                        with Transaction().set_user(user_id), \
                                Transaction().set_context(company=company_id,
                                _check_access=False):
                            lines = ([l for l in source.lines_to_pay
                                    if not l.reconciliation] +
                                [l for l in target.lines_to_pay
                                    if not l.reconciliation])
                            MoveLine.reconcile(lines)
        return new_invoices

    def get_intercompany_account(self):
        Party = Pool().get('party.party')

        with Transaction().set_user(self.target_company.intercompany_user.id), \
                Transaction().set_context(company=self.target_company.id,
                _check_access=False):
            party = Party(self.company.party)
            if self.type == 'out':
                return party.account_payable_used
            else:
                return party.account_receivable_used

    @property
    def intercompany_type(self):
        return 'in'

    def get_intercompany_invoice(self):
        Party = Pool().get('party.party')

        if (self.type != 'out' or not self.target_company
                or self.intercompany_invoices):
            return
        values = {}
        for name, field in self.__class__._fields.items():
            if (name in set(self._intercompany_excluded_fields) or
                    isinstance(field, fields.Function)):
                continue
            values[name] = getattr(self, name)

        if not self.target_company.intercompany_user:
            return

        with Transaction().set_user(self.target_company.intercompany_user.id), \
                Transaction().set_context(company=self.target_company.id,
                _check_access=False):
            invoice = self.__class__(**values)
            invoice.type = self.intercompany_type
            invoice.company = self.target_company
            # Rebrowse party in order to pick the correct company context
            invoice.party = Party(self.company.party)
            invoice.state = 'draft'
            invoice.reference = self.number
            invoice.on_change_party()
            invoice.account = self.get_intercompany_account()
            invoice.set_journal()
            lines = []
            for line in self.lines:
                lines.append(line.get_intercompany_line())
            invoice.lines = lines
            return invoice

    def _credit(self, **values):
        credit = super()._credit(**values)
        if self.target_company:
            credit.target_company = self.target_company.id
        return credit


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    _intercompany_excluded_fields = ['id', 'invoice', 'account', 'taxes', 'origin',
        'party', 'invoice_type', 'company', 'create_date', 'create_uid',
        'write_date', 'write_uid', 'intercompany_account']

    intercompany_invoice = fields.Function(fields.Boolean(
            'Intercompany Invoice'),
        'on_change_with_intercompany_invoice')
    intercompany_account = fields.Many2One('account.account.template',
        'Intercompany Account',
        domain=[
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type') == 'out',
                    ('type.expense', '=', True),
                    ('type.revenue', '=', True)),
                If(Eval('invoice_type') == 'out',
                    ('type.expense', '=', True),
                    ('type.revenue', '=', True)))
            ],
        states={
            'invisible': If(Bool(Eval('_parent_invoice')),
                    ~Bool(Eval('_parent_invoice', {}).get('target_company')),
                    ~Eval('intercompany_invoice', False)),
            'required': If(Bool(Eval('_parent_invoice')),
                    Bool(Eval('_parent_invoice', {}).get('target_company')),
                    Eval('intercompany_invoice', False)),
            },
        )

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if 'intercompany_invoice' not in cls.product.depends:
            required = Bool(Eval('intercompany_invoice'))
            old_required = cls.product.states.get('required')
            if old_required:
                required |= old_required
            cls.product.states['required'] = required
            cls.product.depends.add('intercompany_invoice')

    @fields.depends('_parent_invoice.target_company', '_parent_invoice.type',
        'invoice_type', 'invoice')
    def on_change_product(self):
        super().on_change_product()
        type_ = self.invoice.type if self.invoice else self.invoice_type
        if self.product and self.invoice and self.invoice.target_company:
            account_name = 'account_%s_used' % ('revenue' if type_[:2] == 'in'
                else 'expense')
            account = getattr(self.product, account_name)
            if account and account.template:
                self.intercompany_account = account.template

    @fields.depends('invoice', '_parent_invoice.target_company')
    def on_change_with_intercompany_invoice(self, name=None):
        return self.invoice and bool(self.invoice.target_company)

    def get_intercompany_account(self):
        target_company = self.invoice.target_company
        # TODO: Check for account without template
        return self.intercompany_account.get_syncronized_company_value(
            target_company)

    def get_intercompany_taxes(self):
        pool = Pool()
        Product = pool.get('product.product')
        Party = pool.get('party.party')

        taxes = set()
        if not self.product:
            return taxes

        target_company = self.invoice.target_company
        party = target_company.party
        type_ = self.invoice.type if self.invoice else self.invoice_type

        with Transaction().set_user(target_company.intercompany_user.id), \
                Transaction().set_context(company=target_company.id,
                _check_access=False):
            product = Product(self.product.id)
            party = Party(party.id)

            if type_ == 'out': # if is out, taxes from supplier (in)
                tax_rule = party.supplier_tax_rule
                tax_rule_template = (hasattr(target_company, 'supplier_tax_rule_template')
                    and getattr(target_company, 'supplier_tax_rule_template'))
                if tax_rule_template:
                    tax_rule = tax_rule_template.get_syncronized_company_value(target_company)

                pattern = self._get_tax_rule_pattern()
                for tax in product.supplier_taxes_used:
                    if party and tax_rule:
                        tax_ids = tax_rule.apply(tax, pattern)
                        if tax_ids:
                            taxes.update(tax_ids)
                        continue
                    taxes.add(tax.id)
                if party and tax_rule:
                    tax_ids = tax_rule.apply(None, pattern)
                    if tax_ids:
                        taxes.update(tax_ids)
            else:
                tax_rule = party.customer_tax_rule
                tax_rule_template = (hasattr(target_company, 'customer_tax_rule_template')
                    and getattr(target_company, 'customer_tax_rule_template'))
                if tax_rule_template:
                    tax_rule = tax_rule_template.get_syncronized_company_value(target_company)

                pattern = self._get_tax_rule_pattern()
                for tax in product.customer_taxes_used:
                    if party and tax_rule:
                        tax_ids = tax_rule.apply(tax, pattern)
                        if tax_ids:
                            taxes.update(tax_ids)
                        continue
                    taxes.add(tax.id)
                if party and tax_rule:
                    tax_ids = tax_rule.apply(None, pattern)
                    if tax_ids:
                        taxes.update(tax_ids)
        return taxes

    def get_intercompany_line(self):
        with Transaction().set_user(0):
            line = self.__class__()

        for name, field in self.__class__._fields.items():
            if (name in set(self._intercompany_excluded_fields) or
                    isinstance(field, fields.Function)):
                continue
            setattr(line, name, getattr(self, name))
        target_company = self.invoice.target_company

        with Transaction().set_user(target_company.intercompany_user.id), \
                Transaction().set_context(company=target_company.id,
                _check_access=False):
            line.invoice_type = self.invoice.intercompany_type
            line.company = target_company
            if self.party:
                line.party = target_company.party
            line.origin = self
            if line.type == 'line':
                line.account = self.get_intercompany_account()
                line.taxes = self.get_intercompany_taxes()
                if line.product:
                    if target_company.purchase_taxes_expense:
                        line.taxes_deductible_rate = 0
                    else:
                        line.taxes_deductible_rate = (
                            line.product.supplier_taxes_deductible_rate_used)
        return line

    def _credit(self):
        credit = super()._credit()
        credit.intercompany_account = self.intercompany_account
        return credit
