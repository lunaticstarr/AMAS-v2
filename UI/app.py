import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import base64
import subprocess
from pathlib import Path
import os
import threading

csv_output_path = os.path.join(os.getcwd(), "recommendations.csv")  # Full path to CSV
amas_path = "/Users/luna/Desktop/CRBM/AMAS_proj/AMAS-v2/AMAS/recommend_annotation.py"

# Initialize the Dash app
app = dash.Dash(__name__)

# Define the layout of the app
app.layout = html.Div([
    html.H1("AMAS Annotation Tool"),

    # Top Menu with Upload and Annotate Buttons
    html.Div([
        dcc.Upload(
            id='upload-sbml',
            children=html.Button("Upload SBML Model"),
            multiple=False
        ),
        html.Button("Annotate Model", id="annotation-button", n_clicks=0, disabled=True)
    ], style={"display": "flex", "gap": "10px", "margin-bottom": "20px"}),

    # Display the SBML content with limited height and scroll
    html.Div(id='sbml-content', style={"whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px", 
                                       "margin-top": "20px", "maxHeight": "300px", "overflowY": "scroll"}),

    # Section for real-time AMAS processing messages
    html.Div(id="amas-output", style={"whiteSpace": "pre-wrap", "border": "1px solid #ccc", "padding": "10px", 
                                      "margin-top": "20px", "maxHeight": "150px", "overflowY": "scroll"}),

    # Modal (Pop-Up) for displaying CSV Table
    html.Div(
        id="csv-modal",
        style={"display": "none", "position": "fixed", "top": "50%", "left": "50%", "transform": "translate(-50%, -50%)", 
               "backgroundColor": "white", "padding": "20px", "boxShadow": "0 4px 8px rgba(0, 0, 0, 0.2)", "maxWidth": "90%"},
        children=[
            html.H2("Annotation Results"),
            html.Button("Close", id="close-modal", n_clicks=0),
            dash_table.DataTable(
                id="csv-table",
                style_data={
                    'whiteSpace': 'normal',
                    'height': 'auto',
                    'lineHeight': '15px'
                }
            )
        ]
    ),
    
    # Interval component to update AMAS output in real time
    dcc.Interval(id="interval-component", interval=100, n_intervals=0, disabled=True)  # Update every second
])

# Global variable to hold the AMAS process and output
process_info = {"process": None, "output": "", "output_thread": None}

# Function to read output in a separate thread
def read_process_output(process):
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:  # Process complete
            break
        if line:
            process_info["output"] += line  # Append real-time output
        

# Consolidated callback to handle upload, annotation start, real-time output, and modal display
@app.callback(
    [Output("sbml-content", "children"), Output("annotation-button", "disabled"),
     Output("interval-component", "disabled"), Output("amas-output", "children"),
     Output("csv-modal", "style"), Output("csv-table", "data"), Output("csv-table", "columns")],
    [Input("upload-sbml", "contents"), Input("annotation-button", "n_clicks"),
     Input("interval-component", "n_intervals"), Input("close-modal", "n_clicks")],
    [State("sbml-content", "children"), State("amas-output", "children")]
)
def manage_process(contents, annotation_clicks, n_intervals, close_clicks, sbml_text, amas_output):
    global process_info
    ctx = dash.callback_context
    if not ctx.triggered:
        return "", True, True, "", {"display": "none"}, [], []
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Handle SBML upload
    if button_id == "upload-sbml" and contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Save the uploaded SBML as "uploaded_model.xml"
        sbml_file_path = "uploaded_model.xml"
        with open(sbml_file_path, "wb") as sbml_file:
            sbml_file.write(decoded)
        
        sbml_text = decoded.decode("utf-8")
        return sbml_text, False, True, "", {"display": "none"}, [], []

    # Start annotation process on button click
    elif button_id == "annotation-button" and annotation_clicks > 0 and sbml_text:
        try:
            # Start AMAS process asynchronously to capture real-time output
            process_info["process"] = subprocess.Popen(
                ["python", amas_path, "uploaded_model.xml", "--save", "csv", "--outfile", csv_output_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            process_info["output"] = "Starting AMAS annotation...\n"
            
            # Start a new thread to read the output continuously
            process_info["output_thread"] = threading.Thread(target=read_process_output, args=(process_info["process"],))
            process_info["output_thread"].start()

            return sbml_text, True, False, process_info["output"], {"display": "none"}, [], []

        except Exception as e:
            process_info["output"] = f"Error starting AMAS: {e}"
            return sbml_text, True, True, process_info["output"], {"display": "none"}, [], []

    # Real-time update of AMAS output and check if the process has finished
    elif button_id == "interval-component" and process_info["process"] is not None:
        try:
            # Check if the process has completed
            if process_info["process"].poll() is not None:
                # Ensure all output is captured
                process_info["output_thread"].join()  # Wait for thread to finish
                process_info["process"] = None  # Clear process once done

                # Verify CSV file content update
                if os.path.exists(csv_output_path):
                    for _ in range(10):  # Retry up to 10 times with a short delay
                        with open(csv_output_path, "r") as f:
                            if f.read().strip():  # Check if the file has new content
                                break
                        time.sleep(0.5)  # Wait briefly and retry if content not updated

                # Load CSV results after confirmation
                df = pd.read_csv(csv_output_path)
                df = df[['type', 'id', 'display name', 'annotation', 'annotation label', 'match score', 'existing', 'UPDATE ANNOTATION']]
                data = df.to_dict("records")
                columns = [{"name": i, "id": i} for i in df.columns]

                # Disable interval since the process is complete, display results
                return sbml_text, True, True, process_info["output"], {"display": "block"}, data, columns

        except Exception as e:
            process_info["output"] += f"\nError reading AMAS output: {e}"
            process_info["process"] = None  # Ensure process is stopped in case of error

        # Continue returning updated real-time output
        return sbml_text, True, False, process_info["output"], {"display": "none"}, [], []

    # Close modal on button click
    elif button_id == "close-modal" and close_clicks > 0:
        return sbml_text, True, True, amas_output, {"display": "none"}, [], []

    return sbml_text, True, True, amas_output, {"display": "none"}, [], []


# Run the Dash app
if __name__ == "__main__":
    app.run_server(debug=True)
