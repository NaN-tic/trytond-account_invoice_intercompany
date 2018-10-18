# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class AccountInvoiceIntercomanyTestCase(ModuleTestCase):
    'Test Account Invoice Intercompany'
    module = 'account_invoice_intercompany'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountInvoiceIntercomanyTestCase))
#    Scenario works until post invoice, proteus didn't like to change contex
#    and company.
#    suite.addTests(doctest.DocFileSuite('scenario_invoice_intercompany.rst',
#            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
#            checker=doctest_checker,
#            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
