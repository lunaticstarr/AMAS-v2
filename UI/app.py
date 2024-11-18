import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import base64
import subprocess
import os
import threading

# Initialize the Dash app
app = dash.Dash(__name__)

# Paths
csv_output_path = os.path.join(os.getcwd(), "recommendations.csv")
amas_recommendation_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/recommend_annotation.py"
amas_species_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/recommend_species.py"
amas_reactions_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/recommend_reactions.py"
amas_update_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/update_annotation.py"
current_model_path = "current_model.xml"
download_file_path = "new_model.xml"

# Global variable to hold AMAS process information
process_info = {"process": None, "output": ""}

# Function to read output in a separate thread
def read_process_output(process, params_used):
    process_info["output"] = params_used  # Initialize with parameters
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            process_info["output"] += line

# Define the layout of the app
app.layout = html.Div(
    style={"display": "flex", "flexDirection": "row", "width": "100%", "height": "200vh", "overflow": "hidden"},
    children=[
        # Left Section: Menu, Parameters, Messages
        html.Div(
            style={"width": "25%", "padding": "10px", "boxSizing": "border-box", "borderRight": "1px solid #ccc"},
            children=[
                html.H1("AMAS: Automated Model Annotation System", style={"fontSize": "20px", "textAlign": "center"}),

                # Menu Buttons
                html.Div([
                    dcc.Upload(id='upload-sbml', children=html.Button("Upload SBML Model", style={"height": "50px", "fontSize": "12px"},
                    title = "Upload a model in SBML format."), multiple=False),
                    html.Button("Recommend Annotations", id="annotation-button", n_clicks=0, style={"height": "50px", "fontSize": "12px"},
                    title = "Generate a table that contains the recommended annotations."),
                    html.Button("Update Annotations", id="update-button", n_clicks=0, style={"height": "50px", "fontSize": "12px"},
                    title = "Update model annotation using instructions in table."),
                    html.Button("Download Annotated Model", id="download-button", n_clicks=0, style={"height": "50px", "fontSize": "12px"},
                    title = "Download the annotated model to local."),
                    dcc.Download(id="download-component")
                ], style={"display": "flex", "gap": "10px", "marginBottom": "20px"}),

                # Annotation Type Selection
                html.Label("What to Annotate:", 
                title = "To annotate all elements, or species/reactions only."),
                dcc.RadioItems(
                    id="annotation-type",
                    options=[
                        {"label": "All", "value": "all"},
                        {"label": "Species", "value": "species"},
                        {"label": "Reactions", "value": "reactions"}
                    ],
                    value="all",
                    inline=True
                ),
                html.Br(),

                # Parameters Section
                html.Div([
                    html.Label("Match Score Selection Criteria (--mssc):", 
                    title = "Decide how to recommend candidate annotations based on the match scores."),
                    dcc.RadioItems(
                        id='mssc-radio',
                        options=[
                            {'label': 'Top: report only candidates with the highest match score', 'value': 'top'},
                            {'label': 'Above: report all candidates at or above cutoff match score', 'value': 'above'}
                        ],
                        value='top',  # Default value
                        inline=True
                    ),
                    html.Br(),
                    html.Label("Match Score Cutoff (--cutoff):",
                    title = "The cutoff for match scores (applies to both top and above MSSC)"),
                    dcc.Slider(
                        id='cutoff-slider',
                        min=0.0,
                        max=1.0,
                        step=0.01,
                        value=0.0,  # Default value
                        marks={i / 10: f"{i / 10:.1f}" for i in range(11)}
                    ),
                    html.Br(),
                    html.Label("Minimum Length of Name (--min_len):",
                    title = "Only recommend annotations for those with longer displayed names."),
                    html.Br(),
                    dcc.Input(
                        id='min-len-input',
                        type='number',
                        value=0,  # Default value
                        min=0,
                        step=1,
                        style={"width": "10%"}
                    ),
                    html.Br(),
                    html.Br(),
                    html.Label("Optimize Predictions (--optimize):",
                    title = "Whether to compare once-predicted annotations of species and reactions and iteratively updates them."),
                    dcc.RadioItems(
                        id='optimize-radio',
                        options=[
                            {'label': 'Yes', 'value': 'yes'},
                            {'label': 'No', 'value': 'no'}
                        ],
                        value='no',  # Default value
                        inline=True
                    )
                ], style={"marginBottom": "20px"}),

                # Processing Messages
                html.Div(id="amas-output", style={
                    "whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px",
                    "maxHeight": "500px", "overflowY": "scroll"
                }, children="Please upload an SBML model to begin.")
            ]
        ),

        # Middle Section: SBML Model Display
        html.Div(
            id="sbml-container",
            style={"width": "30%", "padding": "10px", "boxSizing": "border-box", "borderRight": "1px solid #ccc"},
            children=[
                html.H2("SBML Model", style={"fontSize": "16px", "textAlign": "center"}),
                html.Div(id='sbml-content', style={
                    "whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px",
                    "maxHeight": "700px", "overflowY": "scroll"
                })
            ]
        ),

        # Right Section: Table
        html.Div(
            id="table-container",
            style={"width": "45%", "padding": "10px", "boxSizing": "border-box"},
            children=[
                html.H2("Annotation Table", style={"fontSize": "16px", "textAlign": "center"}),
                html.H2("Please select instructions for updating the model in the UPDATE ANNOTATION column.", style={"fontSize": "14px", "textAlign": "left"}),
                dash_table.DataTable(
                    id="csv-table",
                    style_table={"maxHeight": "700px", "overflowY": "scroll", "marginTop": "20px"},
                    style_data={'whiteSpace': 'normal', 'height': 'auto', 'lineHeight': '15px'},
                    editable=True,
                    filter_action = "native", sort_action = "native", sort_mode = "multi",
                    columns=[
                        {"name": "Type", "id": "type"},
                        {"name": "ID", "id": "id"},
                        {"name": "Display Name", "id": "display name"},
                        {"name": "Annotation", "id": "annotation"},
                        {"name": "Annotation Label", "id": "annotation label"},
                        {"name": "Match Score", "id": "match score"},
                        {"name": "Existing", "id": "existing"},
                        {"name": "UPDATE ANNOTATION", "id": "UPDATE ANNOTATION", "presentation": "dropdown"}
                    ],
                    dropdown_conditional=[
                        {
                            "if": {"column_id": "UPDATE ANNOTATION", "filter_query": "{existing} = 1"},
                            "options": [
                                {"label": "keep", "value": "keep"},
                                {"label": "delete", "value": "delete"}
                            ],
                        },
                        {
                            "if": {"column_id": "UPDATE ANNOTATION", "filter_query": "{existing} = 0"},
                            "options": [
                                {"label": "ignore", "value": "ignore"},
                                {"label": "add", "value": "add"}
                            ],
                        },
                    ]
                )
            ]
        ),

        # Interval for real-time AMAS output
        dcc.Interval(id="interval-component", interval=1000, n_intervals=0)
    ]
)

# Callback to manage workflow
@app.callback(
    [Output("amas-output", "children"),
     Output("sbml-content", "children"),
     Output("csv-table", "data"),
     Output("download-component", "data"),
     Output("interval-component", "disabled")],
    [Input("upload-sbml", "contents"),
     Input("annotation-button", "n_clicks"),
     Input("update-button", "n_clicks"),
     Input("download-button", "n_clicks"),
     Input("interval-component", "n_intervals")],
    [State("annotation-type", "value"),
     State("mssc-radio", "value"),
     State("cutoff-slider", "value"),
     State("optimize-radio", "value"),
     State("csv-table", "data"),
     State("sbml-content", "children"),
     State("min-len-input","value")]
)
def manage_workflow(contents, annotation_clicks, update_clicks, download_clicks, n_intervals,
                    annotation_type, mssc, cutoff, optimize, table_data, sbml_text,min_len):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Please upload an SBML model to begin.", sbml_text, [], dash.no_update, True

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Handle SBML Upload
    if button_id == "upload-sbml" and contents:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        with open(current_model_path, "wb") as f:
            f.write(decoded)
        model_content = decoded.decode("utf-8")
        return "Model uploaded successfully.", model_content, [], dash.no_update, True

    # Handle Download
    if button_id == "download-button" and download_clicks > 0:
        return dash.no_update, sbml_text, table_data, dcc.send_file(download_file_path), True

    # Handle Annotation
    if button_id == "annotation-button" and annotation_clicks > 0:
        script_path = {
            "all": amas_recommendation_path,
            "species": amas_species_path,
            "reactions": amas_reactions_path
        }[annotation_type]

        params_used = f"Running AMAS {annotation_type} annotation with parameters:\n  --mssc: {mssc}\n  --cutoff: {cutoff}\n"
        if annotation_type == "all":
            params_used += f"  --optimize: {optimize}\n"
        else: params_used += f" --min_len: {min_len}\n"

        command = [
            "python", script_path, current_model_path,
            "--mssc", mssc, "--cutoff", str(cutoff),
            "--outfile", csv_output_path
        ]
        if annotation_type == "all":
            command += ["--optimize", optimize, "--save", "csv"]
        else: command += ["--min_len", str(min_len)]

        process_info["process"] = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        threading.Thread(target=read_process_output, args=(process_info["process"], params_used)).start()
        return params_used, sbml_text, [], dash.no_update, False

    # Handle Updates
    if button_id == "update-button" and update_clicks > 0:
        pd.DataFrame(table_data).to_csv(csv_output_path, index=False)
        subprocess.run(
            ["python", amas_update_path, current_model_path, csv_output_path, download_file_path],
            check=True
        )
        with open(download_file_path, "r") as f:
            updated_model_content = f.read()
        return "Update complete. You can now download the annotated model.", updated_model_content, table_data, dash.no_update, True

    # Real-Time Output
    if button_id == "interval-component" and process_info["process"]:
        if process_info["process"].poll() is not None:
            df = pd.read_csv(csv_output_path)
            df["UPDATE ANNOTATION"] = df.apply(lambda row: "keep" if row["existing"] == 1 else "ignore", axis=1)
            process_info["output"] += "\nAnnotation complete."
            process_info["process"] = None
            return process_info["output"], sbml_text, df.to_dict("records"), dash.no_update, True
        return process_info["output"], sbml_text, [], dash.no_update, False

    return dash.no_update, sbml_text, [], dash.no_update, True


if __name__ == "__main__":
    app.run_server(debug=True)
