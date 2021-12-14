import smartpy as sp
from oracles.job_scheduler import Fulfill
import oracles.constants as Constants
import oracles.errors as Errors

class Response:
    def get_type():
        """The response type used for the price oracle that uses the generic data transmitter.
        """
        return sp.TRecord(
            timestamp=sp.TNat,
            defi_price=sp.TNat,
            xtz_price=sp.TNat,
            btc_price=sp.TNat).layout(("timestamp",("defi_price",("xtz_price","btc_price"))))
    
    def make(timestamp, defi_price, xtz_price, btc_price):
        """Courtesy function typing a record to Response.get_type() for us
        """
        return sp.set_type_expr(sp.record(
                timestamp=timestamp,
                defi_price=defi_price,
                xtz_price=xtz_price,
                btc_price=btc_price), Response.get_type())


class PriceOracle(sp.Contract):
    """The generic price oracle accepts prices from the set sources and set script. The price is allowed to change only 6.25% max from the previous
    set price. This version of the oracle uses the onchain views. Only the administrator is allowed to change the script and sources.
    """
    def __init__(self, administrator):
        self.init(
            prices=sp.big_map(tkey=sp.TString, tvalue=sp.TNat),
            last_epoch=sp.nat(0),
            response_threshold=sp.nat(3),
            validity_window_in_epochs=sp.nat(4),
            valid_script=sp.bytes("0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533"),
            valid_defi_price=sp.nat(0),
            valid_xtz_price=sp.nat(0),
            valid_btc_price=sp.nat(0),
            valid_epoch=sp.nat(0),
            valid_respondants=sp.set([]),
            valid_sources = sp.set([
                sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe"),
                sp.address("tz3YzXZtqPHuFyX7zxGpkxjAtoA1gnYQkEnL"),
                sp.address("tz3Qg4gvJDj8f4hy3ewvb3wyxEXYXRYbZ6Mz"),
                sp.address("tz3cXew4V1uXDtxuQde5iFSKpxoiF5udC3L1"),
                sp.address("tz3UJN1ZMF7dAS9kJA3FQ5HTmZEpdpCgctjy")
            ]), 
            administrator=administrator 
        )
    
    @sp.entry_point
    def set_valid_script(self, script):
        """Entrypoint used by the admin to set the valid script. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_script = script

    @sp.entry_point
    def set_administrator(self, administrator):
        """Entrypoint used by the admin to set the new admin. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.administrator = administrator
    
    @sp.entry_point
    def add_valid_source(self, source):
        """Entrypoint used by the admin to add a new source. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.add(source)

    @sp.entry_point
    def remove_valid_source(self, source):
        """Entrypoint used by the admin to remove an existing source. Only admin is allowed to call this entrypoint.
        """
        sp.verify(sp.sender==self.data.administrator, message=Errors.NOT_ADMIN)
        self.data.valid_sources.remove(source)

    @sp.private_lambda()
    def smooth(self, pair):
        """Lambda that takes as paramenter a pair (old_value: TNat, new_value: TNat) and returns 
        if the change is bigger than 6.25% old_value*1.0625 if the change is smaller than 6.25% old_value*0.9375. If the
        value is in between between new_value is returned.
        """
        old_value, new_value = sp.match_pair(pair)
        sp.verify(new_value > 0, message=Errors.NULL_VALUE)
        with sp.if_((old_value==0) | (old_value>>4 > abs(old_value-new_value))):
            sp.result(new_value)
        with sp.else_():
            with sp.if_(old_value-new_value>0):
                sp.result(sp.as_nat(old_value-(old_value>>4)))
            with sp.else_():
                sp.result(old_value+(old_value>>4))

    @sp.entry_point
    def fulfill(self, fulfill):
        """The fulfill entrypoint is called by the data transmitter directly. It's your responsibility to make it
        as efficient as possible (it has a gas and storage limit of 11000). While the sp.sender of this entrypoint
        will always be the JobScheduler above, the sp.source will always be the data transmitter. It's your
        responsibility to check that you are receivng the data from the right source. This implementation does
        also aggregate multiple respondants, hence the slightly more complex implementation. 

        This entrypoint checks if the source and script is valid, then if the answer fits in the current epoch
        , comes from a new source and matches with some minor precision margin the value set by a previous source
        the response is counted as +1. If the response counter reaches the threshold the price in storage is set 
        and ready to be used by the get_price entrypoint.
        """
        sp.set_type(fulfill, Fulfill.get_type())

        sp.verify(self.data.valid_script == fulfill.script, message=Errors.INVALID_SCRIPT)
        sp.verify(self.data.valid_sources.contains(sp.source), message=Errors.INVALID_SOURCE)
        
        response = sp.local("response", sp.unpack(fulfill.payload, Response.get_type()).open_some())

        current_epoch = sp.local("current_epoch", response.value.timestamp / Constants.ORACLE_EPOCH_INTERVAL)

        with sp.if_((current_epoch.value != self.data.valid_epoch)):
            self.data.valid_respondants = sp.set([])
            self.data.valid_epoch = current_epoch.value
            self.data.valid_defi_price = response.value.defi_price
            self.data.valid_xtz_price = response.value.xtz_price
            self.data.valid_btc_price = response.value.btc_price

        with sp.if_(sp.len(self.data.valid_respondants) < self.data.response_threshold):
            with sp.if_(
                (self.data.valid_defi_price>>Constants.PRECISION_SHIFT >= abs(response.value.defi_price - self.data.valid_defi_price)) &
                (self.data.valid_xtz_price>>Constants.PRECISION_SHIFT >= abs(response.value.xtz_price - self.data.valid_xtz_price)) &
                (self.data.valid_btc_price>>Constants.PRECISION_SHIFT >= abs(response.value.btc_price - self.data.valid_btc_price))
            ):    
                self.data.valid_respondants.add(sp.source)

                with sp.if_(sp.len(self.data.valid_respondants) >= self.data.response_threshold):
                    self.data.prices['DEFI'] = self.smooth(sp.pair(self.data.prices.get('DEFI',0), self.data.valid_defi_price))
                    self.data.prices['XTZ'] = self.smooth(sp.pair(self.data.prices.get('XTZ',0), self.data.valid_xtz_price))
                    self.data.prices['BTC'] = self.smooth(sp.pair(self.data.prices.get('BTC',0), self.data.valid_btc_price))

                    self.data.last_epoch = current_epoch.value

    @sp.onchain_view()
    def get_price(self, symbol):
        """Onchain view used to read the price out of storage. The onchain view takes the symbol as parameter and reads the respective
        entry from storage to then return it. The price is only returned if it is not older than the validity window set in storage 
        expressed it interval integer. This
        """
        current_epoch = sp.as_nat(sp.now-sp.timestamp(0)) / Constants.ORACLE_EPOCH_INTERVAL
        sp.verify(self.data.last_epoch>sp.as_nat(current_epoch-self.data.validity_window_in_epochs), message=Errors.PRICE_TOO_OLD)
        sp.result(self.data.prices[symbol])

class LegacyProxyOracle(sp.Contract):
    """This smart contract is used for retrocompatibility. It allows contracts that used the pre-onchain-view callback "get_price(cb)" 
    entrypoint to read data from the new generic oracle that uses the onchain view standard. It's instantiated with the oracle's address
    and symbol to request. 
    """
    def __init__(self, oracle, symbol, requires_flip):
        self.requires_flip = requires_flip
        self.init(
            oracle=oracle,
            symbol=symbol
        )
        
    @sp.entry_point
    def default(self):
        """This is a dummy entrypoint in order to allow us to have the named "get_price" entrypoint (if a contract has only 
        1 entrypoint it becomes not-named default otherwise).
        """
        sp.send(sp.sender, sp.amount)

    @sp.entry_point
    def get_price(self, callback):
        """this entrypoint can be called by everyone that provides a valid callback. Only if the price is not older than 4 epochs it will be returned.
        IMPORTANT: some engines (i.e. uUSD engine) require for our use case the quote currency to be the collateral we are "flipping" base and quote 
        by 1//"stored price" if the python variable self.requires_flip is set to True. This switch is evaluated at compiletime and will not be reflected
        in the resulting michelson.
 
        Args:
            callback (sp.TContract(sp.TNat)): callback where to receive the price
        """
        sp.set_type(callback, sp.TContract(sp.TNat))
        price = sp.view("get_price", self.data.oracle, self.data.symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)     
        if self.requires_flip:  
            sp.transfer(10**12//price, sp.mutez(0), callback)
        else:
            sp.transfer(price, sp.mutez(0), callback)

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

        price_oracle = PriceOracle(administrator.address)
        scenario += price_oracle

        script=sp.bytes("0x697066733a2f2f516d50367043416a5337525948383768573366454a754631524b6f75486a7a55674c5035694e61323853636b5533")
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
        price=sp.nat(6000000)
        
        scenario.h2("Response publishing")
        scenario.p("Only valid executors can publish a new price")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=alice.address, source=alice.address, valid=False)
        scenario.verify_equal(price_oracle.data.valid_defi_price, sp.nat(0))
        scenario.p("Only valid executors can publish a new price")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario.verify_equal(price_oracle.data.valid_defi_price, price)

        scenario.h2("Response Threshold")
        scenario.p("Same Executor only counts once")
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor1, source=valid_executor1)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), sp.nat(0))

        scenario.p("Different Executor non-matching (too big difference) price does not count")
        price=sp.nat(6002000)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), sp.nat(0))

        scenario.p("Different Executor with all matching works")
        price=sp.nat(6000000)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), price)
        
        scenario.p("Big price drop only impacts 6.25%")
        price=sp.nat(1)
        now=1800
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), 5625000)

        scenario.p("Big price increase only impacts 6.25%")
        price=sp.nat(90000000)
        now=4500
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), 5976562)

        scenario.p("Inaccurate but similar answers are accepted")
        price=sp.nat(90000000)
        now=Constants.ORACLE_EPOCH_INTERVAL*6
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price, price, price)))).run(sender=valid_executor2, source=valid_executor2)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price+1, price+1, price+1)))).run(sender=valid_executor3, source=valid_executor3)
        scenario += scheduler.fulfill(Fulfill.make(script, sp.pack(Response.make(now, price+3, price+3, price+3)))).run(sender=valid_executor4, source=valid_executor4)
        scenario.verify_equal(price_oracle.data.prices.get('DEFI',0), 6350097)
        
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(sp.TNat, viewer.address, entry_point="set_nat").open_some()

        scenario.h2("using the proxy")
        proxy = LegacyProxyOracle(price_oracle.address, "BTC")
        scenario += proxy
        scenario += proxy.get_price(return_contract).run(now=sp.timestamp(now), valid=True)
        scenario.verify_equal(viewer.data.nat, 6350097)

        scenario.h2("get an old price through the proxy")
        now = sp.timestamp(Constants.ORACLE_EPOCH_INTERVAL*10)
        scenario += proxy.get_price(return_contract).run(now=now, valid=False)

        scenario.h2("only admin can set new script")
        scenario += price_oracle.set_valid_script(sp.bytes("0x01")).run(sender=alice, valid=False)
        scenario += price_oracle.set_valid_script(sp.bytes("0x02")).run(sender=administrator)
        scenario.verify_equal(price_oracle.data.valid_script, sp.bytes("0x02"))

        scenario.h2("only admin can set a new source")
        scenario += price_oracle.add_valid_source(alice.address).run(sender=alice, valid=False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(alice.address), False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), False)
        scenario += price_oracle.add_valid_source(bob.address).run(sender=administrator)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(alice.address), False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), True)

        scenario.h2("only admin can remove source")
        scenario += price_oracle.remove_valid_source(bob.address).run(sender=alice, valid=False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(alice.address), False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), True)
        scenario += price_oracle.remove_valid_source(bob.address).run(sender=administrator)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(alice.address), False)
        scenario.verify_equal(price_oracle.data.valid_sources.contains(bob.address), False)

        scenario.h2("only admin can set admin")
        scenario += price_oracle.set_administrator(alice.address).run(sender=alice, valid=False)
        scenario += price_oracle.set_administrator(bob.address).run(sender=administrator)
        scenario.verify_equal(price_oracle.data.administrator, bob.address)
        scenario += price_oracle.set_administrator(administrator.address).run(sender=administrator, valid=False)
        scenario += price_oracle.set_administrator(administrator.address).run(sender=bob)
        scenario.verify_equal(price_oracle.data.administrator, administrator.address)
