from core.BaseAlgo import BaseAlgo

from strategies.BN1ReHedge import BN1ReHedge
from strategies.N1ReHedge import N1ReHedge
from strategies.RangeBreakOut1430 import RangeBreakOut1430
from strategies.RangeBreakOut200CP import RangeBreakOut200CP
from strategies.NiftySell955CPR40 import NiftySell955CPR40
from strategies.NiftySell1400PR20 import NiftySell1400PR20
from strategies.BNSell955CPR40 import BNSell955CPR40
from strategies.BNSell1400PR20 import BNSell1400PR20

class AlgoTypeA(BaseAlgo):

    def startStrategies(self, short_code, multiple = 0):
    # start running strategies: Run each strategy in a separate thread
    # run = [expiry, mon, tue, wed, thru, fri, -4expiry, -3 expiry, -2 expiry, -1 expiry]

      #Breakouts
      self.startStrategy( RangeBreakOut1430, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 8, 8])
      self.startStrategy( RangeBreakOut200CP, short_code, multiple, [8, 0, 0, 0, 8, 8, 0, 0, 0, 0])

      #Sell
      self.startStrategy( NiftySell955CPR40, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
      self.startStrategy( NiftySell1400PR20, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
      
      self.startStrategy( BNSell955CPR40, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
      self.startStrategy( BNSell1400PR20, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 0, 0])

      #1Re Hedge
      self.startStrategy( BN1ReHedge, short_code, multiple, [8, 0, 0, 0, 0, 0, 0, 0, 0, 2])
      self.startStrategy( N1ReHedge, short_code, multiple, [8, 0, 0, 0, 0, 8, 0, 0, 0, 8])

