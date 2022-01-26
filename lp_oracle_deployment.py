from pytezos.operation.result import OperationResult
from pytezos import pytezos, ContractInterface
import time
import sys

from settings import settings

def main():
    """This script deploys the contracts, wires them and performs calls tries to call some of the methods.

    """
    pytezos_admin_client = pytezos.using(key=settings.ADMIN_KEY, shell=settings.SHELL)
    administrator = pytezos_admin_client.key.public_key_hash()
    print(administrator)
    def get_address(operation_hash):
        while True:
            try:
                opg = pytezos_admin_client.shell.blocks[-20:].find_operation(operation_hash)
                originated_contracts = OperationResult.originated_contracts(opg)
                if len(originated_contracts) >= 1:
                    return originated_contracts[0]
            except:
                pass

    print("Starting Generic Oracledeployment...")
    lp_oracle_code = ContractInterface.from_file('out/FlippedLPPriceOracle/step_000_cont_7_contract.tz')
    storage = lp_oracle_code.storage.dummy()

    storage['lp_token_address'] = settings.LPT_ADDRESS
    storage['lp_address'] = settings.LP_ADDRESS
    storage['value_token_address'] = settings.VALUE_TOKEN_ADDRESS
    storage['value_token_oracle_address'] = settings.VALUE_TOKEN_ORACLE_ADDRESS
    storage['value_token_oracle_symbol'] = settings.VALUE_TOKEN_ORACLE_SYMBOL

    operation_group = pytezos_admin_client.origination(script=lp_oracle_code.script(initial_storage=storage)).send()
    target_oracle_address = get_address(operation_group.hash())
    print("done: '{}'".format(target_oracle_address))

if __name__ == '__main__':
    main()