import smartpy as sp
from oracles.job_scheduler import Fulfill
import oracles.constants as Constants
import oracles.errors as Errors

class Response:
    def get_type():
        """The response type used for the price oracle that uses the generic data transmitter.
        """
        return sp.TRecord(certificates=sp.TList(sp.TString),
            timestamp=sp.TNat, 
            source_count=sp.TNat, 
            price=sp.TNat).layout(("certificates",("timestamp",("source_count","price"))))
    
    def make(certificates, timestamp, source_count, price):
        """Courtesy function typing a record to Fulfill.get_type() for us
        """
        return sp.set_type_expr(sp.record(certificates=certificates, 
                timestamp=timestamp,
                source_count=source_count,
                price=price), Response.get_type())


class PriceOracle(sp.Contract):
    def __init__(self):
        self.init(
            price=sp.nat(5984600),
            last_epoch=sp.nat(0),
            response_threshold=sp.nat(3),
            source_count_threshold=sp.nat(2),
            validity_window_in_epochs=sp.nat(4),
            valid_script=sp.bytes("0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533"),
            valid_response=sp.nat(0),
            valid_epoch=sp.nat(0),
            valid_respondants=sp.set([]),
            valid_certificates = sp.set([
                '80e4f8c906ba3218ba878cbeb55214dae70edd58b376b4367142875b8f7bb4b5',
                'c72992167b41042bc7be1ccdd24e0e2f6301c851e293006d9cae69cca22539d7',
                'e6edf32323d21bac574c4a7ad433e1c5b27d053e2d61fb2b7125129df6e3154e'
            ]),
            valid_sources = sp.set([
                sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe"),
                sp.address("tz3YzXZtqPHuFyX7zxGpkxjAtoA1gnYQkEnL"),
                sp.address("tz3Qg4gvJDj8f4hy3ewvb3wyxEXYXRYbZ6Mz"),
                sp.address("tz3cXew4V1uXDtxuQde5iFSKpxoiF5udC3L1"),
                sp.address("tz3UJN1ZMF7dAS9kJA3FQ5HTmZEpdpCgctjy")
            ]) 
        )

    @sp.entry_point
    def fulfill(self, fulfill):
        """The fulfill entrypoint is called by the data transmitter directly. It's your responsibility to make it
        as efficient as possible (it has a gas and storage limit of 11000). While the sp.sender of this entrypoint
        will always be the JobScheduler above, the sp.source will always be the data transmitter. It's your
        responsibility to check that you are receivng the data from the right source. This implementation does
        also aggregate multiple respondants, hence the slightly more complex implementation. 
        """
        sp.set_type(fulfill, Fulfill.get_type())

        sp.verify(self.data.valid_script == fulfill.script)
        sp.verify(self.data.valid_sources.contains(sp.source))
        
        response = sp.unpack(fulfill.payload, Response.get_type()).open_some()

        sp.for certificate in response.certificates:
            sp.verify(self.data.valid_certificates.contains(certificate))

        current_epoch = sp.local("current_epoch", response.timestamp / Constants.ORACLE_EPOCH_INTERVAL)

        with sp.if_((current_epoch.value != self.data.valid_epoch) & (response.source_count >= self.data.source_count_threshold)):
            self.data.valid_respondants = sp.set([])
            self.data.valid_epoch = current_epoch.value
            self.data.valid_response = response.price

        with sp.if_(sp.len(self.data.valid_respondants) < self.data.response_threshold):
            with sp.if_(response.price == self.data.valid_response):    
                self.data.valid_respondants.add(sp.source)
        sp.else:
            sp.failwith(Errors.THRESHOLD_REACHED)

        with sp.if_(sp.len(self.data.valid_respondants) >= self.data.response_threshold):    
            with sp.if_(self.data.price>>4 > abs(self.data.price-response.price)):
                self.data.price = response.price
            with sp.else_():
                with sp.if_(self.data.price-response.price>0):
                    self.data.price = sp.as_nat(self.data.price-(self.data.price>>4))
                with sp.else_():
                    self.data.price = self.data.price+(self.data.price>>4)
            self.data.last_epoch = current_epoch.value

    @sp.entry_point
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: as we require for our use case the quote currency to be the collateral we are "flipping" base and quote by 1//"stored price"

        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        current_epoch = sp.as_nat(sp.now-sp.timestamp(0)) / Constants.ORACLE_EPOCH_INTERVAL
        sp.verify(self.data.last_epoch>sp.as_nat(current_epoch-self.data.validity_window_in_epochs), message=Errors.PRICE_TOO_OLD)
        sp.transfer(sp.nat(Constants.PRECISION_FACTOR)//self.data.price, sp.mutez(0), callback)

 
if "templates" not in __name__:
    from oracles.job_scheduler import JobScheduler, Job
    from utils.viewer import Viewer
    @sp.add_test(name = "Generic Price Oracle")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("Job Scheduler")

        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")

        scenario.h2("Accounts")
        scenario.show([administrator, alice, bob, dan])
        
        scheduler = JobScheduler(administrator.address)
        scenario += scheduler

        price_oracle = PriceOracle()
        scenario += price_oracle

        script=sp.bytes("0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533")
        valid_certificate1 = '80e4f8c906ba3218ba878cbeb55214dae70edd58b376b4367142875b8f7bb4b5'
        valid_certificate2 = 'c72992167b41042bc7be1ccdd24e0e2f6301c851e293006d9cae69cca22539d7'
        valid_certificate3 = 'e6edf32323d21bac574c4a7ad433e1c5b27d053e2d61fb2b7125129df6e3154e'
        invalid_certificate = '00e4f8c906ba3218ba878cbeb55214dae70edd58b376b4367142875b8f7bb400'
        valid_executor1 = sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe")
        valid_executor2 = sp.address("tz3YzXZtqPHuFyX7zxGpkxjAtoA1gnYQkEnL")
        valid_executor3 = sp.address("tz3Qg4gvJDj8f4hy3ewvb3wyxEXYXRYbZ6Mz")
        valid_executor4 = sp.address("tz3cXew4V1uXDtxuQde5iFSKpxoiF5udC3L1")

        interval = 900
        fee = 1700
        start=sp.timestamp(0)
        end=sp.timestamp(1800000)

        job = Job.make_publish(valid_executor1, script, start, end, interval, fee, price_oracle.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)
        job = Job.make_publish(valid_executor2, script, start, end, interval, fee, price_oracle.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)
        job = Job.make_publish(valid_executor3, script, start, end, interval, fee, price_oracle.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)
        job = Job.make_publish(valid_executor4, script, start, end, interval, fee, price_oracle.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)
        job = Job.make_publish(alice.address, script, start, end, interval, fee, price_oracle.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)

        now=900
        source_count = 2
        price=sp.nat(6000000)
        certificates = [valid_certificate1, valid_certificate2, valid_certificate3]

        scenario.h2("Response publishing")
        scenario.p("Only valid executors can publish a new price")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=alice.address, source=alice.address, valid=False)
        scenario.verify_equal(price_oracle.data.valid_response, sp.nat(0))
        scenario.p("Only valid executors can publish a new price")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario.verify_equal(price_oracle.data.valid_response, price)

        scenario.h2("Response Threshold")
        scenario.p("Same Executor only counts once")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario.verify_equal(price_oracle.data.price, sp.nat(5984600))

        scenario.p("Different Executor non-matching price does not count")
        price=sp.nat(6000001)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.price, sp.nat(5984600))

        scenario.p("Different Executor non-matching certificate does not count")
        certificates = [valid_certificate1, valid_certificate2, invalid_certificate]
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor2, source=valid_executor2, valid=False)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor3, source=valid_executor3, valid=False)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor4, source=valid_executor4, valid=False)
        scenario.verify_equal(price_oracle.data.price, sp.nat(5984600))

        scenario.p("Different Executor with all matching works")
        price=sp.nat(6000000)
        certificates = [valid_certificate1, valid_certificate2, valid_certificate3]
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario.verify_equal(price_oracle.data.price, price)
        
        scenario.p("Too many answers will not be allowed either")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor4, source=valid_executor4, valid=False)

        scenario.p("Big price drop only impacts 6.25%")
        certificates = [valid_certificate1, valid_certificate2, valid_certificate3]
        price=sp.nat(0)
        now=1800
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.price, 5625000)

        scenario.p("Big price increase only impacts 6.25%")
        certificates = [valid_certificate1, valid_certificate2, valid_certificate3]
        price=sp.nat(90000000)
        now=4500
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(certificates, now, source_count, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.price, 5976562)
        
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(sp.TNat, viewer.address, entry_point="set_nat").open_some()

        scenario.h2("make sure the base/quote flip works")
        scenario += price_oracle.get_price(return_contract).run(sender=administrator.address, now=sp.timestamp(4500))
        scenario.verify_equal(viewer.data.nat, Constants.PRECISION_FACTOR//5976562)

        scenario.h2("get an old price")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*9)
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(
            sp.TNat, viewer.address, entry_point="set_nat").open_some()
        scenario += price_oracle.get_price(return_contract).run(now=sp.timestamp(4500+60*60), sender=administrator.address, valid=False)





