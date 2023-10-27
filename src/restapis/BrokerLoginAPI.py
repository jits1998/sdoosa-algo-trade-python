from flask.views import MethodView
from flask import request, redirect, session

from core.Controller import Controller 

class BrokerLoginAPI(MethodView):
  def get(self):
    redirectUrl = Controller.handleBrokerLogin(request.args, session['short_code'])
    if Controller.getBrokerLogin(session['short_code']).getAccessToken() is not None:
      session['access_token'] = Controller.getBrokerLogin(session['short_code']).accessToken
    return redirect(redirectUrl, code=302)