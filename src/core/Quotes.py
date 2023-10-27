from requests.exceptions import ReadTimeout

import logging

from core.Controller import Controller
from models.Quote import Quote
from kiteconnect.exceptions import DataException

class Quotes:
  @staticmethod
  def getQuote(tradingSymbol, short_code, isFnO = False):
    broker = Controller.getBrokerName(short_code)
    brokerHandle = Controller.getBrokerLogin(short_code).getBrokerHandle()
    quote = None
    if broker == "zerodha":
      key = ('NFO:' + tradingSymbol) if isFnO == True else ('NSE:' + tradingSymbol)
      quote = Quote(tradingSymbol)

      bQuoteResp = Quotes._getQuote(brokerHandle, key)

      bQuote = bQuoteResp[key]
      
      # convert broker quote to our system quote
      quote.tradingSymbol = tradingSymbol
      quote.lastTradedPrice = bQuote['last_price']
      quote.lastTradedQuantity = bQuote['last_quantity']
      quote.avgTradedPrice = bQuote['average_price']
      quote.volume = bQuote['volume']
      quote.totalBuyQuantity = bQuote['buy_quantity']
      quote.totalSellQuantity = bQuote['sell_quantity']
      ohlc = bQuote['ohlc']
      quote.open = ohlc['open']
      quote.high = ohlc['high']
      quote.low = ohlc['low']
      quote.close = ohlc['close']
      quote.change = bQuote['net_change']
      quote.oiDayHigh = bQuote['oi_day_high']
      quote.oiDayLow = bQuote['oi_day_low']
      quote.oi = bQuote['oi']
      quote.lowerCiruitLimit = bQuote['lower_circuit_limit']
      quote.upperCircuitLimit = bQuote['upper_circuit_limit']
    else:
      # The logic may be different for other brokers
      quote = None
    return quote

  @staticmethod
  def getCMP(tradingSymbol, short_code):
    quote = Quotes.getQuote(tradingSymbol, short_code)
    if quote:
      return quote.lastTradedPrice
    else:
      return 0

  @staticmethod
  def getIndexQuote(tradingSymbol, short_code):
    broker = Controller.getBrokerName(short_code)
    brokerHandle = Controller.getBrokerLogin(short_code).getBrokerHandle()
    quote = None
    if broker == "zerodha":
      key = 'NSE:' + tradingSymbol

      bQuoteResp = Quotes._getQuote(brokerHandle, key)

      

      bQuote = bQuoteResp[key]
      # convert broker quote to our system quote
      quote = Quote(tradingSymbol)
      quote.tradingSymbol = tradingSymbol
      quote.lastTradedPrice = bQuote['last_price']
      ohlc = bQuote['ohlc']
      quote.open = ohlc['open']
      quote.high = ohlc['high']
      quote.low = ohlc['low']
      quote.close = ohlc['close']
      quote.change = bQuote['net_change']
    else:
      # The logic may be different for other brokers
      quote = None
    return quote
  
  @staticmethod
  def _getQuote(brokerHandle, key):
    retry = True
    bQuoteResp = None

    while retry:
      retry = False
      try: 
        bQuoteResp = brokerHandle.quote(key)
      except DataException as de:
        if de.code in [503,502]:
          retry = True  
      except ReadTimeout:
        retry = True
      if retry:
        import time
        time.sleep(1)
        logging.info("retrying getQuote after 1 s for %s", key)
    return bQuoteResp