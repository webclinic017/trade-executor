"""Test default routing options."""
import pytest
from tradingstrategy.chain import ChainId

from tradeexecutor.ethereum.routing_data import get_routing_model, MismatchReserveCurrency
from tradeexecutor.ethereum.uniswap_v2_routing import UniswapV2SimpleRoutingModel
from tradeexecutor.strategy.default_routing_options import TradeRouting
from tradeexecutor.strategy.execution_context import ExecutionContext, ExecutionMode
from tradeexecutor.strategy.reserve_currency import ReserveCurrency


@pytest.fixture()
def execution_context() -> ExecutionContext:
    return ExecutionContext(ExecutionMode.unit_testing_trading)


def test_route_pancakeswap_busd(execution_context):
    """Test Pancake BUSD routing."""
    routing = get_routing_model(execution_context, TradeRouting.pancakeswap_busd, ReserveCurrency.busd)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.bsc

def test_route_pancakeswap_usdc(execution_context):
    """Test Pancake USDC routing."""
    routing = get_routing_model(execution_context, TradeRouting.pancakeswap_usdc, ReserveCurrency.usdc)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.bsc

def test_route_pancakeswap_usdt(execution_context):
    """Test Pancake USDT routing."""
    routing = get_routing_model(execution_context, TradeRouting.pancakeswap_usdt, ReserveCurrency.usdt)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.bsc

def test_route_quickswap_usdt(execution_context):
    """Test Quickswap USDC routing."""
    routing = get_routing_model(execution_context, TradeRouting.quickswap_usdc, ReserveCurrency.usdc)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.polygon

def test_route_quickswap_usdt(execution_context):
    """Test Quickswap USDT routing."""
    routing = get_routing_model(execution_context, TradeRouting.quickswap_usdt, ReserveCurrency.usdt)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.polygon

def test_route_quickswap_dai(execution_context):
    """Test Quickswap DAI routing."""
    routing = get_routing_model(execution_context, TradeRouting.quickswap_dai, ReserveCurrency.dai)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.polygon

def test_route_trader_joe_usdc(execution_context):
    """Test Trader Joe USDC routing."""
    routing = get_routing_model(execution_context, TradeRouting.trader_joe_usdc, ReserveCurrency.usdc)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.avalanche

def test_route_trader_joe_usdt(execution_context):
    """Test Trader Joe USDT routing."""
    routing = get_routing_model(execution_context, TradeRouting.trader_joe_usdt, ReserveCurrency.usdt)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.avalanche

def test_route_ethereum_usdc(execution_context):
    """Test Uniswap v2 USDC routing."""
    routing = get_routing_model(execution_context, TradeRouting.uniswap_v2_usdc, ReserveCurrency.usdc)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.ethereum

def test_route_ethereum_usdt(execution_context):
    """Test Uniswap v2 USDT routing."""
    routing = get_routing_model(execution_context, TradeRouting.uniswap_v2_usdt, ReserveCurrency.usdt)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.ethereum

def test_route_ethereum_dai(execution_context):
    """Test Uniswap v2 DAI routing."""
    routing = get_routing_model(execution_context, TradeRouting.uniswap_v2_dai, ReserveCurrency.dai)
    assert isinstance(routing, UniswapV2SimpleRoutingModel)
    assert routing.chain_id == ChainId.ethereum

def test_route_mismatch_reserve_currency_pancake(execution_context):
    """Test Pancake BUSD routing."""
    with pytest.raises(MismatchReserveCurrency):
        get_routing_model(execution_context, TradeRouting.pancakeswap_busd, ReserveCurrency.usdc)

def test_route_mismatch_reserve_currency_quickswap(execution_context):
    """Test Quickswap USDC routing."""
    with pytest.raises(MismatchReserveCurrency):
        get_routing_model(execution_context, TradeRouting.quickswap_usdc, ReserveCurrency.usdt)

def test_route_mismatch_reserve_currency_trader_joe(execution_context):
    """Test Trader Joe USDC routing."""
    with pytest.raises(MismatchReserveCurrency):
        get_routing_model(execution_context, TradeRouting.trader_joe_usdc, ReserveCurrency.usdt)



