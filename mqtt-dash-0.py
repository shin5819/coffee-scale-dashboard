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
import time
from collections import deque

# Global variables
save_dir = Path('./data/')
current_time = dt.timedelta(0)
current_weight = 0.0
df_weight = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])  # 空のデータフレームとして初期化
df_load = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])
last_message_time = time.time()

measurement_started = False  # 計測が開始されたかどうかを管理するフラグ
measurement_start_time = None  # 計測開始時点のタイムスタンプ
pre_measurement_buffer = deque(maxlen=10)  # 直前n回分のデータを保存するバッファ

weight_threshold_exceeded = False  # 50gを超えたかどうかを管理するフラグ
measurement_stopped = False  # 計測が終了したかどうかを管理するフラグ
measurement_stopped_time = None  # 計測が終了を判定した時点のタイムスタンプ

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
    global last_message_time
    
    last_message_time = time.time()  # メッセージを受信した時刻を更新
    payload = msg.payload.decode()
    message = json.loads(payload)

    global current_time
    global current_weight
    global df_weight
    global measurement_started
    global measurement_start_time
    global measurement_stopped
    global measurement_stopped_time
    global weight_threshold_exceeded
    global pre_measurement_buffer

    current_weight = message['weight']
    timedelta = pd.to_timedelta(message['timedelta'])

    # 計測が完全に停止されている場合は何もしない
    if measurement_stopped and (measurement_stopped_time is None or time.time() - measurement_stopped_time > 5):
        return

    # 計測終了を判定した場合でも、5秒間は計測を続ける
    if measurement_stopped_time is not None and time.time() - measurement_stopped_time <= 5:
        current_time = timedelta - measurement_start_time
        df_weight.loc[current_time] = [current_time, current_time.total_seconds(), current_weight, 'live']
        return

    # 計測開始前のデータをバッファに保存
    pre_measurement_buffer.append((timedelta, current_weight))

    # 一度0.5gを超えたら、直前のデータを計測開始時点として記録
    if not measurement_started and current_weight > 0.5:
        measurement_started = True

        # バッファ内の最後のデータ（0.5gを超える直前のデータ）を取得
        if len(pre_measurement_buffer) > 1:
            measurement_start_time, initial_weight = pre_measurement_buffer[-2]  # 直前のデータを取得
        else:
            measurement_start_time = timedelta  # バッファが十分でない場合、現在の時刻を使用

        # バッファ内のデータを記録
        for buffered_timedelta, buffered_weight in pre_measurement_buffer:
            buffered_time = buffered_timedelta - measurement_start_time
            df_weight.loc[buffered_time] = [buffered_time, buffered_time.total_seconds(), buffered_weight, 'live']

    # 50gを超えたら、フラグを立てる
    if measurement_started and current_weight > 50:
        weight_threshold_exceeded = True

    # 一度50gを超えた後、10gを下回ったら計測を終了（5秒間の猶予を設ける）
    if weight_threshold_exceeded and current_weight < 10:
        measurement_stopped = True
        measurement_stopped_time = time.time()  # 現在の時刻を記録
        # 10gを下回った瞬間のデータを記録
        current_time = timedelta - measurement_start_time
        df_weight.loc[current_time] = [current_time, current_time.total_seconds(), current_weight, 'live']
        return

    # フラグが立っている場合のみデータを記録
    if measurement_started:
        current_time = timedelta - measurement_start_time
        df_weight.loc[current_time] = [current_time, current_time.total_seconds(), current_weight, 'live']

mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.loop_start()

# -----------------------------------------------------------------------------
# Defining Dash app
# -----------------------------------------------------------------------------
app = dash.Dash(external_stylesheets=[dbc.themes.DARKLY])

# -----------------------------------------------------------------------------
# Time and Weight Display Card
# -----------------------------------------------------------------------------
card_time_weight = dbc.Card(
    dbc.CardBody([
        dbc.Row([
            dbc.Col(html.H5("Time", className="card-title"), width=4),
            dbc.Col(html.H5(id="time_display", className="card-text"), width=8),
        ]),
        dbc.Row([
            dbc.Col(html.H5("Weight", className="card-title"), width=4),
            dbc.Col(html.H5(id="weight_display", className="card-text"), width=8),
        ]),
    ])
)

# -----------------------------------------------------------------------------
# Status Indicators Card (Styled Lamps)
# -----------------------------------------------------------------------------
card_status_indicators = dbc.Card(
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                html.Div("Message Received", id="message_received_lamp", 
                         style={"padding": "3px 8px", "border-radius": "5px", "background-color": "grey", 
                                "text-align": "center", "color": "white", "font-size": "12px", "font-weight": "bold", "margin-bottom": "12px"}),
                width=12
            ),
        ]),
        dbc.Row([
            dbc.Col(
                html.Div("Measurement Started", id="measurement_started_lamp", 
                         style={"padding": "3px 8px", "border-radius": "5px", "background-color": "grey", 
                                "text-align": "center", "color": "white", "font-size": "12px", "font-weight": "bold", "margin-bottom": "12px"}),
                width=12
            ),
        ]),
        dbc.Row([
            dbc.Col(
                html.Div("Threshold Exceeded", id="threshold_exceeded_lamp", 
                         style={"padding": "3px 8px", "border-radius": "5px", "background-color": "grey", 
                                "text-align": "center", "color": "white", "font-size": "12px", "font-weight": "bold", "margin-bottom": "12px"}),
                width=12
            ),
        ]),
        dbc.Row([
            dbc.Col(
                html.Div("Measurement Stopped", id="measurement_stopped_lamp", 
                         style={"padding": "3px 8px", "border-radius": "5px", "background-color": "grey", 
                                "text-align": "center", "color": "white", "font-size": "12px", "font-weight": "bold"}),
                width=12
            ),
        ]),
    ])
)

# -----------------------------------------------------------------------------
# Graph card
# -----------------------------------------------------------------------------
card_graph = dbc.Card(
    dcc.Graph(id="graph")
)

# -----------------------------------------------------------------------------
# Button card
# -----------------------------------------------------------------------------
card_button = dbc.Card(
    html.Div(
        [
            html.Div(
                [
                    dcc.Dropdown(id='file_dropdown', placeholder="Select a file", style={'width': '300px', 'color': 'black'}),
                    dbc.Button("Load", id='load_button', n_clicks=0, size="lg"),
                    dbc.Button("Save", id='save_button', n_clicks=0, size="lg", style={'margin-left': '10px'}),
                    html.Div(id='save_message', style={'margin-left': '10px', 'color': 'orange', 'font-size': '20px'})
                ],
                style={'display': 'flex', 'align-items': 'center', 'gap': '10px'}
            ),
            html.Div(
                dbc.Button("Reset", id='reset_button', n_clicks=0, size="lg",
                           style={'background-color': '#343a40', 'border-color': 'red', 'color': 'red'}),
                style={'margin-left': 'auto', 'display': 'flex', 'justify-content': 'flex-end'}
            ),
        ],
        style={'display': 'flex', 'align-items': 'center', 'justify-content': 'space-between'}
    )
)


# -----------------------------------------------------------------------------
# Application layout with horizontally aligned cards
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        dcc.Interval(id='update', n_intervals=0, interval=200),
        dcc.Location(id='url', refresh=True),  # ページリロード用
        dcc.Store(id='reset_triggered', data=False),  # リセットフラグ用のストアを追加
        html.H1("Coffee Scale Monitor with Plotly Dash"),
        html.Hr(),
        dbc.Row([
            dbc.Col(card_time_weight, style={"flex": "1", "max-width": "350px"}),
            dbc.Col(card_status_indicators, style={"flex": "1", "max-width": "350px"})
        ], style={"display": "flex", "justify-content": "space-between"}),
        dbc.Row(dbc.Col(card_graph)),
        dbc.Row(dbc.Col(card_button))
    ]
)

# -----------------------------------------------------------------------------
# Callback to reset the dashboard state and reload the page
# -----------------------------------------------------------------------------
@app.callback(
    Output('url', 'href'),
    Output('reset_triggered', 'data'),
    Input('reset_button', 'n_clicks')
)
def reset_and_reload(n_clicks):
    if n_clicks > 0:
        # グローバル変数をリセット
        global current_time, current_weight, df_weight, df_load, measurement_started, measurement_start_time
        global weight_threshold_exceeded, measurement_stopped, measurement_stopped_time, pre_measurement_buffer
        current_time = dt.timedelta(0)
        current_weight = 0.0
        df_weight = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])
        df_load = pd.DataFrame(columns=['timedelta', 'timedelta_sec', 'weight', 'type'])
        measurement_started = False
        measurement_start_time = None
        weight_threshold_exceeded = False
        measurement_stopped = False
        measurement_stopped_time = None
        pre_measurement_buffer = deque(maxlen=10)

        # ページのリロードを指示
        return "/", True

    return dash.no_update, dash.no_update

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
    Output('time_display', 'children'),
    Output('weight_display', 'children'),
    Output('graph', 'figure'),
    Output('message_received_lamp', 'style'),
    Output('measurement_started_lamp', 'style'),
    Output('threshold_exceeded_lamp', 'style'),
    Output('measurement_stopped_lamp', 'style'),
    Input('update', 'n_intervals')
)
def update_dashboard(timer):
    base_style = {"padding": "3px 8px", "border-radius": "5px", "text-align": "center", "color": "white", "font-size": "12px", "font-weight": "bold"}

    # 通常の更新処理
    minutes = int(current_time.total_seconds() // 60)  # 分
    seconds = current_time.total_seconds() % 60  # 秒と小数点以下の部分
    time_str = f"{minutes:02}:{seconds:04.1f}"  # mm:ss.s形式にフォーマット
    weight_str = f"{current_weight:.1f}g"

    message_received_style = base_style.copy()
    message_received_style["background-color"] = "green" if time.time() - last_message_time < 1 else "grey"
    message_received_style["box-shadow"] = "0 0 5px green" if time.time() - last_message_time < 1 else "none"

    measurement_started_style = base_style.copy()
    measurement_started_style["background-color"] = "blue" if measurement_started else "grey"
    measurement_started_style["box-shadow"] = "0 0 5px blue" if measurement_started else "none"

    threshold_exceeded_style = base_style.copy()
    threshold_exceeded_style["background-color"] = "orange" if weight_threshold_exceeded else "grey"
    threshold_exceeded_style["box-shadow"] = "0 0 5px orange" if weight_threshold_exceeded else "none"

    measurement_stopped_style = base_style.copy()
    measurement_stopped_style["background-color"] = "red" if measurement_stopped else "grey"
    measurement_stopped_style["box-shadow"] = "0 0 5px red" if measurement_stopped else "none"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_load['timedelta_sec'], y=df_load['weight'])) 
    fig.add_trace(go.Scatter(x=df_weight['timedelta_sec'], y=df_weight['weight'], fill='tozeroy'))
    fig.update_layout(yaxis=dict(range=[-10, None]))

    return time_str, weight_str, fig, message_received_style, measurement_started_style, threshold_exceeded_style, measurement_stopped_style

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
