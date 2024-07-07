# https://gist.github.com/tolgahancepel/ccd7245530dd3a80d823b52968295080

# -----------------------------------------------------------------------------
# Importing the modules
# -----------------------------------------------------------------------------
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import paho.mqtt.client as mqtt
import pandas as pd
import json
import datetime as dt

global current_time
current_time = dt.timedelta(0)

global current_weight
current_weight = 0.0

global df
df_weight = pd.DataFrame({'weight':[current_weight]}, index=[current_time])

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
    df_weight.loc[current_time] = current_weight

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

# -----------------------------------------------------------------------------
# Application layout
# -----------------------------------------------------------------------------
app.layout = dbc.Container(
    [
        # dcc.Interval(id='update', n_intervals=0, interval=1000*3),
        dcc.Interval(id='update', n_intervals=0, interval=200),
        html.H1("Coffee Scale Monitor with Plotly Dash"),
        html.Hr(),
        dbc.Row(dbc.Col(card, lg=4))
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


# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run_server(host='0.0.0.0', port=8050, debug=True)