# https://gist.github.com/tolgahancepel/ccd7245530dd3a80d823b52968295080

# -----------------------------------------------------------------------------
# Importing the modules
# -----------------------------------------------------------------------------
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import paho.mqtt.client as mqtt

global current_temperature
current_temperature = "NaN"

# -----------------------------------------------------------------------------
# MQTT Subscribe
# -----------------------------------------------------------------------------
mqttc = mqtt.Client()
# mqttc.connect("mqtt.eclipseprojects.io", 1883, 60)
mqttc.connect("192.168.11.52", 1883, 60)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    # mqttc.subscribe("myroom/temperature")
    mqttc.subscribe("coffee-scale/measured-weight")

def on_message(client, userdata, msg):
    global current_temperature
    current_temperature = msg.payload.decode()

mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.loop_start()

# -----------------------------------------------------------------------------
# Defining Dash app
# -----------------------------------------------------------------------------
app = dash.Dash(external_stylesheets=[dbc.themes.DARKLY])

# -----------------------------------------------------------------------------
# Temperature card
# -----------------------------------------------------------------------------
card = dbc.Card(
    html.H4(id="temperature")
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
# Callback for updating temperature data
# -----------------------------------------------------------------------------
@app.callback(
    Output('temperature', 'children'),
    Input('update', 'n_intervals')
)

def update_temperature(timer):
    return ("Weight: " + str(current_temperature))


# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run_server(host='0.0.0.0', port=8050, debug=True)