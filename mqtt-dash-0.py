# -----------------------------------------------------------------------------
# Importing the modules
# -----------------------------------------------------------------------------
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import pandas as pd
import json
import datetime as dt
from pathlib import Path
import os

# Global variables
save_dir = Path('./data/')
current_time = dt.timedelta(0)
current_weight = 0.0
df_weight = pd.DataFrame({'timedelta':[dt.timedelta(0)], 'timedelta_sec':[0.0], 'weight':[current_weight], 'type': ['live']}, index=[current_time])
df_load = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])
measurement_started = False  # 計測が開始されたかどうかを管理するフラグ
measurement_start_time = None  # 計測開始時点のタイムスタンプ

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
mqttc.connect("192.168.3.43", 1883, 60)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    mqttc.subscribe("coffee-scale/measured-weight")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    message = json.loads(payload)

    global current_time
    
    global current_weight
    current_weight = message['weight']

    global df_weight
    global measurement_started
    global measurement_start_time

    # 一度0.5gを超えたら、フラグを立てて計測を開始
    if not measurement_started and current_weight > 0.5:
        measurement_started = True
        measurement_start_time = pd.to_timedelta(message['timedelta'])  # 計測開始時点のタイムスタンプを保存

    # フラグが立っている場合のみデータを記録
    if measurement_started:
        current_time = pd.to_timedelta(message['timedelta']) - measurement_start_time
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
    html.Div(
        [
            dcc.Dropdown(id='file_dropdown', placeholder="Select a file", style={'width': '300px', 'color': 'black'}),
            dbc.Button("Load", id='load_button', n_clicks=0, size="lg"),
            dbc.Button("Save", id='save_button', n_clicks=0, size="lg", style={'margin-left': '10px'}),
            html.Div(id='save_message', style={'margin-left': '10px', 'color': 'orange', 'font-size': '20px'})
        ],
        style={'display': 'flex', 'align-items': 'center', 'gap': '10px'}
    )
)

# -----------------------------------------------------------------------------
# Application layout
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        dcc.Interval(id='update', n_intervals=0, interval=200),
        html.H1("Coffee Scale Monitor with Plotly Dash"),
        html.Hr(),
        dbc.Row(dbc.Col(card, lg=4)),
        dbc.Row(dbc.Col(card_graph)),
        dbc.Row(dbc.Col(card_button))
    ]
)

# -----------------------------------------------------------------------------
# Callback to update the dropdown options
# -----------------------------------------------------------------------------
@app.callback(
    Output('file_dropdown', 'options'),
    Input('update', 'n_intervals')
)
def update_dropdown(timer):
    files = list(save_dir.glob('*.csv'))
    files.sort(reverse=True, key=os.path.getmtime)
    options = [{'label': file.name, 'value': str(file)} for file in files]
    return options

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

# -----------------------------------------------------------------------------
# Callback for updating the graph
# -----------------------------------------------------------------------------
@app.callback(
    Output('graph', 'figure'),
    Input('update', 'n_intervals')
)
def update_graph(timer):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_load['timedelta_sec'], y=df_load['weight'])) 
    fig.add_trace(go.Scatter(x=df_weight['timedelta_sec'], y=df_weight['weight'], fill='tozeroy')) 
    # y軸の表示範囲を設定
    fig.update_layout(
        yaxis=dict(range=[-10, None])  # 下限を0に設定し、上限は自動に設定
    )
    return fig

# -----------------------------------------------------------------------------
# Callback for loading graph data from selected file
# -----------------------------------------------------------------------------
@app.callback(
    Input('load_button', 'n_clicks'),
    State('file_dropdown', 'value')
)
def load_graph(n_clicks, selected_file):
    if selected_file is not None and n_clicks > 0:
        global df_load
        df_load = pd.read_csv(selected_file, index_col=0)
        df_load.loc[:,'type'] = 'guide'

# -----------------------------------------------------------------------------
# Callback for saving the current graph data
# -----------------------------------------------------------------------------
@app.callback(
    Output('save_message', 'children'),
    Input('save_button', 'n_clicks')
)
def save_graph(n_clicks):
    if n_clicks > 0:
        try:
            save_filename = save_dir / dt.datetime.now().strftime('%Y%m%d-%H%M%S.csv')
            df_weight.to_csv(save_filename)
            return f"File saved successfully: {save_filename.name}"
        except Exception as e:
            return f"Error saving file: {str(e)}"
    return ""

# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run_server(host='0.0.0.0', port=8050, debug=True)
