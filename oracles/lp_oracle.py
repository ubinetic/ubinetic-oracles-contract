import smartpy as sp
import oracles.constants as Constants
import oracles.errors as Errors
       
class LPPriceOracle(sp.Contract):
    """
    """
    def __init__(self, lp_token_address, lp_address, value_token_address, value_token_decimals, value_token_oracle_address, value_token_oracle_symbol):
        self.init(
            lpt_total_supply=sp.nat(0),            
            value_token_balance_of=sp.nat(0),
            lp_token_address=lp_token_address,
            lp_address=lp_address,
            value_token_address=value_token_address,
            value_token_oracle_address=value_token_oracle_address,
            value_token_oracle_symbol=value_token_oracle_symbol
        )
        self.value_token_decimals = value_token_decimals
    
    @sp.entry_point
    def set_lpt_total_supply(self, lpt_total_supply):
        """Entrypoint used by the LP token to provide its total supply
        """
        self.data.lpt_total_supply = lpt_total_supply
    
    @sp.entry_point
    def set_value_token_balance_of(self, value_token_balance_of):
        """Entrypoint used by the value token to provide the balance
        """
        self.data.value_token_balance_of = value_token_balance_of

    @sp.entry_point
    def get_price(self, callback):
        """Entrypoint used to update the ratio
        """
        sp.set_type(callback, sp.TContract(sp.TNat))

        get_total_supply_contract = sp.contract(sp.TPair(sp.TUnit, sp.TContract(sp.TNat)), self.data.lp_token_address, entry_point="getTotalSupply").open_some()
        total_supply_callback_contract = sp.contract(sp.TNat, sp.self_address, entry_point="set_lpt_total_supply").open_some()
        sp.transfer(sp.pair(sp.unit, total_supply_callback_contract), sp.mutez(0), get_total_supply_contract)

        get_value_token_balance_contract = sp.contract(sp.TPair(sp.TAddress, sp.TContract(sp.TNat)), self.data.value_token_address, entry_point="getBalance").open_some()
        value_token_balance_callback_contract = sp.contract(sp.TNat, sp.self_address, entry_point="set_value_token_balance_of").open_some()
        sp.transfer(sp.pair(self.data.lp_address, value_token_balance_callback_contract), sp.mutez(0), get_value_token_balance_contract)

        sp.transfer(callback, sp.mutez(0), sp.self_entry_point("internal_get_price"))

    @sp.entry_point
    def internal_get_price(self, callback):  
        sp.set_type(callback, sp.TContract(sp.TNat))
        sp.verify(sp.sender == sp.self_address, message=Errors.NOT_INTERNAL)

        value_token_per_lpt_ratio = self.data.value_token_balance_of*Constants.PRICE_PRECISION // self.data.lpt_total_supply
        value_token_price = sp.view("get_price", self.data.value_token_oracle_address, self.data.value_token_oracle_symbol, t=sp.TNat).open_some(Errors.INVALID_VIEW)
        sp.transfer(value_token_price*value_token_per_lpt_ratio*2//(Constants.PRICE_PRECISION * 10**self.value_token_decimals), sp.mutez(0), callback)

if "templates" not in __name__:
    from utils.viewer import Viewer

    class DummyValueToken(sp.Contract):
        def __init__(self, balance):
            self.init(balance=balance)

        @sp.entry_point
        def default(self):
            pass

        @sp.entry_point
        def getBalance(self, parameters):
            sp.set_type(parameters, sp.TPair(sp.TAddress, sp.TContract(sp.TNat)))
            sp.transfer(self.data.balance, sp.mutez(0), sp.snd(parameters))

    class DummyLPToken(sp.Contract):
        def __init__(self, total_supply):
            self.init(total_supply=total_supply)

        @sp.entry_point
        def default(self):
            pass

        @sp.entry_point
        def getTotalSupply(self, parameters):
            sp.set_type(parameters, sp.TPair(sp.TUnit, sp.TContract(sp.TNat)))
            sp.transfer(self.data.total_supply, sp.mutez(0), sp.snd(parameters))

    class DummyOracle(sp.Contract):
        def __init__(self, price):
            self.init(price=price)
        
        @sp.entry_point
        def default(self):
            pass

        @sp.onchain_view()
        def get_price(self, symbol):
            sp.set_type(symbol, sp.TAddress)
            sp.result(self.data.price)

    from utils.viewer import Viewer
    @sp.add_test(name = "LP Price Oracle")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("LP Price Oracle")

        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")

        scenario.h2("Accounts")
        scenario.show([administrator, alice, bob, dan])        

        value_token = DummyValueToken(sp.nat(20775622511))
        scenario += value_token

        lp_token = DummyLPToken(sp.nat(177550279))
        scenario += lp_token        

        value_token_oracle = DummyOracle(sp.nat(47403660000))
        scenario += value_token_oracle

        lp_price_oracle = LPPriceOracle(lp_token.address, administrator.address, value_token.address, 8, value_token_oracle.address, "BTC")
        scenario += lp_price_oracle
        
        viewer = Viewer()
        scenario += viewer
        return_contract = sp.contract(sp.TNat, viewer.address, entry_point="set_nat").open_some()

        scenario.h2("Call get_price")
        scenario += lp_price_oracle.get_price(return_contract)

