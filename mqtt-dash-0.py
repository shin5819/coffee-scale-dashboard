# https://gist.github.com/tolgahancepel/ccd7245530dd3a80d823b52968295080

# -----------------------------------------------------------------------------
# Importing the modules
# -----------------------------------------------------------------------------
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import pandas as pd
import json
import datetime as dt
from pathlib import Path
import os

global save_dir
save_dir = Path('./data/')

global current_time
current_time = dt.timedelta(0)

global current_weight
current_weight = 0.0

global df_weight
df_weight = pd.DataFrame({'timedelta':[dt.timedelta(0)], 'timedelta_sec':[0.0], 'weight':[current_weight], 'type': ['live']}, index=[current_time])

global df_load
df_load = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])

def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    d["milliseconds"], _ = divmod(tdelta.microseconds, 1000)
    d["microseconds"] = tdelta.microseconds
    return fmt.format(**d)

# -----------------------------------------------------------------------------
# MQTT Subscribe
# -----------------------------------------------------------------------------
mqttc = mqtt.Client()
# mqttc.connect("mqtt.eclipseprojects.io", 1883, 60)
mqttc.connect("192.168.11.52", 1883, 60)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    mqttc.subscribe("coffee-scale/measured-weight")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    message = json.loads(payload)

    global current_time
    current_time = pd.to_timedelta(message['timedelta'])
    
    global current_weight
    current_weight = message['weight']

    global df_weight
    df_weight.loc[current_time] = [current_time, current_time.total_seconds(), current_weight, 'live']

mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.loop_start()

# -----------------------------------------------------------------------------
# Defining Dash app
# -----------------------------------------------------------------------------
app = dash.Dash(external_stylesheets=[dbc.themes.DARKLY])

# -----------------------------------------------------------------------------
# weight card
# -----------------------------------------------------------------------------
card = dbc.Card(
    html.H4(id="weight")
)

card_graph = dbc.Card(
    dcc.Graph(id="graph")
)

card_button = dbc.Card(
    [
        html.Button("Load", id='load_button', n_clicks=0),
        html.Button("Save", id='save_button', n_clicks=0)
    ]
)

# -----------------------------------------------------------------------------
# Application layout
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        # dcc.Interval(id='update', n_intervals=0, interval=1000*3),
        dcc.Interval(id='update', n_intervals=0, interval=200),
        html.H1("Coffee Scale Monitor with Plotly Dash"),
        html.Hr(),
        dbc.Row(dbc.Col(card, lg=4)),
        dbc.Row(dbc.Col(card_graph)),
        dbc.Row(dbc.Col(card_button))
    ]
)

# -----------------------------------------------------------------------------
# Callback for updating weight data
# -----------------------------------------------------------------------------
@app.callback(
    Output('weight', 'children'),
    Input('update', 'n_intervals')
)
def update_weight(timer):
    time = strfdelta(current_time, "{minutes}:{seconds:0>2}.{milliseconds:0>3}")
    return ("Time: " +  time + ", Weight: " + str(current_weight))

@app.callback(
    Output('graph', 'figure'),
    Input('update', 'n_intervals')
)
def update_graph(timer):
    # fig = px.area(df_weight, x='timedelta_sec', y='weight', line_group='type')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_load['timedelta_sec'], y=df_load['weight'])) 
    fig.add_trace(go.Scatter(x=df_weight['timedelta_sec'], y=df_weight['weight'], fill='tozeroy')) 

    return fig

@app.callback(
    Input('load_button', 'n_clicks')
)
def load_graph(timer):
    global save_dir
    files = list(save_dir.glob('*.csv'))
    file_updates = {file_path: os.stat(file_path).st_mtime for file_path in files}
    newest_file = max(file_updates, key=file_updates.get)

    global df_load
    df_load = pd.read_csv(newest_file, index_col=0)
    df_load.loc[:,'type'] = 'guide'

@app.callback(
    Input('save_button', 'n_clicks')
)
def save_graph(timer):
    global savedir
    save_filename = Path.joinpath(save_dir, dt.datetime.now().strftime('%Y%m%d-%H%M%S.csv'))
    df_weight.to_csv(save_filename)

# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run_server(host='0.0.0.0', port=8050, debug=True)