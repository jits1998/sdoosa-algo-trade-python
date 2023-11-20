from flask.views import MethodView
import importlib
import json
import logging
import threading, time
from config.Config import getSystemConfig
from flask import session

from config.Config import getSystemConfig, getBrokerAppConfig
from utils.Utils import Utils

class StartAlgoAPI(MethodView):
  def post(self):
    if not Utils.getTradeManager(short_code = session['short_code']) :
      #get User's Algo type
      brokerAppConfig = getBrokerAppConfig(session['short_code'])
      algoType = brokerAppConfig.get("algoType","BaseAlgo")
      algoConfigModule = importlib.import_module('algos.' + algoType, algoType)
      algoConfigClass = getattr(algoConfigModule, algoType)
      # start algo in a separate thread
      x = threading.Thread(target = algoConfigClass().startAlgo, name="Algo", args=(session['access_token'], session['short_code'],\
                                                                                    getBrokerAppConfig(session['short_code']).get("multiple", 1),))

      x.start()
      time.sleep(5)
    systemConfig = getSystemConfig()
    homeUrl = systemConfig['homeUrl'] + '?algoStarted=true'
    logging.info('Sending redirect url %s in response', homeUrl)
    respData = { 'redirect': homeUrl }
    return json.dumps(respData)
  