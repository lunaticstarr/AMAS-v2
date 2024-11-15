import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import base64
import subprocess
import os
import threading
import time

# Initialize the Dash app
app = dash.Dash(__name__)

# Paths
csv_output_path = os.path.join(os.getcwd(), "recommendations.csv")
amas_recommendation_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/recommend_annotation.py"
amas_update_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/update_annotation.py"

# Define the layout of the app
app.layout = html.Div([
    html.H1("AMAS Annotation Tool"),

    # Top Menu with Upload and Annotate Buttons
    html.Div([
        dcc.Upload(id='upload-sbml', children=html.Button("Upload SBML Model"), multiple=False),
        html.Button("Annotate Model", id="annotation-button", n_clicks=0, disabled=True),
        html.Button("Save and Update Annotations", id="update-button", n_clicks=0, disabled=True)
    ], style={"display": "flex", "gap": "10px", "margin-bottom": "20px"}),

    # Display processing messages
    html.Div(id="amas-output", style={"whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px", 
                                      "margin-top": "10px", "maxHeight": "150px", "overflowY": "scroll"},
             children="Please upload an SBML model to begin."),

    # Display SBML content (original or updated)
    html.Div(id='sbml-content', style={"whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px",
                                       "margin-top": "20px", "maxHeight": "300px", "overflowY": "scroll"}),

    # Display CSV Table with dropdowns below the SBML content
    dash_table.DataTable(
        id="csv-table",
        style_table={"maxHeight": "500px", "overflowY": "scroll", "margin-top": "20px"},
        style_data={'whiteSpace': 'normal', 'height': 'auto', 'lineHeight': '15px'},
        editable=True,
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
    ),
    
    # Interval for real-time AMAS output
    dcc.Interval(id="interval-component", interval=1000, n_intervals=0, disabled=True)
])

# Global variables to hold AMAS process information
process_info = {"process": None, "output": "", "output_thread": None}

# Function to read output in a separate thread
def read_process_output(process):
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            process_info["output"] += line

# Main callback to handle upload, annotation, real-time output, and updating messages
@app.callback(
    [Output("sbml-content", "children"), Output("annotation-button", "disabled"),
     Output("interval-component", "disabled"), Output("amas-output", "children"),
     Output("csv-table", "data"), Output("update-button", "disabled")],
    [Input("upload-sbml", "contents"), Input("annotation-button", "n_clicks"),
     Input("interval-component", "n_intervals"), Input("update-button", "n_clicks")],
    [State("sbml-content", "children"), State("amas-output", "children"), State("csv-table", "data")]
)
def manage_process(contents, annotation_clicks, n_intervals, update_clicks, sbml_text, amas_output, table_data):
    global process_info
    ctx = dash.callback_context
    if not ctx.triggered:
        return "", True, True, "Please upload an SBML model to begin.", [], True
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Handle SBML upload
    if button_id == "upload-sbml" and contents:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        sbml_file_path = "uploaded_model.xml"
        with open(sbml_file_path, "wb") as sbml_file:
            sbml_file.write(decoded)
        sbml_text = decoded.decode("utf-8")
        return sbml_text, False, True, "Model uploaded successfully. Click 'Annotate Model' to proceed.", [], True

    # Start annotation process
    elif button_id == "annotation-button" and annotation_clicks > 0 and sbml_text:
        try:
            process_info["process"] = subprocess.Popen(
                ["python", amas_recommendation_path, "uploaded_model.xml", "--save", "csv", "--outfile", csv_output_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            process_info["output"] = "Starting AMAS annotation...\n"
            process_info["output_thread"] = threading.Thread(target=read_process_output, args=(process_info["process"],))
            process_info["output_thread"].start()
            return sbml_text, True, False, process_info["output"], [], True

        except Exception as e:
            process_info["output"] = f"Error starting AMAS: {e}"
            return sbml_text, True, True, process_info["output"], [], True

    # Real-time update of AMAS output and check if the process has finished
    elif button_id == "interval-component" and process_info["process"]:
        if process_info["process"].poll() is not None:
            process_info["output_thread"].join()
            process_info["process"] = None
            if os.path.exists(csv_output_path):
                for _ in range(10):
                    with open(csv_output_path, "r") as f:
                        if f.read().strip():
                            break
                    time.sleep(0.5)
            df = pd.read_csv(csv_output_path)
            df["UPDATE ANNOTATION"] = df.apply(lambda row: "keep" if row["existing"] == 1 else "ignore", axis=1)
            data = df.to_dict("records")
            return sbml_text, True, True, process_info["output"], data, False
        return sbml_text, True, False, process_info["output"], [], True

    # Save and update annotations
    elif button_id == "update-button" and update_clicks > 0 and table_data:
        # Instant feedback
        instant_feedback = "Updating AMAS annotation..."
        
        # Save user modifications to `recommendations.csv`, keeping only UPDATE ANNOTATION column
        df_to_save = pd.DataFrame(table_data)
        df_to_save.to_csv(csv_output_path, index=False)

        try:
            subprocess.run(
                ["python", amas_update_path, "uploaded_model.xml", csv_output_path, "new_model.xml"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            with open("new_model.xml", "r") as f:
                updated_model_content = f.read()
            return updated_model_content, True, True, "Model with AMAS annotation updated successfully.", table_data, False

        except subprocess.CalledProcessError as e:
            return "", True, True, f"Error updating annotation: {e.output}", table_data, True

    return sbml_text, True, True, amas_output, table_data, True

# Run the Dash app
if __name__ == "__main__":
    app.run_server(debug=True)
