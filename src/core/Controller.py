import logging

from config.Config import getBrokerAppConfig
from models.BrokerAppDetails import BrokerAppDetails
from loginmgmt.ZerodhaLogin import ZerodhaLogin

class Controller:
  brokerLogin = {} # static variable
  brokerName = {} # static variable

  def handleBrokerLogin(args, short_code):
    brokerAppConfig = getBrokerAppConfig(short_code)

    brokerAppDetails = BrokerAppDetails(brokerAppConfig['broker'])
    brokerAppDetails.setClientID(brokerAppConfig['clientID'])
    brokerAppDetails.setAppKey(brokerAppConfig['appKey'])
    brokerAppDetails.setAppSecret(brokerAppConfig['appSecret'])

    logging.info('handleBrokerLogin appKey %s', brokerAppDetails.appKey)
    Controller.brokerName[short_code] = brokerAppDetails.broker
    if Controller.brokerName[short_code] == 'zerodha':
      Controller.brokerLogin[short_code] = ZerodhaLogin(brokerAppDetails)
    # Other brokers - not implemented
    #elif Controller.brokerName == 'fyers':
      #Controller.brokerLogin = FyersLogin(brokerAppDetails)

    redirectUrl = Controller.brokerLogin[short_code].login(args)
    return redirectUrl

  def getBrokerLogin(short_code):
    return Controller.brokerLogin.get(short_code, None)

  def getBrokerName(short_code):
    return Controller.brokerName.get(short_code, None)
