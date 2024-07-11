import pandas as pd
import plotly.express as px
from dash import ALL, MATCH, Dash, Input, Output, State, callback, dash_table, dcc, html

from tools.backtesting.data_processor import plot_chart

app = Dash(__name__)

app.layout = html.Div(
    children=[
        html.Div(
            children=[
                html.H1(children="Analysis diamonds dataset", className="header-title"),
                html.P(
                    children="maybe this demo will be useful to someone (:",
                    className="header-description",
                ),
            ],
            className="header",
        ),
        # html.Label('Количество'),
        html.Div(
            [
                dcc.Dropdown(
                    id="demo_drop",
                    options=[
                        {"label": "Огранка", "value": "cut"},
                        {"label": "Ясность(чистота)", "value": "clarity"},
                        {"label": "Цвет", "value": "color"},
                    ],
                    value="cut",
                    className="dropdown",
                ),
                dcc.Graph(id="output_graph"),
            ],
            className="card",
        ),
    ]
)


@app.callback(
    Output(component_id="output_graph", component_property="figure"),
    [Input(component_id="demo_drop", component_property="value")],
)
def update_output(value):
    # if value == 'cut':
    #     h = df.groupby(['cut'], as_index=False, sort=False)['carat'].count()
    # elif value == 'clarity':
    #     h = df.groupby(['clarity'], as_index=False, sort=False)['carat'].count()
    # elif value == 'color':
    #     h = df.groupby(['color'], as_index=False, sort=False)['carat'].count()
    fig = plot_chart("BTC-USDT", "1d")
    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
