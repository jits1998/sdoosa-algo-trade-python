import logging
from datetime import datetime

from core.Quotes import Quotes
from models.Direction import Direction
from models.ProductType import ProductType
from strategies.BaseStrategy import BaseStrategy
from utils.Utils import Utils

# Each strategy has to be derived from BaseStrategy
class RangeBreakOut200CP(BaseStrategy):
  __instance = {}

  @staticmethod
  def getInstance(short_code): # singleton class
    if RangeBreakOut200CP.__instance.get(short_code, None) == None:
      RangeBreakOut200CP()
    return RangeBreakOut200CP.__instance[short_code]

  def __init__(self, short_code):
    if RangeBreakOut200CP.__instance.get(short_code, None) != None:
      raise Exception("This class is a singleton!")
    else:
      RangeBreakOut200CP.__instance[short_code] = self
    # Call Base class constructor
    super().__init__("RangeBreakOut200CP", short_code)
    # Initialize all the properties specific to this strategy
    self.productType = ProductType.MIS
    self.symbols = []
    self.startTimestamp = Utils.getTimeOfToDay(9, 45, 0) # When to start the strategy
    self.rangeBreakOutTimestamp = Utils.getTimeOfToDay(10, 29, 59) # When to range breakout the strategy
    self.stopTimestamp = Utils.getTimeOfToDay(15, 15, 0) # When to stop the strategy
    self.squareOffTimestamp = Utils.getTimeOfToDay(15, 15, 0) # Square off time
    self.maxTradesPerDay = 2 # (1 CE + 1 PE) Max number of trades per day under this strategy
    self.isFnO = True # Does this strategy trade in FnO or not
    self.strategySL = -1200
    self.slPercentage = 0
    self.index = "NIFTY BANK"
    self.indexSymbol = "BANKNIFTY"
    
    self.CESymbol = None
    self.PESymbol = None
    self.ceTrades = []
    self.peTrades = []

  def process(self):
    now = datetime.now()
    if now < self.startTimestamp or not self.isEnabled():
      return

    if len(self.trades) >= self.maxTradesPerDay or not self.isEnabled():
      return
    
    if self.isTargetORSLHit():
      #self.setDisabled()
      return

    if now >= self.startTimestamp and now <= self.rangeBreakOutTimestamp and self.CESymbol is None:
      
      ceStrike, cePremium = self.getStrikeWithMinimumPremium("CE", 200)
      peStrike, pePremium = self.getStrikeWithMinimumPremium("PE", 200)

      self.CESymbol = Utils.prepareWeeklyOptionsSymbol(self.indexSymbol, ceStrike, 'CE')
      self.PESymbol = Utils.prepareWeeklyOptionsSymbol(self.indexSymbol, peStrike, 'PE')

      #register symbols with ticker to track
      Utils.getTradeManager(self.short_code).registerTradingSymbolToTrack([self.CESymbol, self.PESymbol])

    elif now >= self.rangeBreakOutTimestamp:

      if self.CESymbol is not None and len(self.ceTrades) == 0:

        #Get Highest CE price
        highestCEPrice = Utils.getHighestPrice(self.short_code, self.startTimestamp, 
                                              self.rangeBreakOutTimestamp, self.CESymbol)
        lowestCEPrice = Utils.getLowestPrice(self.short_code, self.startTimestamp,
                                              self.rangeBreakOutTimestamp, self.CESymbol)
        
        CERange = highestCEPrice - lowestCEPrice

        if highestCEPrice is not None:
          quote = self.getQuote(self.CESymbol)
          if quote.lastTradedPrice > highestCEPrice:
            highestCEPrice = quote.lastTradedPrice + 0.5
          # Place CE trade
          logging.info("Place CE trade for %s at price %d", self.CESymbol, highestCEPrice + 0.5)
          self.generateTrade(self.CESymbol, Direction.LONG, int(self.getLots()), highestCEPrice + 0.5, placeMarketOrder=False, \
                             slPrice=highestCEPrice + 0.5 - 0.5 * CERange, targetPrice=highestCEPrice + 0.5 + 2 * CERange)
          
      if self.PESymbol is not None and len(self.peTrades) == 0:

        highestPEPrice = Utils.getHighestPrice(self.short_code, self.startTimestamp,
                                              self.rangeBreakOutTimestamp, self.PESymbol)
        lowestPEPrice = Utils.getLowestPrice(self.short_code, self.startTimestamp,
                                              self.rangeBreakOutTimestamp, self.PESymbol)
        PERange = highestPEPrice - lowestPEPrice

        if highestPEPrice is not None:
          quote = self.getQuote(self.PESymbol)
          if quote.lastTradedPrice > highestPEPrice:
            highestPEPrice = quote.lastTradedPrice + 0.5
          # Place PE trade
          logging.info("Place PE trade for %s at price %d", self.PESymbol, highestPEPrice + 0.5)
          self.generateTrade(self.PESymbol, Direction.LONG, int(self.getLots()), highestPEPrice + 0.5, placeMarketOrder=False, \
                              slPrice=highestPEPrice + 0.5 - 0.5 * PERange, targetPrice=highestPEPrice + 0.5 + 2 * PERange)

  def addTradeToList(self, trade):
    if trade != None:
      self.trades.append(trade)
      if trade.tradingSymbol.endswith("CE") :
        self.ceTrades.append(trade)
      elif trade.tradingSymbol.endswith("PE"):
        self.peTrades.append(trade)

  def getTrailingSL(self, trade):
    if trade.entry > 0:
      lastTradedPrice = Utils.getTradeManager(self.short_code).getLastTradedPrice(trade.tradingSymbol)
      if lastTradedPrice == 0:
        return 0
      
      trailSL = 0
      profitPoints = (+1 if trade.direction ==  Direction.SHORT else -1) * int(trade.entry - lastTradedPrice)
      if profitPoints >= trade.entry * 0.1:
        factor = int(profitPoints / (trade.entry * 0.1))
        trailSL = Utils.roundToNSEPrice(trade.initialStopLoss + (-1 if trade.direction ==  Direction.SHORT else +1) * factor * trade.entry * 0.1)
        logging.debug('%s: %s Returning trail SL %f', self.getName(), trade.tradingSymbol, trailSL)
        return trailSL
      
    return 0


  

  

