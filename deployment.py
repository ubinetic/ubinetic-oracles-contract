from pytezos.operation.result import OperationResult
from pytezos import pytezos, ContractInterface
import time
import sys

from settings import settings

def main():
    """This script deploys the contracts, wires them and performs calls tries to call some of the methods.

    """
    pytezos_admin_client = pytezos.using(key=settings.ADMIN_KEY, shell=settings.SHELL)

    def get_address(operation_hash):
        while True:
            try:
                opg = pytezos_admin_client.shell.blocks[-20:].find_operation(operation_hash)
                originated_contracts = OperationResult.originated_contracts(opg)
                if len(originated_contracts) >= 1:
                    return originated_contracts[0]
            except:
                pass

    def wait_applied(operation_hash):
        while True:
            try:
                opg = pytezos_admin_client.shell.blocks[-20:].find_operation(operation_hash)
                originated_contracts = OperationResult.is_applied(opg)
                if originated_contracts:
                    time.sleep(5)
                    return True
            except:
                pass

    print(pytezos_admin_client.key.public_key_hash())
    print("Deploy JobScheduler")
    job_scheduler_code = ContractInterface.from_file('out/JobScheduler/step_000_cont_0_contract.tz')
    storage = job_scheduler_code.storage.dummy()
    storage['admin'] = pytezos_admin_client.key.public_key_hash()
    
    
    operation_group = pytezos_admin_client.origination(script=job_scheduler_code.script(initial_storage=storage)).send()
    job_scheduler_address = get_address(operation_group.hash())
    print("done: '{}'".format(job_scheduler_address))

if __name__ == '__main__':
    main()