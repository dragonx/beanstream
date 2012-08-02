import ConfigParser
from datetime import date
import unittest

from beanstream import gateway
from beanstream import billing


class BeanstreamTests(unittest.TestCase):

    def setUp(self):
        config = ConfigParser.SafeConfigParser()
        config.read('beanstream.cfg')
        merchant_id = config.get('beanstream', 'merchant_id')
        company = config.get('beanstream', 'company')
        username = config.get('beanstream', 'username')
        password = config.get('beanstream', 'password')

        hashcode = None
        if config.has_option('beanstream', 'hashcode'):
            hashcode = config.get('beanstream', 'hashcode')

        hash_algorithm = None
        if config.has_option('beanstream', 'hash_algorithm'):
            hash_algorithm = config.get('beanstream', 'hash_algorithm')

        payment_profile_passcode = None
        if config.has_option('beanstream', 'payment_profile_passcode'):
            payment_profile_passcode = config.get('beanstream', 'payment_profile_passcode')

        recurring_billing_passcode = None
        if config.has_option('beanstream', 'recurring_billing_passcode'):
            recurring_billing_passcode = config.get('beanstream', 'recurring_billing_passcode')

        hash_validation = config.has_option('config', 'hash_validation')
        require_billing_address = config.has_option('config', 'require_billing_address')
        require_cvd = config.has_option('config', 'require_cvd')

        self.beanstream = gateway.Beanstream(
                hash_validation=hash_validation,
                require_billing_address=require_billing_address,
                require_cvd=require_cvd)
        self.beanstream.configure(
                merchant_id,
                company,
                username,
                password,
                hashcode=hashcode,
                hash_algorithm=hash_algorithm,
                payment_profile_passcode=payment_profile_passcode,
                recurring_billing_passcode=recurring_billing_passcode)

        self.approved_cards = {'visa': {'number': '4030000010001234', 'cvd': '123'},
                               '100_visa': {'number': '4504481742333', 'cvd': '123'},
                               'vbv_visa': {'nubmer': '4123450131003312', 'cvd': '123', 'vbv': '12345'},
                               'mc1': {'number': '5100000010001004', 'cvd': '123'},
                               'mc2': {'number': '5194930004875020', 'cvd': '123'},
                               'mc3': {'number': '5123450000002889', 'cvd': '123'},
                               '3d_mc': {'number': '5123450000000000', 'cvd': '123', 'passcode': '12345'},
                               'amex': {'number': '371100001000131', 'cvd': '1234'},
                               'discover': {'number': '6011500080009080', 'cvd': '123'},
                              }
        self.declined_cards = {'visa': {'number': '4003050500040005', 'cvd': '123'},
                               'mc': {'number': '5100000020002000', 'cvd': '123'},
                               'amex': {'number': '342400001000180', 'cvd': '1234'},
                               'discover': {'number': '6011000900901111', 'cvd': '123'},
                              }

        self.billing_address = billing.Address(
            'John Doe',
            'john.doe@example.com',
            '555-555-5555',
            '123 Fake Street',
            '',
            'Fake City',
            'ON',
            'A1A1A1',
            'CA')

    def tearDown(self):
        pass

    def test_successful_cc_purchase(self):
        today = date.today()
        visa = self.approved_cards['visa']
        card = billing.CreditCard(
            'John Doe',
            visa['number'],
            str(today.month), str(today.year + 3),
            visa['cvd'])

        txn = self.beanstream.purchase(50, card, self.billing_address)
        txn.set_comments('%s:test_successful_cc_purchase' % __name__)
        resp = txn.commit()
        assert resp.approved()
        assert resp.cvd_status() == 'CVD Match'

    def test_failed_cvd(self):
        today = date.today()
        visa = self.approved_cards['visa']
        card = billing.CreditCard(
            'John Doe',
            visa['number'],
            str(today.month), str(today.year + 3),
            '000')

        txn = self.beanstream.purchase(50, card, self.billing_address)
        txn.set_comments('%s:test_failed_cvd' % __name__)
        resp = txn.commit()
        assert not resp.approved()
        assert resp.cvd_status() == 'CVD Not Verified'

    def test_over_limit_cc_purchase(self):
        today = date.today()
        visa_limit = self.approved_cards['100_visa']
        card = billing.CreditCard(
            'John Doe',
            visa_limit['number'],
            str(today.month), str(today.year + 3),
            visa_limit['cvd'])

        txn = self.beanstream.purchase(250, card, self.billing_address)
        txn.set_comments('%s:test_over_limit_cc_purchase' % __name__)
        resp = txn.commit()
        assert not resp.approved()
        assert resp.cvd_status() == 'CVD Match'

    def test_create_recurring_billing(self):
        today = date.today()
        visa = self.approved_cards['visa']
        card = billing.CreditCard(
            'John Doe',
            visa['number'],
            str(today.month), str(today.year + 3),
            visa['cvd'])

        txn = self.beanstream.create_recurring_billing_account(50, card, 'w', 2, billing_address=self.billing_address)
        txn.set_comments('%s:test_create_recurring_billing:create_recurring_billing' % __name__)
        resp = txn.commit()
        assert resp.approved()
        assert resp.cvd_status() == 'CVD Match'
        assert resp.account_id() is not None

        account_id = resp.account_id()

        txn = self.beanstream.modify_recurring_billing_account(account_id)
        txn.set_comments('%s:test_create_recurring_billing:modify_recurring_billing' % __name__)
        txn.set_billing_state('closed')
        resp = txn.commit()
        assert resp.approved()

    def test_payment_profiles(self):
        today = date.today()
        visa = self.approved_cards['visa']
        card = billing.CreditCard(
            'John Doe',
            visa['number'],
            str(today.month), str(today.year + 3),
            visa['cvd'])

        txn = self.beanstream.create_payment_profile(card, billing_address=self.billing_address)
        resp = txn.commit()
        assert resp.approved()

        customer_code = resp.customer_code()

        txn = self.beanstream.purchase_with_payment_profile(50, customer_code)
        txn.set_comments('%s:test_payment_profiles:purchase_with_payment_profile' % __name__)
        resp = txn.commit()
        assert resp.approved()

        txn = self.beanstream.modify_payment_profile(customer_code)
        txn.set_status('disabled')
        resp = txn.commit()
        assert resp.approved()

        txn = self.beanstream.purchase_with_payment_profile(50, customer_code)
        txn.set_comments('%s:test_payment_profiles:purchase_with_payment_profile' % __name__)
        resp = txn.commit()
        assert not resp.approved()

    def test_payment_profile_from_recurring_billing(self):
        today = date.today()
        visa = self.approved_cards['visa']
        card = billing.CreditCard(
            'John Doe',
            visa['number'],
            str(today.month), str(today.year + 3),
            visa['cvd'])

        txn = self.beanstream.create_payment_profile(card, billing_address=self.billing_address)
        resp = txn.commit()
        assert resp.approved()

        customer_code = resp.customer_code()

        txn = self.beanstream.create_recurring_billing_account_from_payment_profile(25, customer_code, 'w', 4)
        txn.set_comments('%s:test_payment_profile_from_recurring_billing:create_recurring_billing_account_from_payment_profile' % __name__)
        resp = txn.commit()
        assert resp.approved()
        assert resp.account_id() is not None

    def test_simple_report(self):
        txn = self.beanstream.get_transaction_report()
        txn.set_date_range(date(2011, 8, 12), date(2011, 8, 14))

        resp = txn.commit()

        assert len(resp) == 0

    def test_transaction_set_report(self):
        transaction_ids = [10000283, 10000301, 10000290]
        txn = self.beanstream.get_transaction_set_report(transaction_ids)
        resp = txn.commit()

        assert len(resp) == 3

        for item in resp:
            assert int(item['transaction_id']) in transaction_ids

