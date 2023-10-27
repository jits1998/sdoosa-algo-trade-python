import math
import threading
import uuid
import time
import logging
import calendar
import psycopg2

from datetime import datetime, timedelta
from py_vollib.black_scholes.implied_volatility import implied_volatility
from py_vollib.black_scholes.greeks.analytical import delta, gamma, rho, theta, vega

from config.Config import getHolidays
from models.Direction import Direction
from ordermgmt.Order import Order
from trademgmt.Trade import Trade
from trademgmt.TradeState import TradeState

class Utils:
  dateFormat = "%Y-%m-%d"
  timeFormat = "%H:%M:%S"
  dateTimeFormat = "%Y-%m-%d %H:%M:%S"

  @staticmethod
  def roundOff(price): # Round off to 2 decimal places
    return round(price, 2)
    
  @staticmethod
  def roundToNSEPrice(price, tick_size = 0.05):
    return max(round(tick_size * math.ceil(price/tick_size), 2),0.05) if price != 0 else 0

  @staticmethod
  def isMarketOpen():
    if Utils.isTodayHoliday():
      return False
    now = datetime.now()
    marketStartTime = Utils.getMarketStartTime()
    marketEndTime = Utils.getMarketEndTime()
    return now >= marketStartTime and now <= marketEndTime

  @staticmethod
  def isMarketClosedForTheDay():
    # This method returns true if the current time is > marketEndTime
    # Please note this will not return true if current time is < marketStartTime on a trading day
    if Utils.isTodayHoliday():
      return True
    now = datetime.now()
    marketEndTime = Utils.getMarketEndTime()
    return now > marketEndTime

  @staticmethod
  def waitTillMarketOpens(context):
    nowEpoch = Utils.getEpoch(datetime.now())
    marketStartTimeEpoch = Utils.getEpoch(Utils.getMarketStartTime())
    waitSeconds = marketStartTimeEpoch - nowEpoch
    if waitSeconds > 0:
      logging.info("%s: Waiting for %d seconds till market opens...", context, waitSeconds)
      time.sleep(waitSeconds)

  @staticmethod
  def getEpoch(datetimeObj = None):
    # This method converts given datetimeObj to epoch seconds
    if datetimeObj == None:
      datetimeObj = datetime.now()
    epochSeconds = datetime.timestamp(datetimeObj)
    return int(epochSeconds) # converting double to long

  @staticmethod
  def getMarketStartTime(dateTimeObj = None):
    return Utils.getTimeOfDay(9, 15, 0, dateTimeObj)

  @staticmethod
  def getMarketEndTime(dateTimeObj = None):
    return Utils.getTimeOfDay(15, 30, 0, dateTimeObj)

  @staticmethod
  def getTimeOfDay(hours, minutes, seconds, dateTimeObj = None):
    if dateTimeObj == None:
      dateTimeObj = datetime.now()
    dateTimeObj = dateTimeObj.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
    return dateTimeObj

  @staticmethod
  def getTimeOfToDay(hours, minutes, seconds):
    return Utils.getTimeOfDay(hours, minutes, seconds, datetime.now())

  @staticmethod
  def getTodayDateStr():
    return Utils.convertToDateStr(datetime.now())

  @staticmethod
  def convertToDateStr(datetimeObj):
    return datetimeObj.strftime(Utils.dateFormat)

  @staticmethod
  def isHoliday(datetimeObj):
    dayOfWeek = calendar.day_name[datetimeObj.weekday()]
    if dayOfWeek == 'Saturday' or dayOfWeek == 'Sunday':
      return True

    dateStr = Utils.convertToDateStr(datetimeObj)
    holidays = getHolidays()
    if (dateStr in holidays):
      return True
    else:
      return False

  @staticmethod
  def isTodayHoliday():
    return Utils.isHoliday(datetime.now())
    
  @staticmethod
  def generateTradeID():
    return str(uuid.uuid4())

  @staticmethod
  def calculateTradePnl(trade):
    if trade.tradeState == TradeState.ACTIVE:
      if trade.cmp > 0:
        if trade.direction == Direction.LONG:
          trade.pnl = Utils.roundOff(trade.filledQty * (trade.cmp - trade.entry))
        else:  
          trade.pnl = Utils.roundOff(trade.filledQty * (trade.entry - trade.cmp))
    else:
      if trade.exit > 0:
        if trade.direction == Direction.LONG:
          trade.pnl = Utils.roundOff(trade.filledQty * (trade.exit - trade.entry))
        else:  
          trade.pnl = Utils.roundOff(trade.filledQty * (trade.entry - trade.exit))
    tradeValue = trade.entry * trade.filledQty
    if tradeValue > 0:
      trade.pnlPercentage = Utils.roundOff(trade.pnl * 100 / tradeValue)

    return trade

  @staticmethod
  def prepareMonthlyExpiryFuturesSymbol(inputSymbol, expiryDay = 2):
    expiryDateTime = Utils.getMonthlyExpiryDayDate(expiryDay=expiryDay)
    expiryDateMarketEndTime = Utils.getMarketEndTime(expiryDateTime)
    now = datetime.now()
    if now > expiryDateMarketEndTime:
      # increasing today date by 20 days to get some day in next month passing to getMonthlyExpiryDayDate()
      expiryDateTime = Utils.getMonthlyExpiryDayDate(now + timedelta(days=20),expiryDay)
    year2Digits = str(expiryDateTime.year)[2:]
    monthShort = calendar.month_name[expiryDateTime.month].upper()[0:3]
    futureSymbol = inputSymbol + year2Digits + monthShort + 'FUT'
    logging.info('prepareMonthlyExpiryFuturesSymbol[%s] = %s', inputSymbol, futureSymbol)  
    return futureSymbol

  @staticmethod
  def prepareWeeklyOptionsSymbol(inputSymbol, strike, optionType, numWeeksPlus = 0, expiryDay = 2):
    expiryDateTime = Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDay=expiryDay)
    # Check if monthly and weekly expiry same
    if inputSymbol == "BANKNIFTY":
      expiryDateTimeMonthly = Utils.getMonthlyExpiryDayDate(expiryDay=3)
    else:
      expiryDateTimeMonthly = Utils.getMonthlyExpiryDayDate(expiryDay=expiryDay)
    weekAndMonthExpriySame = False
    if expiryDateTime == expiryDateTimeMonthly or expiryDateTimeMonthly == Utils.getTimeOfDay(0, 0, 0, datetime.now()):
      expiryDateTime = expiryDateTimeMonthly
      weekAndMonthExpriySame = True
      logging.debug('Weekly and Monthly expiry is same for %s', expiryDateTime)

    todayMarketStartTime = Utils.getMarketStartTime()
    expiryDayMarketEndTime = Utils.getMarketEndTime(expiryDateTime)
    if numWeeksPlus > 0:
      expiryDateTime = expiryDateTime + timedelta(days=numWeeksPlus * 7)
      expiryDateTime = Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDateTime, expiryDay)
    if todayMarketStartTime > expiryDayMarketEndTime:
      expiryDateTime = expiryDateTime + timedelta(days=6)
      expiryDateTime = Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDateTime, expiryDay)
    
    year2Digits = str(expiryDateTime.year)[2:]
    optionSymbol = None
    if weekAndMonthExpriySame == True:
      monthShort = calendar.month_name[expiryDateTime.month].upper()[0:3]
      optionSymbol = inputSymbol + str(year2Digits) + monthShort + str(strike) + optionType.upper()
    else:
      m = expiryDateTime.month
      d = expiryDateTime.day
      mStr = str(m)
      if m == 10:
        mStr = "O"
      elif m == 11:
        mStr = "N"
      elif m == 12:
        mStr = "D"
      dStr = ("0" + str(d)) if d < 10 else str(d)
      optionSymbol = inputSymbol + str(year2Digits) + mStr + dStr + str(strike) + optionType.upper()
    # logging.info('prepareWeeklyOptionsSymbol[%s, %d, %s, %d] = %s', inputSymbol, strike, optionType, numWeeksPlus, optionSymbol)  
    return optionSymbol

  @staticmethod
  def getStrikeFromSymbol(symbol):
    return int(symbol[-7:-2])

  @staticmethod
  def getTypeFromSymbol(symbol):
    return symbol[-2:-1]

  @staticmethod
  def getMonthlyExpiryDayDate(datetimeObj = None, expiryDay = 3):
    if datetimeObj == None:
      datetimeObj = datetime.now()
    year = datetimeObj.year
    month = datetimeObj.month
    lastDay = calendar.monthrange(year, month)[1] # 2nd entry is the last day of the month
    datetimeExpiryDay = datetime(year, month, lastDay)
    while datetimeExpiryDay.weekday() != expiryDay:
      datetimeExpiryDay = datetimeExpiryDay - timedelta(days=1)
    while Utils.isHoliday(datetimeExpiryDay) == True:
      datetimeExpiryDay = datetimeExpiryDay - timedelta(days=1)

    datetimeExpiryDay = Utils.getTimeOfDay(0, 0, 0, datetimeExpiryDay)
    return datetimeExpiryDay

  @staticmethod
  def getWeeklyExpiryDayDate(inputSymbol, dateTimeObj = None, expiryDay = 2):

    if inputSymbol == "BANKNIFTY":
      expiryDateTimeMonthly = Utils.getMonthlyExpiryDayDate(expiryDay = 3)
    else:
      expiryDateTimeMonthly = Utils.getMonthlyExpiryDayDate(expiryDay = expiryDay)
    
    if expiryDateTimeMonthly == Utils.getTimeOfDay(0, 0, 0, datetime.now()):  
      datetimeExpiryDay = expiryDateTimeMonthly
    else:
      if dateTimeObj == None:
        dateTimeObj = datetime.now()
      daysToAdd = 0
      if dateTimeObj.weekday() > expiryDay:
        daysToAdd = 7 - (dateTimeObj.weekday() - expiryDay)
      else:
        daysToAdd = expiryDay - dateTimeObj.weekday()
      datetimeExpiryDay = dateTimeObj + timedelta(days=daysToAdd)
      while Utils.isHoliday(datetimeExpiryDay) == True:
        datetimeExpiryDay = datetimeExpiryDay - timedelta(days=1)

      datetimeExpiryDay = Utils.getTimeOfDay(0, 0, 0, datetimeExpiryDay)

    if inputSymbol == "BANKNIFTY" and expiryDay == 2:
      expiryDateTimeMonthly = Utils.getMonthlyExpiryDayDate(expiryDay = expiryDay)
      if datetimeExpiryDay == expiryDateTimeMonthly:
        # weekly and monthly expiry same, thus BN expiry on thu
        datetimeExpiryDay = Utils.getMonthlyExpiryDayDate(expiryDay=3)
        logging.debug('Weekly and Monthly expiry is same for %s', datetimeExpiryDay)

    return datetimeExpiryDay

  @staticmethod
  def isTodayWeeklyExpiryDay(inputSymbol, expiryDay = 2):
    expiryDate = Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDay=expiryDay)
    todayDate = Utils.getTimeOfToDay(0, 0, 0)
    if expiryDate == todayDate:
      return True
    return False

  @staticmethod
  def isTodayOneDayBeforeWeeklyExpiryDay(inputSymbol, expiryDay = 2):
    return Utils.findNumberOfDaysBeforeWeeklyExpiryDay(inputSymbol, expiryDay) == 1

  @staticmethod
  def findNumberOfDaysBeforeWeeklyExpiryDay(inputSymbol, expiryDay = 2):
    
    if Utils.isTodayWeeklyExpiryDay(inputSymbol, expiryDay=expiryDay):
      return 0

    expiryDate = Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDay=expiryDay)
    dateTimeObj = Utils.getTimeOfToDay(0, 0, 0)
    currentWeekTradingDates = []

    while dateTimeObj < expiryDate:

      if Utils.isHoliday(dateTimeObj):
        dateTimeObj += timedelta(days = 1)
        continue

      currentWeekTradingDates.append(dateTimeObj)
      dateTimeObj += timedelta(days = 1)
    return len(currentWeekTradingDates)

  @staticmethod
  def getNearestStrikePrice(price, nearestMultiple = 50):
    inputPrice = int(price)
    remainder = int(inputPrice % nearestMultiple)
    if remainder < int(nearestMultiple / 2):
      return inputPrice - remainder
    else:
      return inputPrice + (nearestMultiple - remainder)
    
  @staticmethod
  def getOrderStrength(quote, direction):
    if direction == Direction.SHORT:
      return quote.totalSellQuantity / quote.totalBuyQuantity
    else:
      return quote.totalBuyQuantity / quote.totalSellQuantity
    
  @staticmethod
  def getVIXAdjustment(short_code):
    return math.pow(Utils.getTradeManager(short_code).symbolToCMPMap["INDIA VIX"]/16, 0.5)

  @staticmethod
  def getUnderlyingBasedSL(inputSymbol, underLyingPrice, strikePrice, quote, percentageUnderlying, type, expiryDay=2):
    percentageUnderlying = (1 + 0/100) * percentageUnderlying #adjust for vix
    greeks = Utils.greeks(quote, Utils.getWeeklyExpiryDayDate(inputSymbol, expiryDay = expiryDay), underLyingPrice, strikePrice, 0.1, type)
    return underLyingPrice*abs(greeks['Delta'])*percentageUnderlying/100

  @staticmethod
  def greeks(premium, expiry, asset_price, strike_price, intrest_rate, instrument_type):
    # t = ((datetime(expiry.year, expiry.month, expiry.day, 15, 30) - datetime(2021, 7, 8, 10, 15, 19))/timedelta(days=1))/365
    t = ((datetime(expiry.year, expiry.month, expiry.day, 15, 30) - datetime.now())/timedelta(days=1))/365
    S = asset_price
    K = strike_price
    r = intrest_rate
    flag = instrument_type[0].lower()
    imp_v = implied_volatility(premium, S, K, t, r, flag)
    return {
            "IV": imp_v,
            "Delta": delta(flag, S, K, t, r, imp_v),
            #"Gamma": gamma(flag, S, K, t, r, imp_v),
            #"Rho": rho(flag, S, K, t, r, imp_v),
            #"Theta": theta(flag, S, K, t, r, imp_v),
            "Vega": vega(flag, S, K, t, r, imp_v)
            }

  @staticmethod
  def getTradeManager(short_code = None):
    if not short_code:
      short_code = Utils.getShortCode()
    for t in threading.enumerate():
      if t.getName() == short_code:
        return t
    return None

  @staticmethod
  def getShortCode():
    if threading.current_thread().getName().find("_") > -1:
      return  threading.current_thread().getName().split("_")[0]
    else:
      return threading.current_thread().getName()

  @staticmethod
  def convertJSONToOrder(jsonData):
    if jsonData == None:
        return None
    order = Order()
    order.tradingSymbol = jsonData['tradingSymbol']
    order.exchange = jsonData['exchange']
    order.productType = jsonData['productType']
    order.orderType = jsonData['orderType']
    order.price = jsonData['price']
    order.triggerPrice = jsonData['triggerPrice']
    order.qty = jsonData['qty']
    order.orderId = jsonData['orderId']
    order.orderStatus = jsonData['orderStatus']
    order.averagePrice = jsonData['averagePrice']
    order.filledQty = jsonData['filledQty']
    order.pendingQty = jsonData['pendingQty']
    order.orderPlaceTimestamp = jsonData['orderPlaceTimestamp']
    order.lastOrderUpdateTimestamp = jsonData['lastOrderUpdateTimestamp']
    order.message = jsonData['message']
    order.parentOrderId = jsonData.get('parent_order_id','')
    return order

  @staticmethod
  def convertJSONToTrade(jsonData):
    trade = Trade(jsonData['tradingSymbol'])
    trade.tradeID = jsonData['tradeID']
    trade.strategy = jsonData['strategy']
    trade.direction = jsonData['direction']
    trade.productType = jsonData['productType']
    trade.isFutures = jsonData['isFutures']
    trade.isOptions = jsonData['isOptions']
    trade.optionType = jsonData['optionType']
    trade.underLying = jsonData.get('underLying', "")
    trade.placeMarketOrder = jsonData['placeMarketOrder']
    trade.intradaySquareOffTimestamp = jsonData['intradaySquareOffTimestamp']
    trade.requestedEntry = jsonData['requestedEntry']
    trade.entry = jsonData['entry']
    trade.qty = jsonData['qty']
    trade.filledQty = jsonData['filledQty']
    trade.initialStopLoss = jsonData['initialStopLoss']
    trade.stopLoss = jsonData['_stopLoss']
    trade.stopLossPercentage = jsonData.get('stopLossPercentage', 0)
    trade.stopLossUnderlyingPercentage = jsonData.get('stopLossUnderlyingPercentage', 0)
    trade.target = jsonData['target']
    trade.cmp = jsonData['cmp']
    trade.tradeState = jsonData['tradeState']
    trade.timestamp = jsonData['timestamp']
    trade.createTimestamp = jsonData['createTimestamp']
    trade.startTimestamp = jsonData['startTimestamp']
    trade.endTimestamp = jsonData['endTimestamp']
    trade.pnl = jsonData['pnl']
    trade.pnlPercentage = jsonData['pnlPercentage']
    trade.exit = jsonData['exit']
    trade.exitReason = jsonData['exitReason']
    trade.exchange = jsonData['exchange']
    for entryOrder in jsonData['entryOrder']:
      trade.entryOrder.append(Utils.convertJSONToOrder(entryOrder))
    for slOrder in jsonData['slOrder']:
      trade.slOrder.append(Utils.convertJSONToOrder(slOrder))
    for trargetOrder in jsonData['targetOrder']:
      trade.targetOrder.append(Utils.convertJSONToOrder(trargetOrder))
    return trade

  @staticmethod
  def getQuestDBConnection(short_code):
    try:
      connection = psycopg2.connect(user = "admin", password = "quest", host = "127.0.0.1", port = "8812", database = "qdb")
      cursor = connection.cursor()
      
      cursor.execute('''CREATE TABLE IF NOT EXISTS {0} ( ts TIMESTAMP, strategy string, tradingSymbol string, tradeId string, cmp float, entry float, pnl float, qty int, status string) timestamp(ts) partition by year'''.format(short_code))
      cursor.execute('''CREATE TABLE IF NOT EXISTS {0}_tickData( ts TIMESTAMP, tradingSymbol string, ltp float, qty int, avgPrice float, volume int, totalBuyQuantity int, totalSellQuantity int, open float, high float, low float, close float, change float) timestamp(ts) partition by year'''.format(short_code))
    
      logging.info("Connected to Quest DB")
      return cursor
    except Exception as err:
      logging.info("Can't connect to QuestDB")
      return None
    
  @staticmethod
  def getHighestPrice(short_code, startTimestamp, endTimestamp, tradingSymbol):
    try:
      cursor = Utils.getQuestDBConnection(short_code)

      query = "select max(ltp) from '{0}_tickData' where ts BETWEEN to_timestamp('{1}', 'yyyy-MM-dd HH:mm:ss') AND to_timestamp('{2}', 'yyyy-MM-dd HH:mm:ss') AND tradingSymbol = '{3}';"\
              .format(short_code, startTimestamp.strftime("%Y-%m-%d %H:%M:%S"), endTimestamp.strftime("%Y-%m-%d %H:%M:%S"), tradingSymbol)
      cursor.execute(query)
      result = cursor.fetchone()
      return result[0]
    
    except Exception as err:
      logging.info("Unable to fetch data from QuestDB", str(err))
      return None
    
  def getLowestPrice(short_code, startTimestamp, endTimestamp, tradingSymbol):
    try:
      cursor = Utils.getQuestDBConnection(short_code)
      query = "select min(ltp) from '{0}_tickData' where ts BETWEEN to_timestamp('{1}', 'yyyy-MM-dd HH:mm:ss') AND to_timestamp('{2}', 'yyyy-MM-dd HH:mm:ss') AND tradingSymbol = '{3}';"\
                .format(short_code, startTimestamp.strftime("%Y-%m-%d %H:%M:%S"), endTimestamp.strftime("%Y-%m-%d %H:%M:%S"), tradingSymbol)
      cursor.execute(query)
      result = cursor.fetchone()
      return result[0]
    except Exception as err:
      logging.info("Unable to fetch data from QuestDB", str(err))
      return None
    

