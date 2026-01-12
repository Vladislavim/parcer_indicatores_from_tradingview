from indicators.boswaves_ema_market_structure import EmaMarketStructureBOSWaves
from indicators.algoalpha_smart_money_breakout import SmartMoneyBreakoutAlgoAlpha
from indicators.algoalpha_trend_targets import TrendTargetsAlgoAlpha

ALL_INDICATORS = [
    EmaMarketStructureBOSWaves(),
    SmartMoneyBreakoutAlgoAlpha(),
    TrendTargetsAlgoAlpha(),
]
