"""Default routing models for Uniswap v2 like exchange.

Describe which smart contract addresses are used to make a trade.
Map factory addresses, router addresses and quote token addresses.

- This takes one of the default routing options and gives the routing model for it

- The routing model consists of smart contract addresses needed to trade

- Parameters needed for basic routing for an Uniswap v2 compatible exchange:

    - Factory smart contract address

    - Router smart contract address

    - Pair contract "init code hash"

    - Wrapped token address

    - Stablecoin addresses

    - Wrapped token/stablecoin pool address

See also :py:class:`tradeexecutor.strategy.default_routing_options.TradeRouting`
that gives the users the choices for the trade routing options in their strategy module.

"""
from typing import TypedDict, List

from tradingstrategy.chain import ChainId

from tradeexecutor.backtest.backtest_routing import BacktestRoutingModel
from tradeexecutor.ethereum.uniswap_v2_routing import UniswapV2SimpleRoutingModel
from tradeexecutor.strategy.execution_context import ExecutionContext, ExecutionMode
from tradeexecutor.strategy.reserve_currency import ReserveCurrency
from tradeexecutor.strategy.default_routing_options import TradeRouting
from tradeexecutor.strategy.routing import RoutingModel


class RoutingData(TypedDict):
    """Describe raw smart contract order routing data."""

    chain_id: ChainId

    #: Factory contract address -> Tuple (default router address, init code hash)
    factory_router_map: tuple

    #: Token address -> pair address
    allowed_intermediary_pairs: dict

    #: Token address for the reserve currency
    #:
    #: E.g. BUSD, USDC address.
    #: Is given as :py:class:`tradeexecutor.strategy.reserve_currency.ReserveCurrency`
    #: and mapped to an address.
    #:
    reserve_token_address: str

    #: Supported quote token addresses
    #:
    #: Besides reserve currency, we can route three leg trades
    #: through high liquidity pools.
    #: E.g. if we buy XXX/BNB pair we route it through BNB/BUSD
    #: and WBNB would appear here as a supported quote token.
    #:
    #: E.g. (WBNB, BUSD), (WBNB, USDC)
    quote_token_addresses: List[str]


class MismatchReserveCurrency(Exception):
    """Routing table did not except this asset as a reserve currency and cannot route."""


def get_pancake_default_routing_parameters(reserve_currency: ReserveCurrency) -> RoutingData:
    """Generate routing using PancakeSwap v2 router. For the Binance Smart Chain.

    TODO: Polish the interface of this function when we have more strategies
    """

    if reserve_currency == ReserveCurrency.busd:
        # https://tradingstrategy.ai/trading-view/binance/tokens/0xe9e7cea3dedca5984780bafc599bd69add087d56
        reserve_token_address = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WBNB through BUSD:WBNB pool,
            # https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-busd
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",
        }

    elif reserve_currency == ReserveCurrency.usdc:
        # https://tradingstrategy.ai/trading-view/binance/tokens/0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d
        reserve_token_address = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WBNB through USDC:WBNB pool,
            # https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-usdc
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "0xd99c7f6c65857ac913a8f880a4cb84032ab2fc5b",
        }
    elif reserve_currency == ReserveCurrency.usdt:
        # https://tradingstrategy.ai/trading-view/binance/tokens/0x55d398326f99059ff775485246999027b3197955
        reserve_token_address = "0x55d398326f99059ff775485246999027b3197955".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WBNB through USDT:WBNB pool,
            # https://tradingstrategy.ai/trading-view/binance/pancakeswap-v2/bnb-usdt
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "0x16b9a82891338f9ba80e2d6970fdda79d1eb0dae",
        }
    else:
        raise NotImplementedError()


    # Allowed exchanges as factory -> router pairs,
    # by their smart contract addresses
    # init_code_hash: https://bscscan.com/address/0x10ED43C718714eb63d5aA57B78B54704E256024E#code#L298
    factory_router_map = {
        "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73": ("0x10ED43C718714eb63d5aA57B78B54704E256024E", "0x00fb7f630766e6a796048ea87d01acd3068e8ff67d078148a3fa3f4a84f69bd5")
    }

    return {
        "chain_id": ChainId.bsc,
        "factory_router_map": factory_router_map,
        "allowed_intermediary_pairs": allowed_intermediary_pairs,
        "reserve_token_address": reserve_token_address,
        "quote_token_addresses": {
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c", "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", 
            "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d", "0x55d398326f99059ff775485246999027b3197955"
        },
        "trading_fee": 25
    }

def get_quickswap_default_routing_parameters(reserve_currency: ReserveCurrency) -> RoutingData:
    """Generate routing using Trader Joe router. For Polygon chain.

    TODO: Polish the interface of this function when we have more strategies
    """
    if reserve_currency == ReserveCurrency.usdc:
        # https://tradingstrategy.ai/trading-view/polygon/tokens/0x2791bca1f2de4661ed88a30c99a7a9449aa84174
        reserve_token_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WMATIC through USDC:WMATIC pool,
            # https://tradingstrategy.ai/trading-view/polygon/quickswap/matic-usdc
            "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270": "0x6e7a5fafcec6bb1e78bae2a1f0b612012bf14827",
        }
    elif reserve_currency == ReserveCurrency.usdt:
        # https://tradingstrategy.ai/trading-view/polygon/tokens/0xc2132d05d31c914a87c6611c10748aeb04b58e8f
        reserve_token_address = "0xc2132d05d31c914a87c6611c10748aeb04b58e8f".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WMATIC through USDT:WMATIC pool,
            # https://tradingstrategy.ai/trading-view/polygon/quickswap/matic-usdt
            "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270": "0x604229c960e5cacf2aaeac8be68ac07ba9df81c3",
        }
    elif reserve_currency == ReserveCurrency.dai:
        # https://tradingstrategy.ai/trading-view/polygon/tokens/0x8f3cf7ad23cd3cadbd9735aff958023239c6a063
        reserve_token_address = "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route USDC through DAI:UDSC pool,
            # https://tradingstrategy.ai/trading-view/polygon/quickswap/dai-usdc
            "0x2791bca1f2de4661ed88a30c99a7a9449aa84174":"0xf04adbf75cdfc5ed26eea4bbbb991db002036bdd"
        }
    else:    
        raise NotImplementedError()

    # Allowed exchanges as factory -> router pairs,
    # by their smart contract addresses
    # init_code_hash: https://polygonscan.com/address/0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff#code#L297
    factory_router_map = {
        "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32": ("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff", "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f")
    }

    return {
        "chain_id": ChainId.polygon,
        "factory_router_map": factory_router_map,
        "allowed_intermediary_pairs": allowed_intermediary_pairs,
        "reserve_token_address": reserve_token_address,
        "quote_token_addresses": {
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270"
        },
        "trading_fee": 30
    }

def get_trader_joe_default_routing_parameters(reserve_currency: ReserveCurrency) -> RoutingData:
    """Generate routing using Trader Joe router. For the Avalanche C-chain.

    TODO: Polish the interface of this function when we have more strategies
    """

    if reserve_currency == ReserveCurrency.usdc:
        # https://tradingstrategy.ai/trading-view/avalanche/tokens/0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e
        reserve_token_address = "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WAVAX through USDC:WAVAX pool,
            # https://tradingstrategy.ai/trading-view/avalanche/trader-joe/wavax-usdc
            "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7": "0xf4003f4efbe8691b60249e6afbd307abe7758adb",
        }
    elif reserve_currency == ReserveCurrency.usdt:
        # https://tradingstrategy.ai/trading-view/avalanche/tokens/0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7
        reserve_token_address = "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WAVAX through USDT:WAVAX pool,
            # https://tradingstrategy.ai/trading-view/avalanche/trader-joe/usdt-wavax
            "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7": "0xbb4646a764358ee93c2a9c4a147d5aded527ab73",
        }
    else:
        raise NotImplementedError()

    # Allowed exchanges as factory -> router pairs,
    # by their smart contract addresses
    # init_code_hash: https://snowtrace.io/address/0x60aE616a2155Ee3d9A68541Ba4544862310933d4#code#L174 
    factory_router_map = {
        "0x9Ad6C38BE94206cA50bb0d90783181662f0Cfa10": ("0x60aE616a2155Ee3d9A68541Ba4544862310933d4", "0x0bbca9af0511ad1a1da383135cf3a8d2ac620e549ef9f6ae3a4c33c2fed0af91")
    }

    return {
        "chain_id": ChainId.avalanche,
        "factory_router_map": factory_router_map,
        "allowed_intermediary_pairs": allowed_intermediary_pairs,
        "reserve_token_address": reserve_token_address,
        "quote_token_addresses": {
            "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e", "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7" 
            "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
        },
        "trading_fee": 30
    }
    

def get_uniswap_v2_default_routing_parameters(reserve_currency: ReserveCurrency) -> RoutingData:
    """Generate routing using Uniswap v2 router.

    TODO: Polish the interface of this function when we have more strategies
    """

    if reserve_currency == ReserveCurrency.usdc:
        # https://tradingstrategy.ai/trading-view/ethereum/tokens/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
        reserve_token_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WETH through USDC:WETH pool,
            # https://tradingstrategy.ai/trading-view/ethereum/uniswap-v2/eth-usdc
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
        }
    elif reserve_currency == ReserveCurrency.usdt:
        # https://tradingstrategy.ai/trading-view/ethereum/tokens/0xdac17f958d2ee523a2206206994597c13d831ec7
        reserve_token_address = "0xdac17f958d2ee523a2206206994597c13d831ec7".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WETH through USDT:WETH pool,
            # https://tradingstrategy.ai/trading-view/ethereum/uniswap-v2/eth-usdt
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852",
        }
    elif reserve_currency == ReserveCurrency.dai:
        # https://tradingstrategy.ai/trading-view/ethereum/tokens/0x6b175474e89094c44da98b954eedeac495271d0f
        reserve_token_address = "0x6b175474e89094c44da98b954eedeac495271d0f".lower()

        # For three way trades, which pools we can use
        allowed_intermediary_pairs = {
            # Route WETH through DAI:WETH pool,
            # https://tradingstrategy.ai/trading-view/ethereum/uniswap-v2/eth-dai
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":"0xa478c2975ab1ea89e8196811f51a7b7ade33eb11"
        }   
    else:
        raise NotImplementedError()

    # Allowed exchanges as factory -> router pairs,
    # by their smart contract addresses
    # https://docs.uniswap.org/protocol/V2/reference/smart-contracts/factory
    # https://github.com/Uniswap/v2-core/issues/102
    # init_code_hash: https://etherscan.io/address/0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D#code#L700
    factory_router_map = {
        "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f": ("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f")
    }

    return {
        "chain_id": ChainId.ethereum,
        "factory_router_map": factory_router_map,
        "allowed_intermediary_pairs": allowed_intermediary_pairs,
        "reserve_token_address": reserve_token_address,
        # USDC, WETH
        "quote_token_addresses": {
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "0xdac17f958d2ee523a2206206994597c13d831ec7"
        },
        "trading_fee": 30
    }


def create_uniswap_v2_compatible_routing(routing_type: TradeRouting, reserve_currency: ReserveCurrency) -> UniswapV2SimpleRoutingModel:
    """Set up Uniswap v2 compatible routing.

    - This takes one of the default routing options and gives the routing model for it

    - The routing model consists of smart contract addresses needed to trade
    """

    if routing_type == TradeRouting.pancakeswap_busd:
        # pancakeswap on bsc
        if reserve_currency != ReserveCurrency.busd:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.pancakeswap_usdc:
        if reserve_currency != ReserveCurrency.usdc:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.pancakeswap_usdt:
        if reserve_currency != ReserveCurrency.usdt:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.quickswap_usdc:
        # quickswap on polygon
        if reserve_currency != ReserveCurrency.usdc:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.quickswap_usdt:
        if reserve_currency != ReserveCurrency.usdt:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.quickswap_dai:
        if reserve_currency != ReserveCurrency.dai:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.trader_joe_usdc:
        # trader joe on avalanche
        if reserve_currency != ReserveCurrency.usdc:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.trader_joe_usdt:
        if reserve_currency != ReserveCurrency.usdt:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.uniswap_v2_usdc:
        # uniswap v2 on ethereum
        if reserve_currency != ReserveCurrency.usdc:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.uniswap_v2_usdt:
        if reserve_currency != ReserveCurrency.usdt:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    elif routing_type == TradeRouting.uniswap_v2_dai:
        if reserve_currency != ReserveCurrency.dai:
            raise MismatchReserveCurrency(f"Got {routing_type} with {reserve_currency}")
    else:
        # else
        raise NotImplementedError(f"Unknown routing type")

    if routing_type in (TradeRouting.pancakeswap_busd, TradeRouting.pancakeswap_usdc, TradeRouting.pancakeswap_usdt):
        # pancake on bsc
        params = get_pancake_default_routing_parameters(reserve_currency)
    elif routing_type in (TradeRouting.quickswap_usdc, TradeRouting.quickswap_usdt, TradeRouting.quickswap_dai):
        # quickswap on polygon
        params = get_quickswap_default_routing_parameters(reserve_currency)
    elif routing_type in (TradeRouting.trader_joe_usdc, TradeRouting.trader_joe_usdt):
        # trader joe on avalanche
        params = get_trader_joe_default_routing_parameters(reserve_currency)
    elif routing_type in (TradeRouting.uniswap_v2_usdc, TradeRouting.uniswap_v2_usdt, TradeRouting.uniswap_v2_dai):
        # uniswap v2 on eth
        params = get_uniswap_v2_default_routing_parameters(reserve_currency)
    else:
        # else
        raise NotImplementedError()

    routing_model = UniswapV2SimpleRoutingModel(
        params["factory_router_map"],
        params["allowed_intermediary_pairs"],
        params["reserve_token_address"],
        params["chain_id"],
        params["trading_fee"]
    )

    return routing_model



def get_backtest_routing_model(routing_type: TradeRouting, reserve_currency: ReserveCurrency) -> BacktestRoutingModel:
    """Get routing options for backtests.

    At the moment, just create a real router and copy parameters from there.
    """

    real_routing_model = create_uniswap_v2_compatible_routing(routing_type, reserve_currency)

    return BacktestRoutingModel(
        real_routing_model.factory_router_map,
        real_routing_model.allowed_intermediary_pairs,
        real_routing_model.reserve_token_address,
    )


def get_routing_model(
        execution_context: ExecutionContext,
        routing_type: TradeRouting,
        reserve_currency: ReserveCurrency) -> RoutingModel:
    """Create trade routing model for the strategy.

    :param execution_model:
        Either backtest or live

    :param routing_type:
        One of the default routing options, as definedin backtest notebook or strategy module

    :param reserve_currency:
        One of the default reserve currency options, as definedin backtest notebook or strategy module
    """

    if execution_context.mode == ExecutionMode.backtesting:
        return get_backtest_routing_model(routing_type, reserve_currency)
    else:
        return create_uniswap_v2_compatible_routing(routing_type, reserve_currency)
