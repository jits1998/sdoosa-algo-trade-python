from logging.handlers import TimedRotatingFileHandler
import os
import logging, datetime
from flask import Flask, redirect, session

from flask_session import Session

from config.Config import getServerConfig
from restapis.HomeAPI import HomeAPI
from restapis.BrokerLoginAPI import BrokerLoginAPI
from restapis.StartAlgoAPI import StartAlgoAPI
from restapis.ChartAPI import ChartAPI

app = Flask(__name__)

app.config["SESSION_TYPE"] = "filesystem"

Session(app)

app.config['PERMANENT_SESSION_LIFETIME'] =  datetime.timedelta(minutes=60)

@app.route("/")
def redirectHome():
  return redirect("/me/"+session.get('short_code',"5207"))

app.add_url_rule("/", 'default_home', redirectHome)
app.add_url_rule("/me/<short_code>", 'home', view_func=HomeAPI.as_view("home_api"))
app.add_url_rule("/apis/broker/login/zerodha", view_func=BrokerLoginAPI.as_view("broker_login_api"))
app.add_url_rule("/apis/algo/start", view_func=StartAlgoAPI.as_view("start_algo_api"))
app.add_url_rule("/chart/<short_code>", view_func=ChartAPI.as_view("chart_api"))


def initLoggingConfg(filepath):
  format = "%(asctime)s: %(message)s"
  handler = TimedRotatingFileHandler(filepath, when='midnight')
  logging.basicConfig(handlers=[handler], format=format, level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")

# Execution starts here
serverConfig = getServerConfig()

deployDir = serverConfig['deployDir']
if os.path.exists(deployDir) == False:
  print("Deploy Directory " + deployDir + " does not exist. Exiting the app.")
  exit(-1)

logFileDir = serverConfig['logFileDir']
if os.path.exists(logFileDir) == False:
  print("LogFile Directory " + logFileDir + " does not exist. Exiting the app.")
  exit(-1)

print("Deploy  Directory = " + deployDir)
print("LogFile Directory = " + logFileDir)
initLoggingConfg(logFileDir + "/app.log")

logging.info('serverConfig => %s', serverConfig)

# brokerAppConfig = getBrokerAppConfig()
# logging.info('brokerAppConfig => %s', brokerAppConfig)

port = serverConfig['port']

def timectime(s):
  if s is None:
    return None
  if isinstance(s, str):
    s = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
  return datetime.datetime.fromtimestamp(s).strftime("%H:%M:%S")

app.jinja_env.filters['ctime']= timectime

app.run('localhost', port, debug=True)



