from indicators.boswaves_ema_market_structure import EmaMarketStructureBOSWaves
from indicators.algoalpha_smart_money_breakout import SmartMoneyBreakoutAlgoAlpha
from indicators.confirmation_stack import ConfirmationStackIndicator

ALL_INDICATORS = [
    EmaMarketStructureBOSWaves(),
    SmartMoneyBreakoutAlgoAlpha(),
    ConfirmationStackIndicator(),
]
