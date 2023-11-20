import logging
import time
from datetime import datetime

from models.ProductType import ProductType
from models.Quote import Quote
from core.Quotes import Quotes
from trademgmt.Trade import Trade
from trademgmt.TradeExitReason import TradeExitReason
from config.Config import getBrokerAppConfig
from instruments.Instruments import Instruments

from utils.Utils import Utils

class BaseStrategy:
  def __init__(self, name, short_code):
    # NOTE: All the below properties should be set by the Derived Class (Specific to each strategy)
    self.name = name # strategy name
    self.short_code = short_code
    self.enabled = True # Strategy will be run only when it is enabled
    self.productType = ProductType.MIS # MIS/NRML/CNC etc
    self.symbols = [] # List of stocks to be traded under this strategy
    self.slPercentage = 0
    self.targetPercentage = 0
    self.startTimestamp = Utils.getMarketStartTime() # When to start the strategy. Default is Market start time
    self.stopTimestamp = None # This is not square off timestamp. This is the timestamp after which no new trades will be placed under this strategy but existing trades continue to be active.
    self.squareOffTimestamp = None # Square off time
    self.capital = 10000 # Capital to trade (This is the margin you allocate from your broker account for this strategy)
    self.leverage = 1 # 2x, 3x Etc
    self.maxTradesPerDay = 1 # Max number of trades per day under this strategy
    self.isFnO = False # Does this strategy trade in FnO or not
    self.strategySL = 0
    self.strategyTarget = 0
    self.capitalPerSet = 0 # Applicable if isFnO is True (Set means 1CE/1PE or 2CE/2PE etc based on your strategy logic)
    # Register strategy with trade manager
    Utils.getTradeManager(self.short_code).registerStrategy(self)
    # Load all trades of this strategy into self.trades on restart of app
    self.trades = Utils.getTradeManager(self.short_code).getAllTradesByStrategy(self.name)
    self.expiryDay = 2
    self.symbol = "BANKNIFTY"

  def getName(self):
    return self.name

  def isEnabled(self):
    return self.enabled

  def setDisabled(self):
    self.enabled = False

  def getMultiple(self):
    return float(getBrokerAppConfig(self.short_code).get("multiple", 1))

  def getLots(self):
    lots = Utils.getTradeManager(self.short_code).algoConfig.getLots(self.getName(),  self.symbol, self.expiryDay) * self.getMultiple()

    if Utils.isTodayWeeklyExpiryDay("NIFTY", expiryDay = 3) and \
      Utils.isTodayWeeklyExpiryDay("BANKNIFTY", expiryDay = 2) :
      lots = lots * 0.5

    if Utils.isTodayWeeklyExpiryDay("FINNIFTY", expiryDay = 1) and \
      Utils.isTodayWeeklyExpiryDay("BANKNIFTY", expiryDay = 2) :
      lots = lots * 0.5

    if Utils.isTodayWeeklyExpiryDay("NIFTY", expiryDay = 3) and \
      Utils.isTodayWeeklyExpiryDay("FINNIFTY", expiryDay = 1) and \
      Utils.isTodayWeeklyExpiryDay("BANKNIFTY", expiryDay = 2) :
      lots = lots * 0.33

    return int(lots)

  def process(self):
    # Implementation is specific to each strategy - To defined in derived class
    logging.info("BaseStrategy process is called.")
    pass
    
  def isTargetORSLHit(self):
    if self.strategySL == 0 and self.strategyTarget == 0:
      return None

    totalPnl = sum([trade.pnl for trade in self.trades])
    exitTrade = False
    reason = None

    if totalPnl<(self.strategySL*self.getLots()):     
      if self.strategySL < 0 :
        exitTrade = True
        reason = TradeExitReason.STRATEGY_SL_HIT
      if self.strategySL > 0 :
        exitTrade = True
        reason = TradeExitReason.STRATEGY_TRAIL_SL_HIT      
    elif self.strategyTarget > 0 and totalPnl>(self.strategyTarget*self.getLots()):
      self.strategySL = 0.9 * totalPnl/self.getLots() 
      logging.warn("Strategy Target %d hit for %s @ PNL per lot = %d, Updated SL to %d ", self.strategyTarget, self.getName(), totalPnl/self.getLots(), self.strategySL)
      self.strategyTarget = 0 #no more targets, will trail SL
    elif self.strategySL > 0 and self.strategySL * 1.2 < totalPnl/self.getLots():
      self.strategySL = 0.9 * totalPnl/self.getLots()
      logging.warn("Updated Strategy SL for %s to %d @ PNL per lot = %d", self.getName(), self.strategySL, totalPnl/self.getLots())
  
    if exitTrade:
      logging.warn("Strategy SL Hit for %s at %d with PNL per lot = %d", self.getName(), self.strategySL, totalPnl/self.getLots())
      return reason
    else:
      return None

  def calculateCapitalPerTrade(self):
    leverage = self.leverage if self.leverage > 0 else 1
    capitalPerTrade = int(self.capital * leverage / self.maxTradesPerDay)
    return capitalPerTrade

  def calculateLotsPerTrade(self):
    if self.isFnO == False:
      return 0
    # Applicable only for fno
    return int(self.capital / self.capitalPerSet)

  def canTradeToday(self):
    # Derived class should override the logic if the strategy to be traded only on specific days of the week
    return self.getLots()>0
  
  def getVIXThreshold(self):
    return 0

  def run(self):
    # NOTE: This should not be overriden in Derived class
    if self.enabled == False:
      Utils.getTradeManager(self.short_code).deRgisterStrategy(self)
      logging.warn("%s: Not going to run strategy as its not enabled.", self.getName())
      return

    if self.strategySL > 0:
      Utils.getTradeManager(self.short_code).deRgisterStrategy(self)
      logging.warn("Strategy SL should be a -ve number")
      return

    if Utils.isMarketClosedForTheDay():
      logging.warn("%s: Not going to run strategy as market is closed.", self.getName())
      return

    for trade in self.trades:
      if trade.exitReason not in [None, TradeExitReason.SL_HIT, TradeExitReason.TARGET_HIT, TradeExitReason.TRAIL_SL_HIT]:
        return #likely something at strategy level or broker level, won't continue
      

    now = datetime.now()
    if now < Utils.getMarketStartTime():
      Utils.waitTillMarketOpens(self.getName())

    if self.canTradeToday() == False:
      Utils.getTradeManager(self.short_code).deRgisterStrategy(self)
      logging.warn("%s: Not going to run strategy as it cannot be traded today.", self.getName())
      return

    if now < self.startTimestamp:
      waitSeconds = Utils.getEpoch(self.startTimestamp) - Utils.getEpoch(now)
      logging.info("%s: Waiting for %d seconds till startegy start timestamp reaches...", self.getName(), waitSeconds)
      if waitSeconds > 0:
        time.sleep(waitSeconds) 

    if self.getVIXThreshold() > Utils.getTradeManager(self.short_code).symbolToCMPMap["INDIA VIX"]:
      Utils.getTradeManager(self.short_code).deRgisterStrategy(self)
      logging.warn("%s: Not going to conitnue strategy as VIX threshold is not met today.", self.getName())
      return

    self.strategySL = self.strategySL * Utils.getVIXAdjustment(self.short_code)
    self.strategyTarget = self.strategyTarget * Utils.getVIXAdjustment(self.short_code)
     
    # Run in an loop and keep processing
    while True:
      
      if Utils.isMarketClosedForTheDay() or not self.isEnabled():
        logging.warn("%s: Exiting the strategy as market closed or strategy was disabled.", self.getName())
        break

      # Derived class specific implementation will be called when process() is called
      self.process()

      # Sleep and wake up 5s after every 15th second, ie after trade manager has updated trades
      now = datetime.now()
      waitSeconds = 5 - (now.second % 5) + 3
      time.sleep(waitSeconds)

  def shouldPlaceTrade(self, trade, tick):
    # Each strategy should call this function from its own shouldPlaceTrade() method before working on its own logic
    if trade == None:
      return False
    if trade.qty == 0:
      Utils.getTradeManager(self.short_code).disableTrade(trade, 'InvalidQuantity')
      return False

    now = datetime.now()
    if now > self.stopTimestamp:
      Utils.getTradeManager(self.short_code).disableTrade(trade, 'NoNewTradesCutOffTimeReached')
      return False

    numOfTradesPlaced = Utils.getTradeManager(self.short_code).getNumberOfTradesPlacedByStrategy(self.getName())
    if numOfTradesPlaced >= self.maxTradesPerDay:
      Utils.getTradeManager(self.short_code).disableTrade(trade, 'MaxTradesPerDayReached')
      return False

    return True

  def addTradeToList(self, trade):
    if trade != None:
      self.trades.append(trade)

  def getQuote(self, tradingSymbol):
    try :
      return Quotes.getQuote(tradingSymbol, self.short_code, self.isFnO)
    except KeyError as e:
      logging.info("%s::%s: Could not get Quote for %s => %s", self.short_code, self.getName(), tradingSymbol, str(e))
    except Exception as exp:
      logging.info("%s::%s: Could not get Quote for %s => %s", self.short_code, self.getName(), tradingSymbol, str(exp))

    return Quote(tradingSymbol)

  def getTrailingSL(self, trade):
    return 0

  def generateTrade(self, optionSymbol, direction, numLots, lastTradedPrice, slPercentage = 0, slPrice = 0, targetPrice = 0, placeMarketOrder = True):
    trade = Trade(optionSymbol, self.getName())
    trade.isOptions = True
    trade.direction = direction
    trade.productType = self.productType
    trade.placeMarketOrder = placeMarketOrder
    trade.requestedEntry = lastTradedPrice
    trade.timestamp = Utils.getEpoch(self.startTimestamp) # setting this to strategy timestamp

    trade.stopLossPercentage = slPercentage
    trade.stopLoss = slPrice # if set to 0, then set stop loss will be set after entry via trailingSL method
    trade.target = targetPrice 
    
    isd = Instruments.getInstrumentDataBySymbol(optionSymbol) # Get instrument data to know qty per lot
    trade.qty = isd['lot_size'] * numLots

    trade.intradaySquareOffTimestamp = Utils.getEpoch(self.squareOffTimestamp)
    # Hand over the trade to TradeManager
    Utils.getTradeManager(self.short_code).addNewTrade(trade)

  def generateTradeWithSLPrice(self, optionSymbol, direction, numLots, lastTradedPrice, underLying, underLyingStopLossPercentage, placeMarketOrder = True):
    trade = Trade(optionSymbol, self.getName())
    trade.isOptions = True
    trade.direction = direction
    trade.productType = self.productType
    trade.placeMarketOrder = placeMarketOrder
    trade.requestedEntry = lastTradedPrice
    trade.timestamp = Utils.getEpoch(self.startTimestamp) # setting this to strategy timestamp

    trade.underLying = underLying
    trade.stopLossUnderlyingPercentage = underLyingStopLossPercentage
    
    isd = Instruments.getInstrumentDataBySymbol(optionSymbol) # Get instrument data to know qty per lot
    trade.qty = isd['lot_size'] * numLots
    
    trade.stopLoss = 0
    trade.target = 0 # setting to 0 as no target is applicable for this trade

    trade.intradaySquareOffTimestamp = Utils.getEpoch(self.squareOffTimestamp)
    # Hand over the trade to TradeManager
    Utils.getTradeManager(self.short_code).addNewTrade(trade)

  def getStrikeWithNearestPremium(self, optionType, nearestPremium, roundToNearestStrike = 100):
    # Get the nearest premium strike price
    futureSymbol = Utils.prepareMonthlyExpiryFuturesSymbol(self.symbol, self.expiryDay)
    quote = self.getQuote(futureSymbol)
    if quote == None:
      logging.error('%s: Could not get quote for %s', self.getName(), futureSymbol)
      return
    
    strikePrice = Utils.getNearestStrikePrice(quote.lastTradedPrice, roundToNearestStrike)
    premium = -1

    lastPremium = premium
    lastStrike = strikePrice

    while premium < nearestPremium: #check if we need to go ITM
      premium = self.getQuote(Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)).lastTradedPrice
      if optionType == "CE":
        strikePrice = strikePrice - roundToNearestStrike
      else:
        strikePrice = strikePrice + roundToNearestStrike
    
    while True:
      try :
        symbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)
        try :
          Instruments.getInstrumentDataBySymbol(symbol)
        except KeyError:
          logging.info('%s: Could not get instrument for %s', self.getName(), symbol)
          return lastStrike, lastPremium
        
        quote = self.getQuote(symbol)

        if quote.totalSellQuantity == 0 and quote.totalBuyQuantity == 0:
            time.sleep(1)
            quote = self.getQuote(symbol) #lets try one more time.
        
        premium = quote.lastTradedPrice

        if premium > nearestPremium:
          lastPremium = premium
        else:
          # quote.lastTradedPrice < quote.upperCircuitLimit and quote.lastTradedPrice > quote.lowerCiruitLimit and \
          if (lastPremium - nearestPremium) > (nearestPremium - premium) and quote.volume > 0 and \
              quote.totalSellQuantity > 0 and quote.totalBuyQuantity > 0:
            return strikePrice, premium
          else:
            logging.info('%s: Returning previous strike for %s as vol = %s sell = %s buy = %s', self.getName(), symbol, \
                         quote.volume, quote.totalSellQuantity, quote.totalBuyQuantity)
            return lastStrike, lastPremium
            
        lastStrike = strikePrice
        lastPremium = premium

        if optionType == "CE":
          strikePrice = strikePrice + roundToNearestStrike
        else:
          strikePrice = strikePrice - roundToNearestStrike
        time.sleep(1)
      except KeyError:
        return lastStrike, lastPremium
  def getStrikeWithMinimumPremium(self, optionType, minimumPremium, roundToNearestStrike = 100):
    # Get the nearest premium strike price
    futureSymbol = Utils.prepareMonthlyExpiryFuturesSymbol(self.symbol, self.expiryDay)
    quote = self.getQuote(futureSymbol)
    if quote == None:
      logging.error('%s: Could not get quote for %s', self.getName(), futureSymbol)
      return
    
    strikePrice = Utils.getNearestStrikePrice(quote.lastTradedPrice, roundToNearestStrike)
    premium = -1

    lastPremium = premium
    lastStrike = strikePrice

    while premium < minimumPremium: #check if we need to go ITM
      premium = self.getQuote(Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)).lastTradedPrice
      if optionType == "CE":
        strikePrice = strikePrice - roundToNearestStrike
      else:
        strikePrice = strikePrice + roundToNearestStrike
    
    while True:
      try :
        symbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)
        Instruments.getInstrumentDataBySymbol(symbol)
        quote = self.getQuote(symbol)

        if quote.totalSellQuantity == 0 and quote.totalBuyQuantity == 0:
            time.sleep(1)
            quote = self.getQuote(symbol) #lets try one more time.
        
        premium = quote.lastTradedPrice

        if premium < minimumPremium:
          return lastStrike, lastPremium
          
            
        lastStrike = strikePrice
        lastPremium = premium

        if optionType == "CE":
          strikePrice = strikePrice + roundToNearestStrike
        else:
          strikePrice = strikePrice - roundToNearestStrike
        time.sleep(1)
      except KeyError:
        return lastStrike, lastPremium
      
  def getStrikeWithMaximumPremium(self, optionType, maximumPremium, roundToNearestStrike = 100):
    # Get the nearest premium strike price
    futureSymbol = Utils.prepareMonthlyExpiryFuturesSymbol(self.symbol, self.expiryDay)
    quote = self.getQuote(futureSymbol)
    if quote == None:
      logging.error('%s: Could not get quote for %s', self.getName(), futureSymbol)
      return
    
    strikePrice = Utils.getNearestStrikePrice(quote.lastTradedPrice, roundToNearestStrike)
    premium = -1

    lastPremium = premium
    lastStrike = strikePrice

    while premium < maximumPremium: #check if we need to go ITM
      premium = self.getQuote(Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)).lastTradedPrice
      if optionType == "CE":
        strikePrice = strikePrice - roundToNearestStrike
      else:
        strikePrice = strikePrice + roundToNearestStrike
    
    while True:
      try :
        symbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, strikePrice, optionType, expiryDay = self.expiryDay)
        Instruments.getInstrumentDataBySymbol(symbol)
        quote = self.getQuote(symbol)

        if quote.totalSellQuantity == 0 and quote.totalBuyQuantity == 0:
            time.sleep(1)
            quote = self.getQuote(symbol) #lets try one more time.
        
        premium = quote.lastTradedPrice

        if premium < maximumPremium:
          return strikePrice, premium
            
        lastStrike = strikePrice
        lastPremium = premium

        if optionType == "CE":
          strikePrice = strikePrice + roundToNearestStrike
        else:
          strikePrice = strikePrice - roundToNearestStrike
        time.sleep(1)
      except KeyError:
        return lastStrike, lastPremium

      
