import smartpy as sp

import oracles.constants as Constants
from oracles.job_scheduler import JobScheduler

def main():
    """
    This file is used for compiling all contract such that the :obj:`oracles.deployment` module can then be used to deploy and wire everything.
    """
    sp.add_compilation_target("JobScheduler", JobScheduler(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83')))
    
if __name__ == '__main__':
    main()