"""
Rad Architecture Blueprint Generator
Maps every file, import, and connection into a visual synapse graph.
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Color Palette for HTML ---
PALETTE = {
    "core": "#ff6b6b",         # Red - Central nervous system
    "organism": "#4ecdc4",      # Teal - The body/digital organism
    "supervisor": "#ffe66d",   # Yellow - The watcher
    "brain": "#a8e6cf",        # Green - Neural logic
    "agent": "#fd79a8",        # Pink - Agency/Action
    "tools": "#dfe6e9",        # Grey - Tools/Extensions
    "vault": "#b2bec3",        # Stone - Memory storage
    "soul": "#ff7675",         # Crimson - The immutable
    "media": "#74b9ff",        # Blue - Multimodal I/O
    "migrations": "#636e72",   # Dark - Infrastructure
    "default": "#a29bfe",      # Purple - Unknown/Other
}


def get_color(path_obj: Path) -> str:
    """Assign a neural color based on directory/file role."""
    parts = path_obj.parts
    name = path_obj.name.lower()
    
    if "soul.txt" in name:
        return PALETTE["soul"]
    if "vault" in parts:
        return PALETTE["vault"]
    if "media" in parts:
        return PALETTE["media"]
    if "migrations" in parts:
        return PALETTE["migrations"]
    if "supervisor" in parts or "supervisor" in name:
        return PALETTE["supervisor"]
    if "brain" in name:
        return PALETTE["brain"]
    if "agent" in name:
        return PALETTE["agent"]
    if "tools" in name:
        return PALETTE["tools"]
    
    for key in ["core", "organism"]:
        if key in parts:
            return PALETTE[key]
    
    return PALETTE["default"]


def extract_imports(file_path: Path) -> list:
    """Parse Python files for import statements (synaptic connections)."""
    connections = []
    if not file_path.suffix == ".py":
        return connections
    
    try:
        content = file_path.read_text(errors="ignore")
    except Exception:
        return connections
    
    # Match 'import x' and 'from x import y'
    imports = re.findall(r"^(?:import|from)\s+([\w\.]+)", content, re.MULTILINE)
    
    for imp in imports:
        # Map to local project structure
        imp_parts = imp.split(".")
        
        # Heuristic: check if import maps to a local file/directory
        for i in range(len(imp_parts), 0, -1):
            partial = Path(*imp_parts[:i])
            candidate = PROJECT_ROOT / partial
            if candidate.exists() or (candidate.with_suffix(".py")).exists():
                rel_path = os.path.relpath(candidate, PROJECT_ROOT)
                connections.append(rel_path)
                break
    
    return connections


def build_blueprint():
    """Crawl the directory tree and build the neural map."""
    nodes = []
    edges = []
    id_map = {}
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Ignore hidden/venv/cache
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "venv" and d != "__pycache__"]
        
        for file in files:
            if file.startswith(".") or file.endswith(".pyc"):
                continue
            
            full_path = Path(root) / file
            rel_path = os.path.relpath(full_path, PROJECT_ROOT)
            
            node_id = len(nodes)
            id_map[rel_path] = node_id
            
            nodes.append({
                "id": node_id,
                "label": rel_path,
                "color": get_color(full_path),
                "size": 10 + (5 if ".py" in file else 0),  # Python files are larger nodes
            })
    
    # Second pass: Build edges (synapses)
    for node in nodes:
        rel_path = node["label"]
        full_path = PROJECT_ROOT / rel_path
        
        imports = extract_imports(full_path)
        
        for imp in imports:
            if imp in id_map:
                edges.append({
                    "source": node["id"],
                    "target": id_map[imp],
                    "value": 1
                })
    
    return {"nodes": nodes, "edges": edges}


def generate_html(blueprint_data: dict, output_path: str = "rad_blueprint.html"):
    """Generate a self-contained interactive D3.js force-directed graph."""
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rad :: Neural Architecture Blueprint</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0; background: #0f0f13; color: #e0e0e0; font-family: 'Courier New', monospace;
            overflow: hidden; display: flex; flex-direction: column; height: 100vh;
        }}
        #header {{
            padding: 15px 25px; background: #1a1a24; border-bottom: 1px solid #333;
            display: flex; justify-content: space-between; align-items: center;
        }}
        h1 {{ margin: 0; font-size: 1.2rem; color: #4ecdc4; letter-spacing: 1px; }}
        #stats {{ font-size: 0.8rem; color: #888; }}
        #viz {{ flex: 1; position: relative; }}
        .node {{ stroke: #fff; stroke-width: 1.5px; cursor: pointer; transition: all 0.3s ease; }}
        .node:hover {{ stroke: #ffe66d; stroke-width: 3px; filter: drop-shadow(0 0 8px rgba(78, 205, 196, 0.6)); }}
        .link {{ stroke: #555; stroke-opacity: 0.6; stroke-width: 1px; }}
        text {{ font-family: monospace; font-size: 10px; pointer-events: none; fill: #ccc; opacity: 0; transition: opacity 0.3s; }}
        .node:hover + text, text:hover {{ opacity: 1; }}
        #tooltip {{
            position: absolute; background: rgba(0,0,0,0.85); border: 1px solid #4ecdc4;
            padding: 8px 12px; border-radius: 4px; font-size: 12px; pointer-events: none;
            display: none; z-index: 10; max-width: 300px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }}
        .legend {{
            position: absolute; bottom: 20px; left: 20px; background: rgba(20,20,30,0.8);
            padding: 15px; border-radius: 8px; border: 1px solid #333; font-size: 0.8rem;
        }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 6px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>RAD // NEURAL ARCHITECTURE BLUEPRINT</h1>
        <div id="stats">Nodes: {len(blueprint_data['nodes'])} | Synapses: {len(blueprint_data['edges'])} | Status: ONLINE</div>
    </div>
    <div id="viz">
        <div id="tooltip"></div>
        <div class="legend">
            <div style="margin-bottom:10px; font-weight:bold; color:#4ecdc4;">NEURAL REGIONS</div>
            <div class="legend-item"><div class="legend-color" style="background:#ff6b6b"></div>Core (Nervous System)</div>
            <div class="legend-item"><div class="legend-color" style="background:#4ecdc4"></div>Organism (Body)</div>
            <div class="legend-item"><div class="legend-color" style="background:#ffe66d"></div>Supervisor (Watcher)</div>
            <div class="legend-item"><div class="legend-color" style="background:#a8e6cf"></div>Brain (Logic)</div>
            <div class="legend-item"><div class="legend-color" style="background:#fd79a8"></div>Agent (Action)</div>
            <div class="legend-item"><div class="legend-color" style="background:#ff7675"></div>Soul (Immutable)</div>
            <div class="legend-item"><div class="legend-color" style="background:#74b9ff"></div>Media (I/O)</div>
            <div class="legend-item"><div class="legend-color" style="background:#b2bec3"></div>Vault (Memory)</div>
        </div>
    </div>

    <script>
        const data = {json.dumps(blueprint_data)};
        
        const width = document.getElementById('viz').clientWidth;
        const height = document.getElementById('viz').clientHeight;
        
        const svg = d3.select("#viz").append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", [0, 0, width, height]);
        
        // Zoom capability
        const g = svg.append("g");
        svg.call(d3.zoom().on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }}));
        
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.edges).id(d => d.id).distance(80))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(d => d.size + 5));
        
        // Links (Synapses)
        const link = g.append("g")
            .selectAll("line")
            .data(data.edges)
            .join("line")
            .attr("class", "link");
        
        // Nodes (Neurons)
        const node = g.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .join("circle")
            .attr("class", "node")
            .attr("r", d => d.size)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", (event, d) => {{
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x; d.fy = d.y;
                }})
                .on("drag", (event, d) => {{
                    d.fx = event.x; d.fy = event.y;
                }})
                .on("end", (event, d) => {{
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null; d.fy = null;
                }}));
        
        // Labels
        const labels = g.append("g")
            .selectAll("text")
            .data(data.nodes)
            .join("text")
            .attr("dx", 12)
            .attr("dy", 4)
            .text(d => d.label);
        
        // Tooltip logic
        const tooltip = d3.select("#tooltip");
        
        node.on("mouseover", (event, d) => {{
            tooltip.style("display", "block")
                .html(`<strong style='color:#4ecdc4'>${{d.label}}</strong><br/>
                       <span style='color:#888'>Type:</span> ${{d.label.split('.').pop()}}<br/>
                       <span style='color:#888'>Size:</span> ${{d.size}}<br/>
                       <span style='color:#888'>Connections:</span> ${{data.edges.filter(e => e.source.id === d.id || e.target.id === d.id).length}}`)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 15) + "px");
        }})
        .on("mouseout", () => tooltip.style("display", "none"));
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            labels
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }});
        
        // Pulse animation for core nodes
        setInterval(() => {{
            node.transition().duration(1000)
                .attr("r", d => d.size * 1.2)
                .transition().duration(1000)
                .attr("r", d => d.size);
        }}, 2000);
    </script>
</body>
</html>"""
    
    output_file = PROJECT_ROOT / output_path
    output_file.write_text(html_template)
    return str(output_file)


if __name__ == "__main__":
    print("[RAD] Generating Neural Architecture Blueprint...")
    blueprint = build_blueprint()
    path = generate_html(blueprint)
    print(f"[SUCCESS] Blueprint generated: {path}")
    print(f"[STATS] Nodes: {len(blueprint['nodes'])} | Synapses: {len(blueprint['edges'])}")
