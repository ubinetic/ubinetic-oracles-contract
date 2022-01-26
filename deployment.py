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
    signed_oracle_code = ContractInterface.from_file('out/PriceOracle/step_000_cont_1_contract.tz')
    storage = signed_oracle_code.storage.dummy()

    storage['response_threshold'] = settings.RESPONSE_THRESHOLD
    storage['validity_window_in_epochs'] = 4
    storage['valid_script'] = settings.VALID_SCRIPT
    storage['valid_sources'] = settings.VALID_SOURCES
    storage['administrator'] = administrator

    operation_group = pytezos_admin_client.origination(script=signed_oracle_code.script(initial_storage=storage)).send()
    target_oracle_address = get_address(operation_group.hash())
    print("done: '{}'".format(target_oracle_address))
    return
    print("Deploy JobScheduler")
    job_scheduler_code = ContractInterface.from_file('out/JobScheduler/step_000_cont_0_contract.tz')
    storage = job_scheduler_code.storage.dummy()
    storage['admin'] = pytezos_admin_client.key.public_key_hash()    
    
    operation_group = pytezos_admin_client.origination(script=job_scheduler_code.script(initial_storage=storage)).send()
    job_scheduler_address = get_address(operation_group.hash())
    print("done: '{}'".format(job_scheduler_address))

    print("Deploy LegacyProxies")
    proxy_code = ContractInterface.from_file('out/LegacyProxyOracle/step_000_cont_2_contract.tz')
    storage = proxy_code.storage.dummy()
    storage['oracle'] = settings.SOURCE_ORACLE
    for symbol in settings.SYMBOLS:
        storage['symbol'] = symbol
        operation_group = pytezos_admin_client.origination(script=proxy_code.script(initial_storage=storage)).send()
        job_scheduler_address = get_address(operation_group.hash())
        print("done: '{}'".format(job_scheduler_address))

    print("Deploy FlippedLegacyProxies")
    proxy_code = ContractInterface.from_file('out/FlippedLegacyProxyOracle/step_000_cont_3_contract.tz')
    storage = proxy_code.storage.dummy()
    storage['oracle'] = settings.SOURCE_ORACLE
    for symbol in settings.SYMBOLS:
        storage['symbol'] = symbol
        operation_group = pytezos_admin_client.origination(script=proxy_code.script(initial_storage=storage)).send()
        job_scheduler_address = get_address(operation_group.hash())
        print("done: '{}'".format(job_scheduler_address))

    print("Deploy ProxyProxies")
    proxy_code = ContractInterface.from_file('out/ProxyOracle/step_000_cont_4_contract.tz')
    storage = proxy_code.storage.dummy()
    storage['oracle'] = settings.SOURCE_ORACLE
    for symbol in settings.SYMBOLS:
        storage['symbol'] = symbol
        operation_group = pytezos_admin_client.origination(script=proxy_code.script(initial_storage=storage)).send()
        job_scheduler_address = get_address(operation_group.hash())
        print("done: '{}'".format(job_scheduler_address))
    
    print("Deploy FlippedProxies")
    proxy_code = ContractInterface.from_file('out/FlippedProxyOracle/step_000_cont_5_contract.tz')
    storage = proxy_code.storage.dummy()
    storage['oracle'] = settings.SOURCE_ORACLE
    for symbol in settings.SYMBOLS:
        storage['symbol'] = symbol
        operation_group = pytezos_admin_client.origination(script=proxy_code.script(initial_storage=storage)).send()
        job_scheduler_address = get_address(operation_group.hash())
        print("done: '{}'".format(job_scheduler_address))
if __name__ == '__main__':
    main()