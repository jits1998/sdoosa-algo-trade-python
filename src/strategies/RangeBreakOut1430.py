import logging, calendar
from datetime import datetime
from config.Config import getBrokerAppConfig

from core.Quotes import Quotes
from models.Direction import Direction
from models.ProductType import ProductType
from strategies.BaseStrategy import BaseStrategy
from trademgmt.TradeExitReason import TradeExitReason
from utils.Utils import Utils

# Each strategy has to be derived from BaseStrategy
class RangeBreakOut1430(BaseStrategy):
  __instance = {}

  @staticmethod
  def getInstance(short_code): # singleton class
    if RangeBreakOut1430.__instance.get(short_code, None) == None:
      RangeBreakOut1430()
    return RangeBreakOut1430.__instance[short_code]

  def __init__(self, short_code):
    if RangeBreakOut1430.__instance.get(short_code, None) != None:
      raise Exception("This class is a singleton!")
    else:
      RangeBreakOut1430.__instance[short_code] = self
    # Call Base class constructor
    super().__init__("RangeBreakOut1430", short_code)
    # Initialize all the properties specific to this strategy
    self.productType = ProductType.MIS
    self.symbols = []
    self.startTimestamp = Utils.getTimeOfToDay(14, 25, 0) # When to start the strategy
    self.rangeBreakOutTimestamp = Utils.getTimeOfToDay(14, 56, 59) # When to range breakout the strategy
    self.stopTimestamp = Utils.getTimeOfToDay(15, 15, 0) # When to stop the strategy
    self.squareOffTimestamp = Utils.getTimeOfToDay(15, 15, 0) # Square off time
    self.maxTradesPerDay = 1 # (1 CE + 0 PE) Max number of trades per day under this strategy
    self.isFnO = True # Does this strategy trade in FnO or not
    self.strategySL = 0
    self.slPercentage = 0
    self.index = "NIFTY BANK"
    self.indexSymbol = "BANKNIFTY"
    
    self.ITMCESymbol = None
    self.ceTrades = []

  def process(self):
    now = datetime.now()
    if now < self.startTimestamp or not self.isEnabled():
      return

    if len(self.trades) >= self.maxTradesPerDay or not self.isEnabled():
      return
    
    if self.isTargetORSLHit():
      #self.setDisabled()
      return

    if now >= self.startTimestamp and now <= self.rangeBreakOutTimestamp and self.ITMCESymbol is None:
      
      # Get current market price of Nifty Future
      quote = Quotes.getIndexQuote(self.index, self.short_code)
      if quote == None:
        logging.error('%s: Could not get quote for %s', self.getName(), self.index)
        return
      
      ATMStrike = Utils.getNearestStrikePrice(quote.lastTradedPrice, 100)

      self.ITMCESymbol = Utils.prepareWeeklyOptionsSymbol(self.indexSymbol, ATMStrike - 100, 'CE')

      #register symbols with ticker to track
      Utils.getTradeManager(self.short_code).registerTradingSymbolToTrack([self.ITMCESymbol])

    elif now >= self.rangeBreakOutTimestamp:

      if self.ITMCESymbol is not None and len(self.ceTrades) == 0:

        #Get Highest CE price
        highestCEPrice = Utils.getHighestPrice(self.short_code, self.startTimestamp, 
                                              self.rangeBreakOutTimestamp, self.ITMCESymbol)
        if highestCEPrice is not None:
          quote = self.getQuote(self.ITMCESymbol)
          if quote.lastTradedPrice > highestCEPrice:
            highestCEPrice = quote.lastTradedPrice * 1.01
          # Place CE trade
          logging.info("Place CE trade for %s at price %d", self.ITMCESymbol, highestCEPrice + 0.5)
          self.generateTrade(self.ITMCESymbol, Direction.LONG, int(self.getLots()), highestCEPrice + 0.5, placeMarketOrder=False)

  def addTradeToList(self, trade):
    if trade != None:
      self.trades.append(trade)
      if(trade.tradingSymbol.endswith("CE")) :
        self.ceTrades.append(trade)

  def getTrailingSL(self, trade):
    if trade.entry > 0 and trade.stopLoss == 0:
      slPercentage = 40
      return Utils.roundToNSEPrice(trade.entry - trade.entry * slPercentage / 100)
    return 0


  

  

