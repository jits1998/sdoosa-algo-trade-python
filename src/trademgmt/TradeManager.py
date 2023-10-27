import json
import logging
import os
import time
import traceback

from datetime import datetime
from threading import Thread

import pymongo

from config.Config import getBrokerAppConfig, getServerConfig
from core.Controller import Controller
from models.Direction import Direction
from models.OrderStatus import OrderStatus
from models.OrderType import OrderType
from ordermgmt.OrderInputParams import OrderInputParams
from ordermgmt.OrderModifyParams import OrderModifyParams
from ordermgmt.ZerodhaOrderManager import ZerodhaOrderManager
from ticker.ZerodhaTicker import ZerodhaTicker
from utils.Utils import Utils

import datetime
from datetime import datetime
import pandas as pd
import numpy as np

from trademgmt.TradeEncoder import TradeEncoder
from trademgmt.TradeExitReason import TradeExitReason
from trademgmt.TradeState import TradeState


class TradeManager(Thread):

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None):
        super(TradeManager, self).__init__(
            group=group, target=target, name=name)
        self._accessToken, self.algoConfig, = args
        self.ticker = None
        self.trades = []  # to store all the trades
        self.strategyToInstanceMap = {}
        self.symbolToCMPMap = {}
        self.symboltoTotalSell = {}
        self.symboltoTotalBuy = {}
        self.intradayTradesDir = None
        self.registeredSymbols = []
        self.trackTradingSymbols = []
        self.isReady = False

        self.candleTime = {}
        self.tickStore = {}

    def run(self):
        dburi = 'mongodb://{}:{}@localhost:27017/{}'.format(getBrokerAppConfig(self.getName())['broker'].lower()
                                                            + "_"+getBrokerAppConfig(self.getName())['clientID'], getBrokerAppConfig(self.getName())['appSecret'], self.getName())

        self.dbTrades = pymongo.MongoClient(
            dburi, serverSelectionTimeoutMS=1000, directConnection=True)[self.getName()].trades

        try:
            self.dbTrades.estimated_document_count()
        except (pymongo.errors.ServerSelectionTimeoutError, pymongo.errors.OperationFailure) as ex:
            print("Can't connect to Mongodb server")
            self.dbTrades = None

        self.questDBCursor = Utils.getQuestDBConnection(self.getName())

        Utils.waitTillMarketOpens("TradeManager")
        # check and create trades directory for today`s date
        serverConfig = getServerConfig()
        tradesDir = os.path.join(serverConfig['deployDir'], 'trades')
        self.intradayTradesDir = os.path.join(
            tradesDir, Utils.getTodayDateStr())
        if os.path.exists(self.intradayTradesDir) == False:
            logging.info('TradeManager: Intraday Trades Directory %s does not exist. Hence going to create.',
                         self.intradayTradesDir)
            os.makedirs(self.intradayTradesDir)

        # start ticker service
        brokerName = getBrokerAppConfig(self.getName())['broker']
        if brokerName == "zerodha":
            self.ticker = ZerodhaTicker(self.getName())
        # elif brokerName == "fyers" # not implemented
        # ticker = FyersTicker()

        self.ticker.startTicker(
            getBrokerAppConfig(self.getName())['appKey'], self._accessToken)
        

        # sleep for 2 seconds for ticker connection establishment
        while self.ticker.ticker.ws is None:
            logging.warn('Waiting for ticker connection establishment..')
            time.sleep(2)
        
        self.ticker.registerListener(self.tickerListener)

        self.ticker.registerSymbols(["NIFTY 50", "NIFTY BANK", "INDIA VIX", "NIFTY FIN SERVICE"], mode = "full")

        # Load all trades from json files to app memory
        self.loadAllTradesFromFile()

        # sleep for 2 seconds for ticker to update ltp map
        time.sleep(2)

        # track and update trades in a loop
        while True:

            self.isReady = True

            if self.questDBCursor is None or self.questDBCursor.closed:
                self.questDBCursor = Utils.getQuestDBConnection(self.getName())

            if not Utils.isTodayHoliday() and not Utils.isMarketClosedForTheDay() and not len(self.strategyToInstanceMap) == 0:
                try:
                    # Fetch all order details from broker and update orders in each trade
                    self.fetchAndUpdateAllTradeOrders()
                    # track each trade and take necessary action
                    self.trackAndUpdateAllTrades()

                    # pe_vega = 0
                    # ce_vega = 0
                    # indexSymbol = "NIFTY BANK"
                    # quote = self.symbolToCMPMap.get(indexSymbol, None)
                    # if quote is not None:
                    #     symbolsToTrack = []
                    #     ATMStrike = Utils.getNearestStrikePrice(quote, 100)
                    #     ATMCESymbol = Utils.prepareWeeklyOptionsSymbol("BANKNIFTY", ATMStrike, 'CE')
                    #     ATMPESymbol = Utils.prepareWeeklyOptionsSymbol("BANKNIFTY", ATMStrike, 'PE')
                    #     symbolsToTrack.append(ATMCESymbol)
                    #     symbolsToTrack.append(ATMPESymbol)

                    #     if self.symbolToCMPMap.get(ATMCESymbol, None) is not None:
                    #         greeks = Utils.greeks(self.symbolToCMPMap[ATMCESymbol], Utils.getWeeklyExpiryDayDate(), self.symbolToCMPMap["NIFTY BANK"], ATMStrike, 0.1, "CE")
                    #         ce_vega += greeks['Vega']
                    #     if self.symbolToCMPMap.get(ATMPESymbol, None) is not None:
                    #         greeks = Utils.greeks(self.symbolToCMPMap[ATMPESymbol], Utils.getWeeklyExpiryDayDate(), self.symbolToCMPMap["NIFTY BANK"], ATMStrike, 0.1, "PE")
                    #         pe_vega += greeks['Vega']

                    #     for i in range(10):
                    #         OTMPEStrike = ATMStrike - 100 * i
                    #         OTMCEStrike = ATMStrike + 100 * i
                    #         OTMCESymbol = Utils.prepareWeeklyOptionsSymbol("BANKNIFTY", OTMCEStrike, 'CE')
                    #         OTMPESymbol = Utils.prepareWeeklyOptionsSymbol("BANKNIFTY", OTMPEStrike, 'PE')
                    #         symbolsToTrack.append(OTMCESymbol)
                    #         symbolsToTrack.append(OTMPESymbol)

                    #         if self.symbolToCMPMap.get(OTMCESymbol, None) is not None:
                    #             greeks = Utils.greeks(self.symbolToCMPMap[OTMCESymbol], Utils.getWeeklyExpiryDayDate(), self.symbolToCMPMap["NIFTY BANK"], OTMCEStrike, 0.1, "CE")
                    #             # print("%s : %s" %(OTMCESymbol, greeks))
                    #             ce_vega += greeks['Vega']
                    #         if self.symbolToCMPMap.get(OTMPESymbol, None) is not None:
                    #             greeks = Utils.greeks(self.symbolToCMPMap[OTMPESymbol], Utils.getWeeklyExpiryDayDate(), self.symbolToCMPMap["NIFTY BANK"], OTMPEStrike, 0.1, "PE")
                    #             # print("%s : %s" %(OTMPESymbol, greeks))
                    #             pe_vega += greeks['Vega']
                    #     self.ticker.registerSymbols(symbolsToTrack)

                    self.checkStrategyHealth()
                    # print ( "%s =>%f :: %f" %(datetime.now().strftime("%H:%M:%S"), pe_vega, ce_vega))
                except Exception as e:
                    traceback.print_exc()
                    logging.exception("Exception in TradeManager Main thread")

                # save updated data to json file
                self.saveAllTradesToFile()

            # Sleep and wake up on every 30th second
            now = datetime.now()
            waitSeconds = 5 - (now.second % 5)
            time.sleep(waitSeconds)

    def registerStrategy(self, strategyInstance):
        self.strategyToInstanceMap[strategyInstance.getName(
        )] = strategyInstance

    def deRgisterStrategy(self, strategyInstance):
        del self.strategyToInstanceMap[strategyInstance.getName()]

    def loadAllTradesFromFile(self):
        tradesFilepath = self.getTradesFilepath()
        if os.path.exists(tradesFilepath) == False:
            logging.warn(
                'TradeManager: loadAllTradesFromFile() Trades Filepath %s does not exist', tradesFilepath)
            return
        self.trades = []
        tFile = open(tradesFilepath, 'r')
        tradesData = json.loads(tFile.read())
        for tr in tradesData:
            trade = Utils.convertJSONToTrade(tr)
            if self.dbTrades is not None:
                tradeFound = self.dbTrades.find_one_and_replace(
                    {"tradeID": trade.tradeID}, tr, upsert=True, return_document=pymongo.ReturnDocument.AFTER)
            logging.info('loadAllTradesFromFile trade => %s', trade)
            self.trades.append(trade)
            if trade.tradingSymbol not in self.registeredSymbols:
                # Algo register symbols with ticker
                self.ticker.registerSymbols([trade.tradingSymbol])
                self.registeredSymbols.append(trade.tradingSymbol)
        logging.info('TradeManager: Successfully loaded %d trades from json file %s', len(
            self.trades), tradesFilepath)

    def getTradesFilepath(self):
        tradesFilepath = os.path.join(self.intradayTradesDir, getBrokerAppConfig(self.getName())[
                                      'broker']+'_'+getBrokerAppConfig(self.getName())['clientID']+'.json')
        return tradesFilepath

    def saveAllTradesToFile(self):
        tradesFilepath = self.getTradesFilepath()
        with open(tradesFilepath, 'w') as tFile:
            json.dump(self.trades, tFile, indent=2, cls=TradeEncoder)
        if self.dbTrades is not None:
            for trade in self.trades:
                tradeFound = self.dbTrades.find_one_and_replace({"tradeID": trade.tradeID}, json.loads(
                    json.dumps(trade, cls=TradeEncoder)), upsert=True, return_document=pymongo.ReturnDocument.AFTER)
        logging.debug('TradeManager: Saved %d trades to file %s',
                     len(self.trades), tradesFilepath)

    def addNewTrade(self, trade):
        if trade == None:
            return
        logging.info('TradeManager: addNewTrade called for %s', trade)
        for tr in self.trades:
            if tr.equals(trade):
                logging.warn(
                    'TradeManager: Trade already exists so not adding again. %s', trade)
                return
        # Add the new trade to the list
        self.trades.append(trade)
        logging.info(
            'TradeManager: trade %s added successfully to the list', trade.tradeID)
        # Register the symbol with ticker so that we will start getting ticks for this symbol
        if trade.tradingSymbol not in self.registeredSymbols:
            self.ticker.registerSymbols([trade.tradingSymbol])
            self.registeredSymbols.append(trade.tradingSymbol)
        # Also add the trade to strategy trades list
        strategyInstance = self.strategyToInstanceMap[trade.strategy]
        if strategyInstance != None:
            strategyInstance.addTradeToList(trade)

    def disableTrade(self, trade, reason):
        if trade != None:
            logging.info(
                'TradeManager: Going to disable trade ID %s with the reason %s', trade.tradeID, reason)
            trade.tradeState = TradeState.DISABLED

    def updateCandle(self, tick):
        return
        timenow = datetime.now()
        if self.tickStore.get(tick.tradingSymbol) == None:
            self.tickStore[tick.tradingSymbol] = []
            self.candleTime[tick.tradingSymbol] = None

        if timenow.strftime("%d-%m-%Y %H:%M:00") == self.candleTime[tick.tradingSymbol]:
            self.tickStore[tick.tradingSymbol].append(tick.lastTradedPrice)
        elif int(timenow.strftime("%S")) < 5:

            if self.candleTime[tick.tradingSymbol] is not None:
                x_df = pd.DataFrame(self.tickStore[tick.tradingSymbol])
                x_df.groupby(lambda _: True).agg(
                    open=(0, 'first'),
                    high=(0, np.max),
                    low=(0, np.min),
                    close=(0, 'last')
                )
                # store in quest db self.tickStore[tick.tradingSymbol] self.candleTime[tick.tradingSymbol], open, high, low, close
                self.tickStore[tick.tradingSymbol] = []

            self.candleTime[tick.tradingSymbol] = timenow.strftime(
                "%d-%m-%Y %H:%M:00")

    def tickerListener(self, tick):
        # logging.info('tickerLister: new tick received for %s = %f', tick.tradingSymbol, tick.lastTradedPrice);
        # Store the latest tick in map
        self.symbolToCMPMap[tick.tradingSymbol] = tick.lastTradedPrice
        self.symboltoTotalBuy[tick.tradingSymbol] = tick.totalBuyQuantity
        self.symboltoTotalSell[tick.tradingSymbol] = tick.totalSellQuantity
        if tick.exchange_timestamp:
           self.symbolToCMPMap["exchange_timestamp"] = tick.exchange_timestamp
        self.updateCandle(tick)
        self.storeTickDataInDB(tick)
        # On each new tick, get a created trade and call its strategy whether to place trade or not
        for strategy in self.strategyToInstanceMap:
            longTrade = self.getUntriggeredTrade(
                tick.tradingSymbol, strategy, Direction.LONG)
            shortTrade = self.getUntriggeredTrade(
                tick.tradingSymbol, strategy, Direction.SHORT)
            if longTrade == None and shortTrade == None:
                continue
            strategyInstance = self.strategyToInstanceMap[strategy]
            if longTrade != None:
                if strategyInstance.shouldPlaceTrade(longTrade, tick):
                    # place the longTrade
                    isSuccess = self.executeTrade(longTrade)
                    if isSuccess == True:
                        # set longTrade state to ACTIVE
                        longTrade.tradeState = TradeState.ACTIVE
                        longTrade.startTimestamp = Utils.getEpoch()
                        continue
                    else:
                        longTrade.tradeState = TradeState.DISABLED

            if shortTrade != None:
                if strategyInstance.shouldPlaceTrade(shortTrade, tick):
                    # place the shortTrade
                    isSuccess = self.executeTrade(shortTrade)
                    if isSuccess == True:
                        # set shortTrade state to ACTIVE
                        shortTrade.tradeState = TradeState.ACTIVE
                        shortTrade.startTimestamp = Utils.getEpoch()
                    else:
                        shortTrade.tradeState = TradeState.DISABLED

    def getUntriggeredTrade(self, tradingSymbol, strategy, direction):
        trade = None
        for tr in self.trades:
            if tr.tradeState == TradeState.DISABLED:
                continue
            if tr.tradeState != TradeState.CREATED:
                continue
            if tr.tradingSymbol != tradingSymbol:
                continue
            if tr.strategy != strategy:
                continue
            if tr.direction != direction:
                continue
            trade = tr
            break
        return trade

    def executeTrade(self, trade):
        logging.info('TradeManager: Execute trade called for %s', trade)
        trade.initialStopLoss = trade.stopLoss
        # Create order input params object and place order
        oip = OrderInputParams(trade.tradingSymbol)
        oip.direction = trade.direction
        oip.productType = trade.productType
        oip.orderType = OrderType.LIMIT if trade.placeMarketOrder == True else OrderType.SL_LIMIT
        oip.triggerPrice = Utils.roundToNSEPrice(trade.requestedEntry)
        oip.price = Utils.roundToNSEPrice(trade.requestedEntry *
                                          (1.01 if trade.direction == Direction.LONG else 0.99))
        oip.qty = trade.qty
        oip.tag = trade.strategy
        if trade.isFutures == True or trade.isOptions == True:
            oip.isFnO = True
        try:
            trade.entryOrder.append(self.getOrderManager(
                self.getName()).placeOrder(oip))
        except Exception as e:
            logging.error(
                'TradeManager: Execute trade failed for tradeID %s: Error => %s', trade.tradeID, str(e))
            return False

        logging.info(
            'TradeManager: Execute trade successful for %s and entryOrder %s', trade, trade.entryOrder)
        return True

    def fetchAndUpdateAllTradeOrders(self):
        allOrders = {}
        for trade in self.trades:
            for entryOrder in trade.entryOrder:
                allOrders[entryOrder] = trade.strategy
            for slOrder in trade.slOrder:
                allOrders[slOrder] = trade.strategy
            for targetOrder in trade.targetOrder:
                allOrders[targetOrder] = trade.strategy

        missingOrders = self.getOrderManager(
            self.getName()).fetchAndUpdateAllOrderDetails(allOrders)
        
        #lets find the place for these orders
        for missingOrder in missingOrders: 
            orderParentFound = False     
            for trade in self.trades:
                for entryOrder in trade.entryOrder:
                    if entryOrder.orderId == missingOrder.parentOrderId:
                        trade.entryOrder.append(missingOrder)
                        orderParentFound = True
                for slOrder in trade.slOrder:
                    if slOrder.orderId == missingOrder.parentOrderId:
                        trade.slOrder.append(missingOrder)
                        orderParentFound = True
                for targetOrder in trade.targetOrder:
                    if targetOrder.orderId == missingOrder.parentOrderId:
                        trade.targetOrder.append(missingOrder)
                        orderParentFound = True
                if orderParentFound:
                    break

    def trackAndUpdateAllTrades(self):

        if self.questDBCursor is not None:
            try:
                query = "INSERT INTO '{0}' VALUES('{1}', '{2}', '{3}', '{4}', {5}, {6}, {7}, {8}, '{9}');"\
                    .format(self.getName(), datetime.now(), "Nifty", "NIFTY 50", "",
                            self.getLastTradedPrice("NIFTY 50"), 0, 0, 0, "")
                self.questDBCursor.execute(query)
                query = "INSERT INTO '{0}' VALUES('{1}', '{2}', '{3}', '{4}', {5}, {6}, {7}, {8}, '{9}');"\
                    .format(self.getName(), datetime.now(), "BankNifty", "NIFTY BANK", "",
                            self.getLastTradedPrice("NIFTY BANK"), 0, 0, 0, "")
                self.questDBCursor.execute(query)
                query = "INSERT INTO '{0}' VALUES('{1}', '{2}', '{3}', '{4}', {5}, {6}, {7}, {8}, '{9}');"\
                    .format(self.getName(), datetime.now(), "VIX", "INDIA VIX", "",
                            self.getLastTradedPrice("INDIA VIX"), 0, 0, 0, "")
                self.questDBCursor.execute(query)
                self.questDBCursor.connection.commit()
            except Exception as err:
                logging.error("Error inserting into Quest DB %s", str(err))

        for trade in self.trades:
            if trade.tradeState == TradeState.ACTIVE:
                self.trackEntryOrder(trade)
                self.trackTargetOrder(trade)
                self.trackSLOrder(trade)
                if trade.intradaySquareOffTimestamp != None:
                    nowEpoch = Utils.getEpoch()
                    if nowEpoch >= trade.intradaySquareOffTimestamp:
                        trade.target = self.symbolToCMPMap[trade.tradingSymbol]
                        self.squareOffTrade(
                            trade, TradeExitReason.SQUARE_OFF)

    def checkStrategyHealth(self):
        for strategy in self.strategyToInstanceMap.values():
            if strategy.isEnabled():
                SLorTargetHit = strategy.isTargetORSLHit()
                if(SLorTargetHit is not None):
                    for trade in strategy.trades:
                        if trade.tradeState in (TradeState.ACTIVE):
                            trade.target = self.symbolToCMPMap[trade.tradingSymbol]
                            self.squareOffTrade(trade, SLorTargetHit)
                    strategy.setDisabled()

    def trackEntryOrder(self, trade):
        if trade.tradeState != TradeState.ACTIVE:
            return

        if len(trade.entryOrder) == 0:
            return

        trade.filledQty = 0
        trade.entry = 0
        orderCanceled = 0

        for entryOrder in trade.entryOrder:
            if entryOrder.orderStatus == OrderStatus.CANCELLED or entryOrder.orderStatus == OrderStatus.REJECTED:
                orderCanceled += 1

            if entryOrder.filledQty > 0:
                trade.entry = (trade.entry * trade.filledQty + entryOrder.averagePrice *
                               entryOrder.filledQty) / (trade.filledQty+entryOrder.filledQty)
            elif entryOrder.orderStatus not in [OrderStatus.REJECTED, OrderStatus.CANCELLED] and not entryOrder.orderType in [OrderType.SL_LIMIT]:
                omp = OrderModifyParams()
                if trade.direction == Direction.LONG:
                    omp.newPrice = Utils.roundToNSEPrice(entryOrder.price * 1.01) + 0.05
                else:
                    omp.newPrice = Utils.roundToNSEPrice(entryOrder.price * 0.99) - 0.05
                try:  
                    self.getOrderManager(self.getName()).modifyOrder(
                        entryOrder, omp, trade.qty)
                except Exception as e:
                    if e.args[0] == "Maximum allowed order modifications exceeded.":
                        self.getOrderManager(self.getName()).cancelOrder(entryOrder)
            elif entryOrder.orderStatus in [OrderStatus.TRIGGER_PENDING]:
                nowEpoch = Utils.getEpoch()
                if nowEpoch >= Utils.getEpoch(self.strategyToInstanceMap[trade.strategy].stopTimestamp):
                    self.getOrderManager(self.getName()).cancelOrder(entryOrder)

            trade.filledQty += entryOrder.filledQty

        if orderCanceled == len(trade.entryOrder):
            trade.tradeState = TradeState.CANCELLED

        # Update the current market price and calculate pnl
        trade.cmp = self.symbolToCMPMap[trade.tradingSymbol]
        Utils.calculateTradePnl(trade)

        if self.questDBCursor is None or self.questDBCursor.closed:
            self.questDBCursor = Utils.getQuestDBConnection(self.getName())

        if self.questDBCursor is not None:
            try:
                query = "INSERT INTO '{0}' VALUES('{1}', '{2}', '{3}', '{4}', {5}, {6}, {7}, {8}, '{9}');"\
                    .format(self.getName(), datetime.now(), trade.strategy, trade.tradingSymbol, trade.tradeID,
                            trade.cmp, trade.entry, trade.pnl, trade.qty, trade.tradeState)
                self.questDBCursor.execute(query)
                self.questDBCursor.connection.commit()
            except Exception as err:
                logging.error("Error inserting into Quest DB %s", str(err))

    def trackSLOrder(self, trade):
        if trade.tradeState != TradeState.ACTIVE:
            for entryOrder in trade.entryOrder:
                if entryOrder.orderStatus in [OrderStatus.OPEN, OrderStatus.TRIGGER_PENDING]:
                    return
        if trade.stopLoss == 0:
            # check if stoploss is yet to be calculated
            newSL = self.strategyToInstanceMap.get(
                trade.strategy, None).getTrailingSL(trade)
            if newSL == 0:
                return
            else:
                trade.stopLoss = newSL

        if len(trade.slOrder) == 0 and trade.entry > 0:
            # Place SL order
            self.placeSLOrder(trade)
        else:
            slCompleted = 0
            slAverage = 0
            slQuantity = 0
            slCancelled = 0
            slOpen = 0
            for slOrder in trade.slOrder:
                if slOrder.orderStatus == OrderStatus.COMPLETE:
                    slCompleted+=1
                    slAverage = (slQuantity * slAverage + slOrder.filledQty * slOrder.averagePrice) / (slQuantity+slOrder.filledQty)
                    slQuantity  += slOrder.filledQty
                elif slOrder.orderStatus == OrderStatus.CANCELLED:
                    slCancelled+=1
                elif slOrder.orderStatus == OrderStatus.OPEN:
                    slOpen+=1
                    omp = OrderModifyParams()
                    if trade.direction == Direction.LONG:
                        omp.newTriggerPrice = Utils.roundToNSEPrice(slOrder.price * 0.99) - 0.05
                        omp.newPrice = Utils.roundToNSEPrice(omp.newTriggerPrice * 0.99) - 0.05
                    else:
                        omp.newTriggerPrice = Utils.roundToNSEPrice(slOrder.price * 1.01) + 0.05
                        omp.newPrice = Utils.roundToNSEPrice(omp.newTriggerPrice * 1.01) + 0.05
                        
                        
                    self.getOrderManager(self.getName()).modifyOrder(
                        slOrder, omp, trade.qty)

            if  slCompleted == len(trade.slOrder) and len(trade.slOrder) > 0 :
                # SL Hit
                exit = slAverage
                exitReason = TradeExitReason.SL_HIT if trade.initialStopLoss == trade.stopLoss else TradeExitReason.TRAIL_SL_HIT
                self.setTradeToCompleted(trade, exit, exitReason)
                # Make sure to cancel target order if exists
                self.cancelTargetOrder(trade)

            elif slCancelled ==  len(trade.slOrder) and len(trade.slOrder) > 0 :
                targetOrderPendingCount  = 0
                for targetOrder in trade.targetOrder:
                    if targetOrder.orderStatus not in [OrderStatus.COMPLETE, OrderStatus.OPEN]:
                        targetOrderPendingCount+=1
                if targetOrderPendingCount == len (trade.targetOrder):
                    # Cancel target order if exists
                    self.cancelTargetOrder(trade)
                    # SL order cancelled outside of algo (manually or by broker or by exchange)
                    logging.error('SL order tradeID %s cancelled outside of Algo. Setting the trade as completed with exit price as current market price.',
                                trade.tradeID)
                    exit = self.symbolToCMPMap[trade.tradingSymbol]
                    self.setTradeToCompleted(
                        trade, exit, TradeExitReason.SL_CANCELLED)
            elif slOpen > 0 :
                pass #handled above, skip calling trail SL
            else:
                self.checkAndUpdateTrailSL(trade)

    def checkAndUpdateTrailSL(self, trade):
        # Trail the SL if applicable for the trade
        strategyInstance = self.strategyToInstanceMap.get(
            trade.strategy, None)
        if strategyInstance == None:
            return

        newTrailSL = Utils.roundToNSEPrice(
            strategyInstance.getTrailingSL(trade))
        updateSL = False
        if newTrailSL > 0:
            if trade.direction == Direction.LONG and newTrailSL > trade.stopLoss:
                if newTrailSL < trade.cmp:
                    updateSL = True
                else:
                    logging.info(
                        'TradeManager: Trail SL %f triggered Squareoff at market for tradeID %s', newTrailSL, trade.tradeID)
                    self.squareOffTrade(trade, reason=TradeExitReason.SL_HIT)
            elif trade.direction == Direction.SHORT and newTrailSL < trade.stopLoss:
                if newTrailSL > trade.cmp:
                    updateSL = True
                else:  # in case the SL is called due to all leg squareoff
                    logging.info(
                        'TradeManager: Trail SL %f triggered Squareoff at market for tradeID %s', newTrailSL, trade.tradeID)
                    self.squareOffTrade(trade, reason=TradeExitReason.SL_HIT)
        if updateSL == True:
            omp = OrderModifyParams()
            omp.newTriggerPrice = newTrailSL
            omp.newPrice = Utils.roundToNSEPrice(
                omp.newTriggerPrice * (0.99 if trade.direction == Direction.LONG else 1.01))  # sl order direction is reverse
            try:
                oldSL = trade.stopLoss
                for slOrder in trade.slOrder:
                    self.getOrderManager(self.getName()).modifyOrder(
                        slOrder, omp, trade.qty)
                logging.info('TradeManager: Trail SL: Successfully modified stopLoss from %f to %f for tradeID %s',
                                oldSL, newTrailSL, trade.tradeID)
                # IMPORTANT: Dont forget to update this on successful modification
                trade.stopLoss = newTrailSL
            except Exception as e:
                logging.error('TradeManager: Failed to modify SL order for tradeID %s : Error => %s',
                              trade.tradeID, str(e))

    def trackTargetOrder(self, trade):
        if trade.tradeState != TradeState.ACTIVE and self.strategyToInstanceMap[trade.strategy].isTargetORSLHit() is not None:
            return
        if trade.target == 0:  # Do not place Target order if no target provided
            return
        if len(trade.targetOrder) == 0 and trade.entry > 0 : #place target order only after the entry happened
            # Place Target order
            self.placeTargetOrder(trade)
        else:
            targetCompleted = 0
            targetAverage = 0
            targetQuantity = 0
            targetCancelled = 0
            targetOpen = 0
            for targetOrder in trade.targetOrder:
                if targetOrder.orderStatus == OrderStatus.COMPLETE:
                    targetCompleted+=1
                    targetAverage = (targetQuantity * targetAverage + targetOrder.filledQty * targetOrder.averagePrice) / (targetQuantity+targetOrder.filledQty)
                    targetQuantity  += targetOrder.filledQty
                elif targetOrder.orderStatus == OrderStatus.CANCELLED:
                    targetCancelled+=1
                elif targetOrder.orderStatus == OrderStatus.OPEN and trade.exitReason is not None:
                    targetOpen+=1
                    omp = OrderModifyParams()
                    if trade.direction == Direction.LONG:
                        omp.newTriggerPrice = Utils.roundToNSEPrice(targetOrder.price * 0.99) - 0.05
                        omp.newPrice = Utils.roundToNSEPrice(omp.newTriggerPrice * 0.99) - 0.05
                    else:
                        omp.newTriggerPrice = Utils.roundToNSEPrice(targetOrder.price * 1.01) + 0.05
                        omp.newPrice = Utils.roundToNSEPrice(omp.newTriggerPrice * 1.01) + 0.05
                        
                    self.getOrderManager(self.getName()).modifyOrder(
                        targetOrder, omp, trade.qty)

            if targetCompleted == len(trade.targetOrder) and len(trade.targetOrder) > 0 :
                # Target Hit
                exit = targetAverage
                self.setTradeToCompleted(
                    trade, exit, TradeExitReason.TARGET_HIT)
                # Make sure to cancel sl order
                self.cancelSLOrder(trade)

            elif targetCancelled == len(trade.targetOrder) and len(trade.targetOrder) > 0 :
                # Target order cancelled outside of algo (manually or by broker or by exchange)
                logging.error('Target orderfor tradeID %s cancelled outside of Algo. Setting the trade as completed with exit price as current market price.',
                               trade.tradeID)
                exit = self.symbolToCMPMap[trade.tradingSymbol]
                self.setTradeToCompleted(
                    trade, exit, TradeExitReason.TARGET_CANCELLED)
                # Cancel SL order
                self.cancelSLOrder(trade)

    def placeSLOrder(self, trade):
        oip = OrderInputParams(trade.tradingSymbol)
        oip.direction = Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG
        oip.productType = trade.productType
        oip.orderType = OrderType.SL_LIMIT
        oip.triggerPrice = Utils.roundToNSEPrice(trade.stopLoss)
        oip.price = Utils.roundToNSEPrice(trade.stopLoss *
                                          (0.99 if trade.direction == Direction.LONG else 1.01))
        oip.qty = trade.qty
        oip.tag = trade.strategy
        if trade.isFutures == True or trade.isOptions == True:
            oip.isFnO = True
        try:
            trade.slOrder.append(self.getOrderManager(
                self.getName()).placeOrder(oip))
        except Exception as e:
            logging.error(
                'TradeManager: Failed to place SL order for tradeID %s: Error => %s', trade.tradeID, str(e))
            raise(e)
        logging.info('TradeManager: Successfully placed SL order %s for tradeID %s',
                     trade.slOrder[0].orderId, trade.tradeID)

    def placeTargetOrder(self, trade, isMarketOrder=False):
        oip = OrderInputParams(trade.tradingSymbol)
        oip.direction = Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG
        oip.productType = trade.productType
        # oip.orderType = OrderType.LIMIT if (
        #     trade.placeMarketOrder == True or isMarketOrder) else OrderType.SL_LIMIT
        oip.orderType = OrderType.MARKET if isMarketOrder == True else OrderType.LIMIT
        oip.triggerPrice = Utils.roundToNSEPrice(trade.target)
        oip.price = Utils.roundToNSEPrice(trade.target *
                                          (+ 1.01 if trade.direction == Direction.LONG else 0.99))
        oip.qty = trade.qty
        oip.tag = trade.strategy
        if trade.isFutures == True or trade.isOptions == True:
            oip.isFnO = True
        try:
            trade.targetOrder.append(self.getOrderManager(
                self.getName()).placeOrder(oip))
        except Exception as e:
            logging.error(
                'TradeManager: Failed to place Target order for tradeID %s: Error => %s', trade.tradeID, str(e))
            raise(e)
        logging.info('TradeManager: Successfully placed Target order %s for tradeID %s',
                     trade.targetOrder[0].orderId, trade.tradeID)

    def cancelEntryOrder(self, trade):
        if len(trade.entryOrder) == 0:
            return
        for entryOrder in trade.entryOrder:
            if entryOrder.orderStatus == OrderStatus.CANCELLED:
                continue
            try:
                self.getOrderManager(self.getName()).cancelOrder(entryOrder)
            except Exception as e:
                logging.error('TradeManager: Failed to cancel Entry order %s for tradeID %s: Error => %s',
                              entryOrder.orderId, trade.tradeID, str(e))
                raise(e)
            logging.info('TradeManager: Successfully cancelled Entry order %s for tradeID %s',
                         entryOrder.orderId, trade.tradeID)

    def cancelSLOrder(self, trade):
        if len(trade.slOrder) == 0:
            return
        for slOrder in trade.slOrder:
            if slOrder.orderStatus == OrderStatus.CANCELLED:
                continue
            try:
                self.getOrderManager(self.getName()).cancelOrder(slOrder)
            except Exception as e:
                logging.error('TradeManager: Failed to cancel SL order %s for tradeID %s: Error => %s',
                              slOrder.orderId, trade.tradeID, str(e))
                raise(e)
            logging.info('TradeManager: Successfully cancelled SL order %s for tradeID %s',
                         slOrder.orderId, trade.tradeID)

    def cancelTargetOrder(self, trade):
        if len(trade.targetOrder) == 0:
            return
        for targetOrder in trade.targetOrder:
            if targetOrder.orderStatus == OrderStatus.CANCELLED:
                continue
            try:
                self.getOrderManager(self.getName()).cancelOrder(targetOrder)
            except Exception as e:
                logging.error('TradeManager: Failed to cancel Target order %s for tradeID %s: Error => %s',
                              targetOrder.orderId, trade.tradeID, str(e))
                raise(e)
            logging.info('TradeManager: Successfully cancelled Target order %s for tradeID %s',
                         targetOrder.orderId, trade.tradeID)

    def setTradeToCompleted(self, trade, exit, exitReason=None):
        trade.tradeState = TradeState.COMPLETED
        trade.exit = exit
        trade.exitReason = exitReason if trade.exitReason == None else trade.exitReason
        #TODO Timestamp to be matched with last order
        # if trade.targetOrder != None and trade.targetOrder.orderStatus == OrderStatus.COMPLETE:
        #     trade.endTimestamp = datetime.strptime(
        #         trade.targetOrder.lastOrderUpdateTimestamp, "%Y-%m-%d %H:%M:%S").timestamp()
        # elif trade.slOrder != None and trade.slOrder.orderStatus == OrderStatus.COMPLETE:
        #     trade.endTimestamp = datetime.strptime(
        #         trade.slOrder.lastOrderUpdateTimestamp, "%Y-%m-%d %H:%M:%S").timestamp()
        # else:
        trade.endTimestamp = Utils.getEpoch()

        trade = Utils.calculateTradePnl(trade)

        if self.questDBCursor is None or self.questDBCursor.closed:
            self.questDBCursor = Utils.getQuestDBConnection(self.getName())

        if self.questDBCursor is not None:
            try:
                query = "INSERT INTO '{0}' VALUES('{1}', '{2}', '{3}', '{4}', {5}, {6}, {7}, {8}, '{9}');"\
                    .format(self.getName(), datetime.now(), trade.strategy, trade.tradingSymbol, trade.tradeID,
                            trade.cmp, trade.entry, trade.pnl, trade.qty, trade.tradeState)
                self.questDBCursor.execute(query)
                self.questDBCursor.connection.commit()
            except Exception as err:
                logging.error("Error inserting into Quest DB %s", str(err))

        logging.info('TradeManager: setTradeToCompleted strategy = %s, symbol = %s, qty = %d, entry = %f, exit = %f, pnl = %f, exit reason = %s',
                     trade.strategy, trade.tradingSymbol, trade.filledQty, trade.entry, trade.exit, trade.pnl, trade.exitReason)

    def squareOffTrade(self, trade, reason=TradeExitReason.SQUARE_OFF):
        logging.info(
            'TradeManager: squareOffTrade called for tradeID %s with reason %s', trade.tradeID, reason)
        if trade == None or trade.tradeState != TradeState.ACTIVE:
            return

        trade.exitReason = reason
        if len(trade.entryOrder) > 0:  
            for entryOrder in trade.entryOrder:
                if entryOrder.orderStatus in [OrderStatus.OPEN, OrderStatus.TRIGGER_PENDING]:
                    # Cancel entry order if it is still open (not filled or partially filled case)
                    self.cancelEntryOrder(trade)
                    break

        if len(trade.slOrder) > 0:
            try:
                self.cancelSLOrder(trade)
            except Exception:
                #probably the order is being processed.
                logging.info('TradeManager: squareOffTrade couldn\'t cancel SL order for %s, not placing target order, strategy will be disabled',
                         trade.tradeID)
                return


        if len(trade.targetOrder) > 0:
            # Change target order type to MARKET to exit position immediately
            logging.info('TradeManager: changing target order to MARKET to exit position for tradeID %s',
                         trade.tradeID)
            for targetOrder in trade.targetOrder:
                if targetOrder.orderStatus == OrderStatus.OPEN:
                    omp = OrderModifyParams()
                    omp.newPrice = Utils.roundToNSEPrice(
                        trade.cmp * (0.99 if trade.direction == Direction.LONG else 1.01))
                    self.getOrderManager(self.getName()).modifyOrder(
                        targetOrder, omp, trade.qty)
        else:
            # Place new target order to exit position, adjust target to current market price
            trade.target = trade.cmp * \
                (0.99 if trade.direction == Direction.LONG else 1.01)
            logging.info(
                'TradeManager: placing new target order to exit position for tradeID %s', trade.tradeID)
            self.placeTargetOrder(trade, True)

    def getOrderManager(self, short_code):
        orderManager = None
        brokerName = getBrokerAppConfig(short_code)['broker']
        if brokerName == "zerodha":
            orderManager = ZerodhaOrderManager(Controller.getBrokerLogin(
                short_code).getBrokerHandle(), getBrokerAppConfig(short_code)['clientID'])
        # elif brokerName == "fyers": # Not implemented
        return orderManager

    def getNumberOfTradesPlacedByStrategy(self, strategy):
        count = 0
        for trade in self.trades:
            if trade.strategy != strategy:
                continue
            if trade.tradeState == TradeState.CREATED or trade.tradeState == TradeState.DISABLED:
                continue
            # consider active/completed/cancelled trades as trades placed
            count += 1
        return count

    def getAllTradesByStrategy(self, strategy):
        tradesByStrategy = []
        for trade in self.trades:
            if trade.strategy == strategy:
                tradesByStrategy.append(trade)
        return tradesByStrategy

    def getLastTradedPrice(self, tradingSymbol):
        return self.symbolToCMPMap[tradingSymbol]
    
    def storeTickDataInDB(self, tick):
        try:
            #check if tick is registerd to track
            if tick.tradingSymbol not in self.trackTradingSymbols:
                return
            
            #Check for QuestDB connection
            if self.questDBCursor is None or self.questDBCursor.closed:
                self.questDBCursor = Utils.getQuestDBConnection(self.getName())

            query = "INSERT INTO '{0}_tickData' VALUES('{1}', '{2}', {3}, {4}, {5}, {6}, {7}, {8}, {9}, {10}, {11}, {12}, {13});"\
                    .format(self.getName(), datetime.now(), tick.tradingSymbol, tick.lastTradedPrice, tick.lastTradedQuantity,
                            tick.avgTradedPrice, tick.volume, tick.totalBuyQuantity, tick.totalSellQuantity, 
                            tick.open, tick.high, tick.low, tick.close, tick.change)
            self.questDBCursor.execute(query)
            self.questDBCursor.connection.commit()

        except Exception as e:
            logging.error("Error in storeTickDataInDB for symbol %s,  Error => %s", tick.symbol, str(e))
    
    
    def registerTradingSymbolToTrack(self, tradingSymbolsList):
        for tradingSymbol in tradingSymbolsList:
            try:
                if tradingSymbol not in self.registeredSymbols:
                    # Algo register symbols with ticker
                    self.ticker.registerSymbols([tradingSymbol])
                
                if tradingSymbol not in self.trackTradingSymbols:
                    #Algo add symbols in tracking symbols list
                    self.trackTradingSymbols.append(tradingSymbol)

            except Exception as e:
                logging.error("Error in registerStrikeToTrack for symbol %s,  Error => %s", tradingSymbol, str(e))

        

