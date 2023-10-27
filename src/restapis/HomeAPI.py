from flask.views import MethodView
from flask import render_template
from flask import session
from utils.Utils import Utils 
from core.Controller import Controller

class HomeAPI(MethodView):
  def get(self, short_code):

    if session.get('short_code', None) is not None and not short_code == session['short_code']:
      session.clear()
      session['short_code'] = short_code

    if session.get('access_token', None) is None and Utils.getTradeManager(short_code) is None:
      session['short_code'] = short_code
      return render_template('index.html')
    else:
      trademanager = Utils.getTradeManager(short_code)
      return render_template('index_algostarted.html', strategies = trademanager.strategyToInstanceMap.values() if trademanager is not None else {}, 
                                                        ltps = trademanager.symbolToCMPMap if trademanager is not None else {},
                                                        totalBuys = trademanager.symboltoTotalBuy if trademanager is not None else {},
                                                        totalSells = trademanager.symboltoTotalSell if trademanager is not None else {},
                                                        algoStarted = True if trademanager is not None else False,
                                                        margins = Controller.getBrokerLogin(short_code).getBrokerHandle().margins() if Controller.getBrokerLogin(short_code) is not None else {})