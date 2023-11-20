from strategies.BaseStrategy import BaseStrategy
from utils.Utils import Utils
from models.Direction import Direction
from models.ProductType import ProductType
from datetime import datetime
import logging

class BN1ReHedge (BaseStrategy):
    __instance = {}

    @staticmethod
    def getInstance(short_code):  # singleton class
        if BN1ReHedge.__instance.get(short_code, None) == None:
            BN1ReHedge(short_code)
        return BN1ReHedge.__instance[short_code]

    def __init__(self, short_code):
        if BN1ReHedge.__instance.get(short_code, None) != None:
            raise Exception("This class is a singleton!")
        else:
            BN1ReHedge.__instance[short_code] = self
        # Call Base class constructor
        super().__init__("BN1ReHedge", short_code)
        # Initialize all the properties specific to this strategy
        
        # When to start the strategy. Default is Market start time
        self.startTimestamp = Utils.getTimeOfToDay(9, 30, 0)
        self.productType = ProductType.MIS
        # This is not square off timestamp. This is the timestamp after which no new trades will be placed under this strategy but existing trades continue to be active.
        self.stopTimestamp = Utils.getTimeOfToDay(15, 24, 0)
        self.squareOffTimestamp = Utils.getTimeOfToDay(15, 24, 0)  # Square off time
        # Capital to trade (This is the margin you allocate from your broker account for this strategy)
        # (1 CE + 1 PE) Max number of trades per day under this strategy
        self.maxTradesPerDay = 2
        self.isFnO = True  # Does this strategy trade in FnO or not

    def addTradeToList(self, trade):
        if trade != None:
            self.trades.append(trade)

    def process(self):
        now = datetime.now()
        if now < self.startTimestamp or not self.isEnabled():
            return
        
        if not len(self.trades) == 0:
            return

        numLots = self.getLots()
    
        ceStrike, cePremium = self.getStrikeWithNearestPremium("CE", 1)
        logging.info('%s:: Recieved CE Strike %s CE Premium %s' % (self.short_code, ceStrike, cePremium))
        if not ceStrike == 0:
            ceSymbol = Utils.prepareWeeklyOptionsSymbol(self.symbol,ceStrike, "CE")
            self.generateTrade(ceSymbol, Direction.LONG, numLots, cePremium+0.1)

        peStrike, pePremium = self.getStrikeWithNearestPremium("PE", 1)
        logging.info('%s:: Recieved PE Strike %s PE Premium %s' % (self.short_code, peStrike, pePremium))
        if not peStrike == 0:
            peSymbol = Utils.prepareWeeklyOptionsSymbol(self.symbol, peStrike, "PE")
            self.generateTrade(peSymbol, Direction.LONG, numLots, pePremium+0.1)  

        logging.info('%s::%s' % (ceStrike, peStrike))
                     
        return