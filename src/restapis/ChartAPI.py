from re import U
from flask.views import MethodView
from flask import render_template, request
from flask import redirect
from utils.Utils import Utils 

import logging
import json
import plotly
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date
from itertools import cycle
import plotly.express as px



class ChartAPI(MethodView):
  def get(self, short_code):
    if Utils.getTradeManager(short_code) is None:
      return redirect("/me/"+short_code, code=302)
    else:
      try:
        questDBCursor = Utils.getTradeManager(short_code).questDBCursor
        if questDBCursor is not None:
          df = pd.read_sql_query("select * from %(short_code)s where ts > to_timestamp(%(dstart)s, 'yyyy-MM-dd HH:mm:ss')", 
                    con = questDBCursor.connection, params = {"short_code" : short_code, "dstart" : date.today().strftime("%Y-%m-%d %H:%M:%S")})

          if not df.empty:

            #Parse ts and convert to datetime type
            df["ts"] = pd.to_datetime(df["ts"]).dt.strftime('%Y-%m-%d %H:%M:%S')
            df["ts"] = pd.to_datetime(df["ts"])

            #group pnl in 30sec frequency and select last pnl for each trade
            resample_data = df.groupby([pd.Grouper(key='ts', freq = '1T'), "tradeId", "strategy"]).agg(pnl = ('pnl', 'last')).reset_index()

            #Create pivot table with datetime as columns and trades as row index. Then forward fill pnl till end if trade is closed
            p_table = pd.pivot_table(resample_data, values = ["pnl"], index=['strategy', 'tradeId'],
                          columns=['ts'], margins = True, margins_name='total_pnl').ffill(axis = 1).replace(np.nan, 0)

            #Drop unwanted column headings
            p_table.columns = p_table.columns.droplevel(0)

            #Added Missing timestamp and previous pnls if timestamps are not available
            p_table = p_table.reindex(columns = pd.date_range(datetime.now().replace(minute = 30, hour = 9, second = 00).strftime('%Y-%m-%d %H:%M:%S'), 
                                                              df.iloc[-1]["ts"].strftime('%Y-%m-%d %H:%M:%S'),  freq="1T")).\
                                                              ffill(axis = 1).replace(np.nan, 0)

            #Group by strategy and sum of pnl at every timestamp
            g_table = p_table.groupby(["strategy"]).sum()
            g_table.loc["total_pnl"] = g_table[:-1].sum()


            x_axis = g_table.columns.to_list()[:-1]
            colors = cycle(px.colors.qualitative.Vivid)
            graph_info = []
            fig = go.Figure()
            
            #Plot Strategy pnls
            for s_name in g_table.index:
              if s_name != "total_pnl":
                  fig.add_trace(go.Bar(name = s_name, x = x_axis, y = g_table.loc[s_name].tolist(), marker_color = next(colors)))

            #Set barmode and set graph from 9:30 - 15:30
            fig.update_layout(barmode = 'group', xaxis_range=[datetime.now().replace(hour = 9, minute = 30, second = 00), 
                                                              datetime.now().replace(hour = 15, minute = 30, second = 00)])

            #Plot total pnl                                                     
            total_pnl_df = pd.DataFrame({"pnl" : g_table.loc["total_pnl"].tolist()})
          
            #Set postive pnl line to black ad negative pnl line color to red
            fig.add_scattergl(name = "Total PNL", x = x_axis, y = g_table.loc["total_pnl"].tolist(), line = {'color': 'black'})
            fig.add_scattergl(name = "Total PNL", x = x_axis, y = total_pnl_df.pnl.where( total_pnl_df.pnl < 0), line = {'color': 'red'})
            
            graphJSON = json.dumps(fig, cls = plotly.utils.PlotlyJSONEncoder)

            return render_template("chart.html", graphJSON = graphJSON)
          else:
            return "Data Not found"
        else:
          return "QuestDB not connected"
      except Exception as err:
        return "Error while connecting to QuestDB " + str(err)

