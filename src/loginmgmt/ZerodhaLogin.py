import logging
from kiteconnect import KiteConnect

from config.Config import getSystemConfig
from loginmgmt.BaseLogin import BaseLogin

class ZerodhaLogin(BaseLogin):
  def __init__(self, brokerAppDetails):
    BaseLogin.__init__(self, brokerAppDetails)

  def login(self, args):
    logging.info('==> ZerodhaLogin .args => %s', args);
    systemConfig = getSystemConfig()
    brokerHandle = KiteConnect(api_key=self.brokerAppDetails.appKey)
    self.setBrokerHandle(brokerHandle)
    redirectUrl = None
    if 'request_token' in args:
      requestToken = args['request_token']
      logging.info('Zerodha requestToken = %s', requestToken)
      broker_session = brokerHandle.generate_session(requestToken, api_secret=self.brokerAppDetails.appSecret)

      if not broker_session['user_id'] == self.brokerAppDetails.clientID:
        raise Exception("Invalid User Credentials")

      
      accessToken = broker_session['access_token']
      logging.info('Zerodha accessToken = %s', accessToken)
      brokerHandle.set_access_token(accessToken)
      
      logging.info('Zerodha Login successful. accessToken = %s', accessToken)

      # set broker handle and access token to the instance
      
      self.setAccessToken(accessToken)

      # redirect to home page with query param loggedIn=true
      homeUrl = systemConfig['homeUrl'] + '?loggedIn=true'
      logging.info('Zerodha Redirecting to home page %s', homeUrl)
      redirectUrl = homeUrl
    else:
      loginUrl = brokerHandle.login_url()
      logging.info('Redirecting to zerodha login url = %s', loginUrl)
      redirectUrl = loginUrl

    return redirectUrl

