import smartpy as sp

import oracles.constants as Constants
from oracles.job_scheduler import JobScheduler
from oracles.generic_oracle import PriceOracle, LegacyProxyOracle, ProxyOracle, RelativeProxyOracle
from oracles.lp_oracle import LPPriceOracle

def main():
    """
    This file is used for compiling all contract such that the :obj:`oracles.deployment` module can then be used to deploy and wire everything.
    """
    sp.add_compilation_target("JobScheduler", JobScheduler(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83')))
    sp.add_compilation_target("PriceOracle", PriceOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83')))
    sp.add_compilation_target("LegacyProxyOracle", LegacyProxyOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 'BTC'))
    sp.add_compilation_target("FlippedLegacyProxyOracle", LegacyProxyOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 'BTC', requires_flip=True))

    sp.add_compilation_target("ProxyOracle", ProxyOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 'BTC'))
    sp.add_compilation_target("FlippedProxyOracle", ProxyOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 'BTC', requires_flip=True))
    sp.add_compilation_target("LPPriceOracle", LPPriceOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 8, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), "BTC", requires_flip=False))
    sp.add_compilation_target("FlippedLPPriceOracle", LPPriceOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), 8, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), "BTC", requires_flip=True))
    sp.add_compilation_target("RelativeProxyOracle", RelativeProxyOracle(sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'), "BTC", "XTZ"))
    
if __name__ == '__main__':
    main()