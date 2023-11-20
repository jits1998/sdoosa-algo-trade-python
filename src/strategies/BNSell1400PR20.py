from datetime import datetime

from models.Direction import Direction
from models.ProductType import ProductType
from core.BaseStrategy import BaseStrategy
from utils.Utils import Utils
from trademgmt.TradeState import TradeState

# Each strategy has to be derived from BaseStrategy
class BNSell1400PR20(BaseStrategy):
  __instance = {}

  @staticmethod
  def getInstance(short_code): # singleton class
    if BNSell1400PR20.__instance.get(short_code, None) == None:
      BNSell1400PR20()
    return BNSell1400PR20.__instance[short_code]

  def __init__(self, short_code, multiple = 0):
    if BNSell1400PR20.__instance.get(short_code, None) != None:
      raise Exception("This class is a singleton!")
    else:
      BNSell1400PR20.__instance[short_code] = self
    # Call Base class constructor
    super().__init__("BNSell1400PR20", short_code, multiple)
    # Initialize all the properties specific to this strategy
    self.productType = ProductType.MIS
    self.slPercentage = 0
    self.targetPercentage = 0
    self.startTimestamp = Utils.getTimeOfToDay(14, 00, 0) # When to start the strategy. Default is Market start time
    self.stopTimestamp = Utils.getTimeOfToDay(15, 24, 0) # This is not square off timestamp. This is the timestamp after which no new trades will be placed under this strategy but existing trades continue to be active.
    self.squareOffTimestamp = Utils.getTimeOfToDay(15, 24, 0) # Square off time
    self.capital = 500000 # Capital to trade (This is the margin you allocate from your broker account for this strategy)
    self.leverage = 0
    self.ceTrades = []
    self.peTrades = []
    self.maxCETradesPerDay = 2
    self.maxPETradesPerDay = 2
    self.maxTradesPerDay = self.maxCETradesPerDay + self.maxPETradesPerDay # (2 CE + 2 PE) Max number of trades per day under this strategy
    self.isFnO = True # Does this strategy trade in FnO or not
    self.capitalPerSet = 150000 # Applicable if isFnO is True (1 set means 1CE/1PE or 2CE/2PE etc based on your strategy logic)
    self.strategySL = 0
    self.strategyTarget = 0
    self.symbol = "BANKNIFTY"
    for trade in self.trades:
      if(trade.tradingSymbol.endswith("CE")):
        self.ceTrades.append(trade)
      else:
        self.peTrades.append(trade)

  def process(self):
    now = datetime.now()
    if now < self.startTimestamp or not self.isEnabled():
      return
    
    if len(self.ceTrades) >= int(self.maxCETradesPerDay) and len(self.peTrades) >= int(self.maxPETradesPerDay) :
        return
        
    if self.isTargetORSLHit():
      #self.setDisabled()
      return
    
    activeCETrade = 0
    activePETrade = 0
    for trade in self.ceTrades:
      if trade.tradingSymbol.endswith("CE") and trade.tradeState in (TradeState.ACTIVE, TradeState.CREATED):
        activeCETrade +=1
    for trade in self.peTrades:
      if trade.tradingSymbol.endswith("PE") and trade.tradeState in (TradeState.ACTIVE, TradeState.CREATED):
        activePETrade  +=1

    takeCETrade = False
    takePETrade = False

    if activeCETrade == 0 and len(self.ceTrades)<int(self.maxCETradesPerDay):
      takeCETrade = True

    if activePETrade == 0 and len(self.peTrades)<int(self.maxPETradesPerDay):
      takePETrade = True

    if takeCETrade:
      ceStrike, cePremium = self.getStrikeWithMaximumPremium("CE", 20)
      CESymbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, ceStrike, 'CE', expiryDay=self.expiryDay)
      self.generateTrade(CESymbol, Direction.SHORT, self.getLots(), cePremium)

    if takePETrade:
      peStrike, pePremium = self.getStrikeWithMaximumPremium("PE", 20)
      PESymbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, peStrike, 'PE', expiryDay=self.expiryDay)
      self.generateTrade(PESymbol, Direction.SHORT, self.getLots(), pePremium)
    
  def addTradeToList(self, trade):
    if trade != None:
      self.trades.append(trade)
      if(trade.tradingSymbol.endswith("CE")) :
        self.ceTrades.append(trade)
      else:
        self.peTrades.append(trade)
  
  def getTrailingSL(self, trade):
    if trade.entry > 0 and trade.stopLoss == 0:
      slPercentage = 40
      return Utils.roundToNSEPrice(trade.entry + trade.entry * slPercentage / 100)
    return 0