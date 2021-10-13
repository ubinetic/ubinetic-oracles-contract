def get_address(operation_hash):
    while True:
        try:
            opg = pytezos_admin_client.shell.blocks[-50:].find_operation(operation_hash)
            originated_contracts = OperationResult.originated_contracts(opg)
            if len(originated_contracts) >= 1:
                return originated_contracts[0]
        except:
            pass

def wait_applied(operation_hash):
    while True:
        try:
            opg = pytezos_admin_client.shell.blocks[-50:].find_operation(operation_hash)
            originated_contracts = OperationResult.is_applied(opg)
            if originated_contracts:
                time.sleep(5)
                return True
        except:
            pass