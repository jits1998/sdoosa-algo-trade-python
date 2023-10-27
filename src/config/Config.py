import json
import os

def getServerConfig():
  with open('../config/server.json', 'r') as server:
    jsonServerData = json.load(server)
    return jsonServerData

def getSystemConfig():
  with open('../config/system.json', 'r') as system:
    jsonSystemData = json.load(system)
    return jsonSystemData

def getBrokerAppConfig(short_code):
  with open('../config/{short_code}.json'.format(short_code = short_code), 'r') as brokerapp:
    jsonUserData = json.load(brokerapp)
    return jsonUserData

def getHolidays():
  with open('../config/holidays.json', 'r') as holidays:
    holidaysData = json.load(holidays)
    return holidaysData

def getTimestampsData():
  serverConfig = getServerConfig()
  timestampsFilePath = os.path.join(serverConfig['deployDir'], 'timestamps.json')
  if os.path.exists(timestampsFilePath) == False:
    return {}
  timestampsFile = open(timestampsFilePath, 'r')
  timestamps = json.loads(timestampsFile.read())
  return timestamps

def saveTimestampsData(timestamps = {}):
  serverConfig = getServerConfig()
  timestampsFilePath = os.path.join(serverConfig['deployDir'], 'timestamps.json')
  with open(timestampsFilePath, 'w') as timestampsFile:
    json.dump(timestamps, timestampsFile, indent=2)
  print("saved timestamps data to file " + timestampsFilePath)
