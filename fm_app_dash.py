import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import networkx as nx
import dash_cytoscape as cyto
import plotly.graph_objects as go
import pandas as pd

# Load nodes and edges
nodes_df = pd.read_csv('nodes.csv')
edges_df = pd.read_csv('edges.csv')

# Create graph
G = nx.from_pandas_edgelist(edges_df, 'source', 'target', create_using=nx.Graph())

# Adding missing nodes to the graph if they don't exist
for name in nodes_df['name']:
    if name not in G:
        G.add_node(name)  # Add node if it does not exist

# Add node attributes from nodes_df 
for idx, row in nodes_df.iterrows():
    G.nodes[row['name']].update(row.to_dict())

# Identify orphaned nodes (nodes with a degree of 0)
orphaned_nodes = [node for node, degree in G.degree() if degree == 0]

# Drop orphaned nodes from graph
G.remove_nodes_from(orphaned_nodes)

# Prepare the Dash app
app = dash.Dash(__name__, external_stylesheets=['https://github.com/ddorrell-79/fm_app_crfm/blob/main/styles.css'])
server = app.server

# App layout
app.layout = html.Div([
    # Top bar with logo and description
    html.Div([
        html.Img(src='https://github.com/ddorrell-79/fm_app_crfm/blob/main/frontierlogothin.png', style={'height': '50px', 'margin-right': '20px'}),
        html.Div(id='node-description', style={'flex-grow': '1', 'text-align': 'right'}),
    ], style={'display': 'flex', 'align-items': 'center', 'justify-content': 'space-between', 'padding': '10px', 'border-bottom': '1px solid #ccc'}),
    
    # Sidebar with dropdowns, legend, and source link
    html.Div([
        html.Div([
            dcc.Dropdown(
                id='name-dropdown',
                options=[{'label': node, 'value': node} for node in sorted(G.nodes())],
                placeholder="Select a name",
                multi=True,
                style={'margin-bottom': '10px'}
            ),
            dcc.Dropdown(
                id='organization-dropdown',
                options=[{'label': org, 'value': org} for org in sorted(nodes_df['organization'].unique())],
                placeholder="Select an organization",
                multi=True,
                style={'margin-bottom': '10px'}
            ),
            # Legend
            html.Div([
                html.H4("Legend", style={'text-align': 'left'}),
                html.Div([
                    html.Div([
                        html.Span(style={'background-color': 'blue', 'display': 'inline-block', 'width': '20px', 'height': '20px', 'margin-right': '5px'}),
                        html.Span("Model")
                    ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '5px'}),
                    html.Div([
                        html.Span(style={'background-color': 'yellow', 'display': 'inline-block', 'width': '20px', 'height': '20px', 'margin-right': '5px'}),
                        html.Span("Dataset")
                    ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '5px'}),
                    html.Div([
                        html.Span(style={'background-color': 'red', 'display': 'inline-block', 'width': '20px', 'height': '20px', 'margin-right': '5px'}),
                        html.Span("Application")
                    ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '5px'}),
                ])
            ], style={'margin-bottom': '20px', 'border-top': '1px solid #ccc', 'padding-top': '10px'}),
            # Source Link
            html.Div([
                html.H4("Source", style={'text-align': 'left'}),
                html.A("Original Data Source: Stanford Center for Research on Foundation Models", href="https://crfm.stanford.edu/ecosystem-graphs/index.html?mode=graph", target="_blank"),
            ], style={'margin-bottom': '20px', 'border-top': '1px solid #ccc', 'padding-top': '10px'})
        ], style={'width': '250px', 'padding': '10px', 'border-right': '1px solid #ccc'}),
        
        # Main content with Cytoscape graph
        html.Div([
            cyto.Cytoscape(
                id='network-graph',
                layout={'name': 'cose'},
                style={'width': '100%', 'height': '80vh'},
                stylesheet=[
                    {'selector': 'node', 'style': {'label': 'data(label)', 'background-color': 'data(color)'}},
                    {'selector': 'edge', 'style': {'line-color': '#888', 'width': 0.5}},
                    {'selector': ':selected', 'style': {'border-color': 'blue', 'border-width': 2}}
                ],
                elements=[]
            )
        ], style={'flex-grow': '1', 'padding': '10px'})
    ], style={'display': 'flex', 'height': 'calc(100vh - 70px)'})
])

@app.callback(
    Output('network-graph', 'elements'),
    [Input('name-dropdown', 'value'),
     Input('organization-dropdown', 'value')]
)

def update_graph(selected_names, selected_organizations):
    if not selected_names:
        selected_names = []
    if not selected_organizations:
        selected_organizations = []

    # Filter nodes based on selections
    filtered_nodes = {
        node for node, attr in G.nodes(data=True)
        if (not selected_names or node in selected_names) and
           (not selected_organizations or attr.get('organization') in selected_organizations)
    }

    nodes_to_include = set(filtered_nodes)
     
    #Loops through selected nodes and expands graph to include up to two steps
    for iteration in range(2):
        current_nodes = set()
        for node in nodes_to_include:
            neighbors = set(G.neighbors(node))  
            current_nodes.update(neighbors)
    
        # If no new nodes are found, break out of the loop early
        if current_nodes.issubset(nodes_to_include):
            break

        nodes_to_include.update(current_nodes)

    #Creates a subgraph of the the nodes
    sub_G = G.subgraph(nodes_to_include)

    #Based on the networkx subgraph, creates elements list that is used the cytoscape class
    elements = []
    for node, attr in sub_G.nodes(data=True):
        color = 'gray'
        
        if attr.get('type') == 'model' : color = 'blue'
        if attr.get('type') == 'dataset' : color = 'yellow'
        if attr.get('type') == 'application' : color = 'red'
        if (node in filtered_nodes and (selected_names or selected_organizations)) : color = 'green' 
        elements.append({
            'data': {'id': node, 'label': node, 'color': color,'description': attr.get('description', '')},
        })

    for source, target in sub_G.edges():
        elements.append({'data': {'source': source, 'target': target}})

    return elements

#callback to display description when node is clicked
@app.callback(
    Output('node-description', 'children'),
    [Input('network-graph', 'tapNodeData')]
)
def display_node_description(data):
      
    if data is None:
        return "Click on a node to see its description."
    return f"Description: {data.get('description', 'No description available')}"

if __name__ == '__main__':
    app.run_server(debug=True)
