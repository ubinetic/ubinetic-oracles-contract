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

    print("Starting Relative Oracle deployment...")
    relative_oracle_code = ContractInterface.from_file('out/RelativeProxyOracle/step_000_cont_8_contract.tz')
    storage = relative_oracle_code.storage.dummy()

    storage['oracle'] = settings.SOURCE_ORACLE
    storage['base_symbol'] = settings.BASE_SYMBOL
    storage['quote_symbol'] = settings.QUOTE_SYMBOL

    operation_group = pytezos_admin_client.origination(script=relative_oracle_code.script(initial_storage=storage)).send()
    target_oracle_address = get_address(operation_group.hash())
    print("done: '{}'".format(target_oracle_address))

if __name__ == '__main__':
    main()