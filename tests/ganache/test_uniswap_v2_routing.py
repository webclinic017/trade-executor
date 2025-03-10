"""Uniswap v2 routing model tests.

To run these tests, we need to connect to BNB Chain:

.. code-block::  shell

    export BNB_CHAIN_JSON_RPC="https://bsc-dataseed.binance.org/"
    pytest -k test_uniswap_v2_routing

"""

import datetime
import os
from decimal import Decimal

import flaky
import pytest
from eth_account import Account

from eth_defi.gas import estimate_gas_fees, node_default_gas_price_strategy
from eth_defi.confirmation import wait_transactions_to_complete
from eth_typing import HexAddress, HexStr
from web3 import Web3, HTTPProvider
from web3.contract import Contract

from eth_defi.abi import get_deployed_contract
from eth_defi.ganache import fork_network
from eth_defi.hotwallet import HotWallet
from eth_defi.uniswap_v2.deployment import UniswapV2Deployment, fetch_deployment
from eth_defi.utils import is_localhost_port_listening

from tradeexecutor.ethereum.execution import broadcast_and_resolve
from tradeexecutor.ethereum.tx import TransactionBuilder
from tradeexecutor.ethereum.uniswap_v2_routing import UniswapV2RoutingState, UniswapV2SimpleRoutingModel, OutOfBalance
from tradeexecutor.ethereum.wallet import sync_reserves
from tradeexecutor.state.sync import apply_sync_events
from tradeexecutor.state.portfolio import Portfolio
from tradeexecutor.state.state import State
from tradeexecutor.state.identifier import AssetIdentifier, TradingPairIdentifier
from tradeexecutor.state.position import TradingPosition

from tradeexecutor.cli.log import setup_pytest_logging


# https://docs.pytest.org/en/latest/how-to/skipping.html#skip-all-test-functions-of-a-class-or-module
from tradeexecutor.strategy.trading_strategy_universe import create_pair_universe_from_code
from tradeexecutor.testing.pairuniversetrader import PairUniverseTestTrader
from tradingstrategy.chain import ChainId
from tradingstrategy.pair import PandasPairUniverse


pytestmark = pytest.mark.skipif(os.environ.get("BNB_CHAIN_JSON_RPC") is None, reason="Set BNB_CHAIN_JSON_RPC environment variable to Binance Smart Chain node to run this test")


@pytest.fixture(scope="module")
def logger(request):
    """Setup test logger."""
    return setup_pytest_logging(request)


@pytest.fixture()
def large_busd_holder() -> HexAddress:
    """A random account picked from BNB Smart chain that holds a lot of BUSD.

    This account is unlocked on Ganache, so you have access to good BUSD stash.

    `To find large holder accounts, use bscscan <https://bscscan.com/token/0xe9e7cea3dedca5984780bafc599bd69add087d56#balances>`_.
    """
    # Binance Hot Wallet 6
    return HexAddress(HexStr("0x8894E0a0c962CB723c1976a4421c95949bE2D4E3"))


@pytest.fixture()
def ganache_bnb_chain_fork(logger, large_busd_holder) -> str:
    """Create a testable fork of live BNB chain.

    :return: JSON-RPC URL for Web3
    """

    mainnet_rpc = os.environ["BNB_CHAIN_JSON_RPC"]

    if not is_localhost_port_listening(19999):
        # Start Ganache
        launch = fork_network(
            mainnet_rpc,
            block_time=1,  # Insta mining cannot be done in this test
            evm_version="berlin",  # BSC is not yet London compatible?
            unlocked_addresses=[large_busd_holder],  # Unlock WBNB stealing
            quiet=True,  # Otherwise the Ganache output is millions lines of long
        )
        yield launch.json_rpc_url
        # Wind down Ganache process after the test is complete
        launch.close(verbose=True)
    else:
        # raise AssertionError("ganache zombie detected")

        # Uncomment to test against manually started Ganache
        yield "http://127.0.0.1:19999"


@pytest.fixture
def web3(ganache_bnb_chain_fork: str):
    """Set up a local unit testing blockchain."""
    # https://web3py.readthedocs.io/en/stable/examples.html#contract-unit-tests-in-python
    web3 = Web3(HTTPProvider(ganache_bnb_chain_fork))
    web3.eth.set_gas_price_strategy(node_default_gas_price_strategy)
    return web3


@pytest.fixture
def chain_id(web3):
    return web3.eth.chain_id


@pytest.fixture
def busd_token(web3) -> Contract:
    """BUSD with $4B supply."""
    # https://bscscan.com/address/0xe9e7cea3dedca5984780bafc599bd69add087d56
    token = get_deployed_contract(web3, "ERC20MockDecimals.json", "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56")
    return token


@pytest.fixture
def cake_token(web3) -> Contract:
    """CAKE token."""
    token = get_deployed_contract(web3, "ERC20MockDecimals.json", "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82")
    return token


@pytest.fixture()
def pancakeswap_v2(web3) -> UniswapV2Deployment:
    """Fetch live PancakeSwap v2 deployment.

    See https://docs.pancakeswap.finance/code/smart-contracts for more information
    """
    deployment = fetch_deployment(
        web3,
        "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        # Taken from https://bscscan.com/address/0xca143ce32fe78f1f7019d7d551a6402fc5350c73#readContract
        init_code_hash="0x00fb7f630766e6a796048ea87d01acd3068e8ff67d078148a3fa3f4a84f69bd5",
        )
    return deployment


@pytest.fixture
def wbnb_token(pancakeswap_v2: UniswapV2Deployment) -> Contract:
    return pancakeswap_v2.weth


@pytest.fixture()
def busd_asset(busd_token, chain_id) -> AssetIdentifier:
    return AssetIdentifier(
        chain_id,
        busd_token.address,
        busd_token.functions.symbol().call(),
        busd_token.functions.decimals().call())


@pytest.fixture
def bnb_asset(wbnb_token, chain_id) -> AssetIdentifier:
    return AssetIdentifier(chain_id, wbnb_token.address, wbnb_token.functions.symbol().call(), wbnb_token.functions.decimals().call())


@pytest.fixture
def cake_asset(cake_token, chain_id) -> AssetIdentifier:
    return AssetIdentifier(chain_id, cake_token.address, cake_token.functions.symbol().call(), cake_token.functions.decimals().call())


@pytest.fixture
def cake_bnb_trading_pair_address() -> HexAddress:
    """See https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/cake-bnb."""
    return HexAddress(HexStr("0x0ed7e52944161450477ee417de9cd3a859b14fd0"))


@pytest.fixture
def bnb_busd_trading_pair_address() -> HexAddress:
    """See https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-busd."""
    return HexAddress(HexStr("0x58f876857a02d6762e0101bb5c46a8c1ed44dc16"))


@pytest.fixture()
def hot_wallet(web3: Web3, busd_token: Contract, large_busd_holder: HexAddress) -> HotWallet:
    """Our trading Ethereum account.

    Start with 10,000 USDC cash and 2 BNB.
    """
    account = Account.create()
    web3.eth.send_transaction({"from": large_busd_holder, "to": account.address, "value": 2*10**18})
    tx_hash = busd_token.functions.transfer(account.address, 10_000 * 10**18).transact({"from": large_busd_holder})
    wait_transactions_to_complete(web3, [tx_hash])
    wallet = HotWallet(account)
    wallet.sync_nonce(web3)
    return wallet


@pytest.fixture
def cake_busd_trading_pair(cake_asset, busd_asset, pancakeswap_v2) -> TradingPairIdentifier:
    """Cake-BUSD pair representation in the trade executor domain."""
    return TradingPairIdentifier(
        cake_asset,
        busd_asset,
        "0x804678fa97d91B974ec2af3c843270886528a9E6",  #  https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/cake-busd
        internal_id=1000,  # random number
        internal_exchange_id=1000,  # random number
        exchange_address=pancakeswap_v2.factory.address,
    )


@pytest.fixture
def bnb_busd_trading_pair(bnb_asset, busd_asset, pancakeswap_v2) -> TradingPairIdentifier:
    return TradingPairIdentifier(
        bnb_asset,
        busd_asset,
        "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",  #  https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-busd
        internal_id=1001,  # random number
        internal_exchange_id=1000,  # random number
        exchange_address=pancakeswap_v2.factory.address,
    )


@pytest.fixture
def cake_bnb_trading_pair(cake_asset, bnb_asset, pancakeswap_v2) -> TradingPairIdentifier:
    """Cake-BUSD pair representation in the trade executor domain."""
    return TradingPairIdentifier(
        cake_asset,
        bnb_asset,
        "0x0ed7e52944161450477ee417de9cd3a859b14fd0",  #  https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/cake-bnb
        internal_id=1002,  # random number
        internal_exchange_id=1000,  # random number
        exchange_address=pancakeswap_v2.factory.address,
    )


@pytest.fixture
def pair_universe(cake_busd_trading_pair, bnb_busd_trading_pair, cake_bnb_trading_pair) -> PandasPairUniverse:
    """Pair universe needed for the trade routing."""
    return create_pair_universe_from_code(ChainId.bsc, [cake_busd_trading_pair, bnb_busd_trading_pair, cake_bnb_trading_pair])


@pytest.fixture()
def routing_model(busd_asset):

    # Allowed exchanges as factory -> router pairs
    factory_router_map = {
        # Pancake
        "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73": ("0x10ED43C718714eb63d5aA57B78B54704E256024E", "0x00fb7f630766e6a796048ea87d01acd3068e8ff67d078148a3fa3f4a84f69bd5"),
        # Biswap
        #"0x858e3312ed3a876947ea49d572a7c42de08af7ee": ("0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8", )
        # FSTSwap
        #"0x9A272d734c5a0d7d84E0a892e891a553e8066dce": ("0x1B6C9c20693afDE803B27F8782156c0f892ABC2d", ),
    }

    allowed_intermediary_pairs = {
        # For WBNB pairs route thru (WBNB, BUSD) pool
        # https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-busd
        "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",
    }

    return UniswapV2SimpleRoutingModel(
        factory_router_map,
        allowed_intermediary_pairs,
        reserve_token_address=busd_asset.address)


@pytest.fixture()
def portfolio(web3, hot_wallet, busd_asset) -> Portfolio:
    """A portfolio synced to the hot wallet, starting with 10_000 BUSD."""
    portfolio = Portfolio()
    events = sync_reserves(web3, datetime.datetime.utcnow(), hot_wallet.address, [], [busd_asset])
    assert len(events) > 0
    apply_sync_events(portfolio, events)
    reserve_currency, exchange_rate = portfolio.get_default_reserve_currency()
    assert reserve_currency == busd_asset
    return portfolio


@pytest.fixture
def state(portfolio) -> State:
    """State used in the tests."""
    state = State(portfolio=portfolio)
    return state


# Flaky because Ganache hangs
@flaky.flaky()
def test_simple_routing_one_leg(
        web3,
        hot_wallet,
        busd_asset,
        cake_token,
        routing_model,
        cake_busd_trading_pair,
        pair_universe,
):
    """Make 1x two way trade BUSD -> Cake.

    - Buy Cake with BUSD
    """

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    # Create
    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    txs = routing_model.trade(
        routing_state,
        cake_busd_trading_pair,
        busd_asset,
        100 * 10**18,  # Buy Cake worth of 100 BUSD,
        check_balances=True,
    )

    # We should have 1 approve, 1 swap
    assert len(txs) == 2

    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )

    # Check all transactions succeeded
    for tx in txs:
        assert tx.is_success(), f"Transaction failed: {tx}"

    # We received the tokens we bought
    assert cake_token.functions.balanceOf(hot_wallet.address).call() > 0


def test_simple_routing_buy_sell(
        web3,
        hot_wallet,
        busd_asset,
        cake_asset,
        cake_token,
        busd_token,
        routing_model,
        cake_busd_trading_pair,
        pair_universe,
):
    """Make 2x two way trade BUSD -> Cake -> BUSD."""

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    # Create
    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    txs = routing_model.trade(
        routing_state,
        cake_busd_trading_pair,
        busd_asset,
        100 * 10**18,  # Buy Cake worth of 100 BUSD,
        check_balances=True,
    )

    # We should have 1 approve, 1 swap
    assert len(txs) == 2

    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )

    assert all([tx.is_success() for tx in txs])

    # We received the tokens we bought
    cake_balance = cake_token.functions.balanceOf(hot_wallet.address).call()

    # Sell Cake we received
    txs = routing_model.trade(
        routing_state,
        cake_busd_trading_pair,
        cake_asset,
        cake_balance,  # Sell all cake
        check_balances=True,
    )
    assert len(txs) == 2
    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )
    assert all([tx.is_success() for tx in txs])

    # We started with 10_000 BUSD
    balance = busd_token.functions.balanceOf(hot_wallet.address).call()
    assert balance == pytest.approx(9999500634326300440503)


def test_simple_routing_not_enough_balance(
        web3,
        hot_wallet,
        busd_asset,
        routing_model,
        cake_busd_trading_pair,
):
    """Try to buy, but does not have cash."""

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    # Create
    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    with pytest.raises(OutOfBalance):
        routing_model.trade(
            routing_state,
            cake_busd_trading_pair,
            busd_asset,
            1_000_000_000 * 10**18,  # Buy Cake worth of 10B BUSD,
            check_balances=True,
        )


def test_simple_routing_three_leg(
        web3,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        routing_model,
        cake_bnb_trading_pair,
        bnb_busd_trading_pair,
        pair_universe,
):
    """Make 1x two way trade BUSD -> BNB -> Cake."""

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    txs = routing_model.trade(
        routing_state,
        cake_bnb_trading_pair,
        busd_asset,
        100 * 10**18,  # Buy Cake worth of 100 BUSD,
        check_balances=True,
        intermediary_pair=bnb_busd_trading_pair,
    )

    # We should have 1 approve, 1 swap
    assert len(txs) == 2

    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )

    # Check all transactions succeeded
    for tx in txs:
        assert tx.is_success(), f"Transaction failed: {tx}"

    # We received the tokens we bought
    assert cake_token.functions.balanceOf(hot_wallet.address).call() > 0


def test_three_leg_buy_sell(
        web3,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        busd_token,
        routing_model,
        cake_bnb_trading_pair,
        bnb_busd_trading_pair,
        pair_universe,
):
    """Make trades BUSD -> BNB -> Cake and Cake -> BNB -> BUSD."""

    # We start without Cake
    balance = cake_token.functions.balanceOf(hot_wallet.address).call()
    assert balance == 0

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    txs = routing_model.trade(
        routing_state,
        cake_bnb_trading_pair,
        busd_asset,
        100 * 10**18,  # Buy Cake worth of 100 BUSD,
        check_balances=True,
        intermediary_pair=bnb_busd_trading_pair,
    )

    # We should have 1 approve, 1 swap
    assert len(txs) == 2

    # # Check for three legs
    buy_tx = txs[1]
    path = buy_tx.args[2]
    assert len(path) == 3

    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )

    # Check all transactions succeeded
    for tx in txs:
        assert tx.is_success(), f"Transaction failed: {tx}"

    # We received the tokens we bought
    balance = cake_token.functions.balanceOf(hot_wallet.address).call()
    assert balance > 0

    txs = routing_model.trade(
        routing_state,
        cake_bnb_trading_pair,
        cake_asset,
        balance,
        check_balances=True,
        intermediary_pair=bnb_busd_trading_pair,
    )

    # We should have 1 approve, 1 swap
    assert len(txs) == 2

    # Check for three legs
    sell_tx = txs[1]
    path = sell_tx.args[2]
    assert len(path) == 3, f"Bad sell tx {sell_tx}"

    # Execute
    tx_builder.broadcast_and_wait_transactions_to_complete(
        web3,
        txs,
        revert_reasons=True
    )

    # Check all transactions succeeded
    for tx in txs:
        assert tx.is_success(), f"Transaction failed: {tx}"

    # We started with 10_000 BUSD
    balance = busd_token.functions.balanceOf(hot_wallet.address).call()
    assert balance == pytest.approx(9999003745120046326850)


def test_three_leg_buy_sell_twice_on_chain(
        web3,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        busd_token,
        routing_model,
        cake_bnb_trading_pair,
        bnb_busd_trading_pair,
        pair_universe,
):
    """Make trades 2x BUSD -> BNB -> Cake and Cake -> BNB -> BUSD.

    Because we do the round trip 2x, we should not need approvals
    on the second time and we need one less transactions.

    We reset the routing state between, forcing
    the routing state to read the approval information
    back from the chain.
    """

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    routing_state = None

    def trip():

        txs = routing_model.trade(
            routing_state,
            cake_bnb_trading_pair,
            busd_asset,
            100 * 10**18,  # Buy Cake worth of 100 BUSD,
            check_balances=True,
            intermediary_pair=bnb_busd_trading_pair,
        )

        # Execute
        tx_builder.broadcast_and_wait_transactions_to_complete(
            web3,
            txs,
            revert_reasons=True
        )

        # Check all transactions succeeded
        for tx in txs:
            assert tx.is_success(), f"Transaction failed: {tx}"

        # We received the tokens we bought
        balance = cake_token.functions.balanceOf(hot_wallet.address).call()
        assert balance > 0

        txs2 = routing_model.trade(
            routing_state,
            cake_bnb_trading_pair,
            cake_asset,
            balance,
            check_balances=True,
            intermediary_pair=bnb_busd_trading_pair,
        )


        # Execute
        tx_builder.broadcast_and_wait_transactions_to_complete(
            web3,
            txs2,
            revert_reasons=True
        )

        # Check all transactions succeeded
        for tx in txs2:
            assert tx.is_success(), f"Transaction failed: {tx}"

        return txs + txs2

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)
    txs_1 = trip()
    assert len(txs_1) == 4
    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)
    txs_2 = trip()
    assert len(txs_2) == 2


def test_three_leg_buy_sell_twice(
        web3,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        busd_token,
        routing_model,
        cake_bnb_trading_pair,
        bnb_busd_trading_pair,
        pair_universe,
):
    """Make trades 2x BUSD -> BNB -> Cake and Cake -> BNB -> BUSD.

    Because we do the round trip 2x, we should not need approvals
    on the second time and we need one less transactions.
    """

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(
        web3,
        hot_wallet,
        fees,
    )

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    def trip():

        txs = routing_model.trade(
            routing_state,
            cake_bnb_trading_pair,
            busd_asset,
            100 * 10**18,  # Buy Cake worth of 100 BUSD,
            check_balances=True,
            intermediary_pair=bnb_busd_trading_pair,
        )

        # Execute
        tx_builder.broadcast_and_wait_transactions_to_complete(
            web3,
            txs,
            revert_reasons=True
        )

        # Check all transactions succeeded
        for tx in txs:
            assert tx.is_success(), f"Transaction failed: {tx}"

        # We received the tokens we bought
        balance = cake_token.functions.balanceOf(hot_wallet.address).call()
        assert balance > 0

        txs2 = routing_model.trade(
            routing_state,
            cake_bnb_trading_pair,
            cake_asset,
            balance,
            check_balances=True,
            intermediary_pair=bnb_busd_trading_pair,
        )

        # Execute
        tx_builder.broadcast_and_wait_transactions_to_complete(
            web3,
            txs2,
            revert_reasons=True
        )

        # Check all transactions succeeded
        for tx in txs2:
            assert tx.is_success(), f"Transaction failed: {tx}"

        return txs + txs2

    txs_1 = trip()
    assert len(txs_1) == 4
    txs_2 = trip()
    assert len(txs_2) == 2


# Flaky becaues Ganache hangs
@flaky.flaky()
def test_stateful_routing_three_legs(
        web3,
        pair_universe,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        routing_model,
        cake_bnb_trading_pair,
        bnb_busd_trading_pair,
        state: State,
):
    """Perform 3-leg buy/sell using RoutingModel.execute_trades().

    This also shows how blockchain native transactions
    and state management integrate.
    """

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(web3, hot_wallet, fees)

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    trader = PairUniverseTestTrader(state)

    reserve = pair_universe.get_token(busd_asset.address)
    if not reserve:
        all_tokens = pair_universe.get_all_tokens()
        assert reserve, f"Reserve asset {busd_asset.address} missing in the universe {busd_asset}, we have {all_tokens}"

    # Buy Cake via BUSD -> BNB pool for 100 USD
    trades = [
        trader.buy(cake_bnb_trading_pair, Decimal(100))
    ]

    t = trades[0]
    assert t.is_buy()
    assert t.reserve_currency == busd_asset
    assert t.pair == cake_bnb_trading_pair


    state.start_trades(datetime.datetime.utcnow(), trades)
    routing_model.execute_trades_internal(pair_universe, routing_state, trades, check_balances=True)
    broadcast_and_resolve(web3, state, trades, stop_on_execution_failure=True)

    # Check all all trades and transactions completed
    for t in trades:
        assert t.is_success()
        for tx in t.blockchain_transactions:
            assert tx.is_success()

    # We received the tokens we bought
    assert cake_token.functions.balanceOf(hot_wallet.address).call() > 0

    cake_position: TradingPosition = state.portfolio.open_positions[1]
    assert cake_position

    # Buy Cake via BUSD -> BNB pool for 100 USD
    trades = [
        trader.sell(cake_bnb_trading_pair, cake_position.get_quantity())
    ]

    t = trades[0]
    assert t.is_sell()
    assert t.reserve_currency == busd_asset
    assert t.pair == cake_bnb_trading_pair
    assert t.planned_quantity == -cake_position.get_quantity()

    state.start_trades(datetime.datetime.utcnow(), trades)
    routing_model.execute_trades_internal(pair_universe, routing_state, trades, check_balances=True)
    broadcast_and_resolve(web3, state, trades, stop_on_execution_failure=True)

    # Check all all trades and transactions completed
    for t in trades:
        assert t.is_success()
        for tx in t.blockchain_transactions:
            assert tx.is_success()

    # On-chain balance is zero after the sell
    assert cake_token.functions.balanceOf(hot_wallet.address).call() == 0


def test_stateful_routing_two_legs(
        web3,
        pair_universe,
        hot_wallet,
        busd_asset,
        bnb_asset,
        cake_asset,
        cake_token,
        routing_model,
        cake_busd_trading_pair,
        state: State,
):
    """Perform 2-leg buy/sell using RoutingModel.execute_trades().

    This also shows how blockchain native transactions
    and state management integrate.

    Routing is abstracted away - this test is not different from one above,
    except for the trading pair that we have changed.
    """

    # Get live fee structure from BNB Chain
    fees = estimate_gas_fees(web3)

    # Prepare a transaction builder
    tx_builder = TransactionBuilder(web3, hot_wallet, fees)

    routing_state = UniswapV2RoutingState(pair_universe, tx_builder)

    trader = PairUniverseTestTrader(state)

    # Buy Cake via BUSD -> BNB pool for 100 USD
    trades = [
        trader.buy(cake_busd_trading_pair, Decimal(100))
    ]

    t = trades[0]
    assert t.is_buy()
    assert t.reserve_currency == busd_asset
    assert t.pair == cake_busd_trading_pair

    state.start_trades(datetime.datetime.utcnow(), trades)
    routing_model.execute_trades_internal(pair_universe, routing_state, trades, check_balances=True)
    broadcast_and_resolve(web3, state, trades, stop_on_execution_failure=True)

    # Check all all trades and transactions completed
    for t in trades:
        assert t.is_success()
        for tx in t.blockchain_transactions:
            assert tx.is_success()

    # We received the tokens we bought
    assert cake_token.functions.balanceOf(hot_wallet.address).call() > 0

    cake_position: TradingPosition = state.portfolio.open_positions[1]
    assert cake_position

    # Buy Cake via BUSD -> BNB pool for 100 USD
    trades = [
        trader.sell(cake_busd_trading_pair, cake_position.get_quantity())
    ]

    t = trades[0]
    assert t.is_sell()
    assert t.reserve_currency == busd_asset
    assert t.pair == cake_busd_trading_pair
    assert t.planned_quantity == -cake_position.get_quantity()

    state.start_trades(datetime.datetime.utcnow(), trades)
    routing_model.execute_trades_internal(pair_universe, routing_state, trades, check_balances=True)
    broadcast_and_resolve(web3, state, trades, stop_on_execution_failure=True)

    # Check all all trades and transactions completed
    for t in trades:
        assert t.is_success()
        for tx in t.blockchain_transactions:
            assert tx.is_success()

    # On-chain balance is zero after the sell
    assert cake_token.functions.balanceOf(hot_wallet.address).call() == 0

