# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from collections import defaultdict
from trytond.model import fields, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

__all__ = ['Invoice', 'InvoiceLine']
__metaclass__ = PoolMeta


class Invoice:
    __name__ = 'account.invoice'
    _intercompany_excluded_fields = ['id', 'company', 'party', 'lines',
        'account', 'type', 'state', 'create_date', 'create_uid', 'write_date',
        'write_uid', 'target_company', 'taxes', 'invoice_report_cache',
        'invoice_report_format', 'move', 'number', 'taxes']

    target_company = fields.Many2One('company.company', 'Target company',
        domain=[
            ('party', '=', Eval('party')),
            ],
        states={
            'invisible': ~Eval('type', '').in_(
                ['out_invoice', 'out_credit_note']),
            'readonly': Eval('state') != 'draft',
            },
        depends=['type', 'state', 'party'])
    intercompany_invoices = fields.Function(fields.One2Many('account.invoice',
            None, 'Intercompany Invoice'),
        'get_intercompany_invoices')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._buttons.update({
                'create_intercompany_invoices': {
                    'invisible': (~Eval('state').in_(['posted', 'paid'])
                        | Eval('type').in_(['in_invoice', 'in_credit_note'])),
                    },
                })

    def get_intercompany_invoices(self, name):
        if not self.target_company:
            return []
        with Transaction().set_user(0):
            return [i.id for i in self.search([
                        ('lines.origin.invoice.id', '=', self.id,
                            'account.invoice.line'),
                        ('company', '=', self.target_company.id),
                        ('type', '=', self.intercompany_type),
                        ])]

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        cls.create_intercompany_invoices(invoices)

    @classmethod
    @ModelView.button
    def create_intercompany_invoices(cls, invoices):
        intercompany_invoices = defaultdict(list)
        transaction = Transaction()
        with transaction.set_user(0, set_context=True):
            for invoice in invoices:
                intercompany_invoice = invoice.get_intercompany_invoice()
                if intercompany_invoice:
                    company_id = intercompany_invoice.company.id
                    intercompany_invoices[company_id].append(
                        intercompany_invoice)
            for company, new_invoices in intercompany_invoices.iteritems():
                # Company must be set on context to avoid domain errors
                with transaction.set_context(company=company):
                    to_write, to_create, to_post = [], [], []
                    # XXX: Use save multi on version 3.6
                    for new_invoice in new_invoices:
                        if new_invoice.id is None or invoice.id < 0:
                            to_create.append(new_invoice._save_values)
                        elif new_invoice._save_values:
                            to_write.append(new_invoice)
                        else:
                            to_post.append(new_invoice)
                    to_post += cls.create(to_create)
                    if to_write:
                        cls.write(*sum(
                                (([i], i._save_values) for i in to_write),
                                ()))
                        # We must reload invoices
                        to_post += cls.browse(to_write)
                    super(Invoice, cls).post(to_post)

    @classmethod
    def draft(cls, invoices):
        to_delete = defaultdict(list)
        for invoice in invoices:
            with Transaction().set_user(0):
                intercompany = cls.browse(invoice.intercompany_invoices)
            for iinvoice in intercompany:
                to_delete[iinvoice.company.id].append(iinvoice)
        if to_delete:
            for company, delete in to_delete.iteritems():
                with Transaction().set_context(company=company):
                    cls.draft(delete)
                    cls.delete(delete)
        super(Invoice, cls).draft(invoices)

    @classmethod
    def credit(cls, invoices, refund=False):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        new_invoices = super(Invoice, cls).credit(invoices, refund)
        if refund:
            for invoice, new_invoice in zip(invoices, new_invoices):
                if new_invoice.state == 'paid':
                    for source, target in zip(invoice.intercompany_invoices,
                            new_invoice.intercompany_invoices):
                        with Transaction().set_user(0):
                            source, = cls.browse([source])
                            target, = cls.browse([target])
                            company = source.company.id
                        with Transaction().set_context(company=company):
                            lines = ([l for l in source.lines_to_pay
                                    if not l.reconciliation] +
                                [l for l in target.lines_to_pay
                                    if not l.reconciliation])
                            MoveLine.reconcile(lines)
        return new_invoices

    def get_intercompany_account(self):
        pool = Pool()
        Party = pool.get('party.party')
        with Transaction().set_context(company=self.target_company.id):
            party = Party(self.company.party)
            if self.type[:3] == 'out':
                return party.account_payable
            else:
                return party.account_receivable

    @property
    def intercompany_type(self):
        return 'in_%s' % self.type[4:]

    def get_intercompany_invoice(self):
        pool = Pool()
        Party = pool.get('party.party')
        if (self.type[:4] != 'out_' or not self.target_company
                or self.intercompany_invoices):
            return
        transaction = Transaction()
        values = {}
        for name, field in self.__class__._fields.iteritems():
            if (name in set(self._intercompany_excluded_fields) or
                    isinstance(field, fields.Function)):
                continue
            values[name] = getattr(self, name)
        old_lines = self.lines
        with transaction.set_context(company=self.target_company.id,
                _check_access=False):
            invoice = self.__class__(**values)
            invoice.type = self.intercompany_type
            invoice.company = self.target_company
            # Rebrowse party in order to pick the correct company context
            invoice.party = Party(self.company.party)
            invoice.state = 'draft'
            invoice.reference = self.number
            for field, value in invoice.on_change_party().iteritems():
                setattr(invoice, field, value)
            invoice.account = self.get_intercompany_account()
            lines = []
            for line in old_lines:
                lines.append(line.get_intercompany_line())
            invoice.lines = lines
            return invoice

    def _credit(self):
        res = super(Invoice, self)._credit()
        if self.target_company:
            res['target_company'] = self.target_company.id
        return res


class InvoiceLine:
    __name__ = 'account.invoice.line'
    # Excluce aeat340_book_key to force to calculate it on create
    _intercompany_excluded_fields = ['id', 'account', 'taxes', 'origin',
        'party', 'invoice_type', 'company', 'create_date', 'create_uid',
        'write_date', 'write_uid', 'intercompany_account', 'aeat340_book_key']

    intercompany_invoice = fields.Function(fields.Boolean(
            'Intercompany Invoice'),
        'on_change_with_intercompany_invoice')
    intercompany_account = fields.Many2One('account.account.template',
        'Intercompany Account',
        domain=[
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type').in_(['out_invoice',
                    'out_credit_note']),
                    ('kind', '=', 'expense'),
                    ('kind', '=', 'revenue')),
                If(Eval('invoice_type').in_(['out_invoice',
                            'out_credit_note']),
                    ('kind', '=', 'expense'),
                    ('kind', '=', 'revenue')))
            ],
        states={
            'invisible': If(Bool(Eval('_parent_invoice')),
                    ~Bool(Eval('_parent_invoice', {}).get('target_company')),
                    ~Eval('intercompany_invoice', False)),
            'required': If(Bool(Eval('_parent_invoice')),
                    Bool(Eval('_parent_invoice', {}).get('target_company')),
                    Eval('intercompany_invoice', False)),
            },
        depends=['intercompany_invoice', 'invoice_type'])

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        if 'intercompany_invoice' not in cls.product.depends:
            required = Bool(Eval('intercompany_invoice'))
            old_required = cls.product.states.get('required')
            if old_required:
                required |= old_required
            cls.product.states['required'] = required
            cls.product.depends.append('intercompany_invoice')

    @fields.depends('_parent_invoice.target_company', '_parent_invoice.type',
        'invoice_type')
    def on_change_product(self):
        changes = super(InvoiceLine, self).on_change_product()
        type_ = self.invoice.type if self.invoice else self.invoice_type
        if self.product and self.invoice and self.invoice.target_company:
            account_name = 'account_%s_used' % ('revenue' if type_[:2] == 'in'
                else 'expense')
            account = getattr(self.product, account_name)
            if account and account.template:
                changes['intercompany_account'] = account.template.id
        return changes

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
        taxes = []
        if not self.product:
            return taxes
        target_company = self.invoice.target_company
        type = self.invoice.type if self.invoice else self.invoice_type
        tax_name = '%s_taxes_used' % ('customer' if type[:2] == 'in'
            else 'supplier')
        with Transaction().set_context(company=target_company.id):
            product, = Product.browse([self.product.id])
            taxes = getattr(product, tax_name, [])
        return taxes

    def get_intercompany_line(self):
        with Transaction().set_user(0):
            line = self.__class__()
        for name, field in self.__class__._fields.iteritems():
            if (name in set(self._intercompany_excluded_fields) or
                    isinstance(field, fields.Function)):
                continue
            setattr(line, name, getattr(self, name))
        target_company = self.invoice.target_company
        with (Transaction().set_user(0) and
                Transaction().set_context(company=target_company.id)):
            line.invoice_type = self.invoice.intercompany_type
            line.company = target_company
            if self.party:
                line.party = target_company.party
            line.account = self.get_intercompany_account()
            line.taxes = self.get_intercompany_taxes()
            line.origin = self
        return line

    def _credit(self):
        res = super(InvoiceLine, self)._credit()
        res['intercompany_account'] = self.intercompany_account
        return res
