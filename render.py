import json
import os
import folium
from pathlib import Path
import argparse

def summarize_frames(frames):
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html>")
    html.append("<head>")
    html.append("<meta charset='utf-8' />")
    html.append("<title>All Frames</title>")
    html.append("<style>")
    html.append("""
      body { margin:0; padding:0; font-family: sans-serif; }
      h3 { background: #eee; margin: 0; padding: 8px; }
      .frameLine {
        display: block;
        padding: 5px;
        border-bottom: 1px solid #ccc;
        text-decoration: none;
        color: #000;
      }
      .frameLine:target {
        background-color: yellow;
      }
    """)
    html.append("</style>")
    html.append("</head>")
    html.append("<body>")
    html.append("<h3>All Frames (Events)</h3>")
    html.append("<div>")
    for i, frame in enumerate(frames):
        anchor_id = f"frame{i}"
        desc_safe = frame["description"].replace("<", "&lt;").replace(">", "&gt;")
        line_html = (
            f"<a id='{anchor_id}' name='{anchor_id}' "
            f"class='frameLine'>Frame {i}: {desc_safe}</a>"
        )
        html.append(line_html)
    html.append("</div>")
    html.append("</body>")
    html.append("</html>")
    return "\n".join(html)

def color_hex_to_folium_icon(hex_color):
    c = hex_color.strip().lower()
    if c.startswith("#"):
        c = c[1:]
    if len(c) == 3:
        c = "".join(ch*2 for ch in c)
    try:
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
    except ValueError:
        return "blue"
    named_colors = {
        "red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 255, 0),
        "purple": (128, 0, 128), "orange": (255, 165, 0), "darkred": (139, 0, 0),
        "lightred": (255, 102, 102), "beige": (245, 245, 220),
        "darkblue": (0, 0, 139), "darkgreen": (0, 100, 0),
        "cadetblue": (95, 158, 160), "darkpurple": (48, 25, 52),
        "white": (255, 255, 255), "pink": (255, 192, 203),
        "lightblue": (173, 216, 230), "lightgreen": (144, 238, 144),
        "gray": (128, 128, 128), "black": (0, 0, 0), "lightgray": (211, 211, 211),
    }
    best_color = "blue"
    best_dist = float("inf")
    for name, (nr, ng, nb) in named_colors.items():
        dist_sq = (r - nr)**2 + (g - ng)**2 + (b - nb)**2
        if dist_sq < best_dist:
            best_dist = dist_sq
            best_color = name
    return best_color

def create_map_for_frame(frame, global_bounds, output_path):
    all_coords = []

    for tag in frame.get("tags", []):
        all_coords.append(tag["position"])
    for line in frame.get("lines", []):
        all_coords.append(line["start"])
        all_coords.append(line["end"])

    if all_coords:
        lats, lngs = zip(*all_coords)
        frame_bounds = [[min(lats), min(lngs)], [max(lats), max(lngs)]]
        m = folium.Map()
        m.fit_bounds(frame_bounds)
    elif global_bounds:
        m = folium.Map()
        m.fit_bounds(global_bounds)
    else:
        m = folium.Map()

    for tag in frame.get("tags", []):
        lat, lng = tag["position"]
        icon_type = tag.get("icon", "info-sign")
        color_hex = tag.get("color", "#0000FF")
        desc_text = tag.get("description", "")
        folium_color = color_hex_to_folium_icon(color_hex)
        popup_str = f"{desc_text} (icon: {icon_type})"
        folium.Marker(
            location=[lat, lng],
            popup=popup_str,
            icon=folium.Icon(color=folium_color, icon=icon_type, prefix="fa")
        ).add_to(m)

    for line in frame.get("lines", []):
        start_lat, start_lng = line["start"]
        end_lat, end_lng = line["end"]
        line_color_hex = line["color"]
        folium.PolyLine(
            locations=[(start_lat, start_lng), (end_lat, end_lng)],
            color=line_color_hex,
            weight=4
        ).add_to(m)

    m.save(output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate Folium maps from frames JSON data")
    parser.add_argument("--input_file", type=str, default="route.json",
                        help="JSON file containing frames data (default: route.json)")
    parser.add_argument("--output_dir", type=str, default="route_output",
                        help="Output directory to save maps (default: route_output)")
    args = parser.parse_args()

    input_file = args.input_file
    output_dir = args.output_dir

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    frames = data["frames"]
    os.makedirs(output_dir, exist_ok=True)

    # Global bounding box (fallback only)
    min_lat, max_lat = 90.0, -90.0
    min_lng, max_lng = 180.0, -180.0
    for frame in frames:
        for tag in frame.get("tags", []):
            lat, lng = tag["position"]
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lng = min(min_lng, lng)
            max_lng = max(max_lng, lng)
        for line in frame.get("lines", []):
            slat, slng = line["start"]
            elat, elng = line["end"]
            min_lat = min(min_lat, slat, elat)
            max_lat = max(max_lat, slat, elat)
            min_lng = min(min_lng, slng, elng)
            max_lng = max(max_lng, slng, elng)

    global_bounds = [[min_lat, min_lng], [max_lat, max_lng]] if min_lat <= max_lat and min_lng <= max_lng else None

    all_frames_html = summarize_frames(frames)
    all_frames_path = os.path.join(output_dir, "all_frames.html")
    with open(all_frames_path, "w", encoding="utf-8") as f:
        f.write(all_frames_html)

    for i, frame in enumerate(frames):
        map_filename = f"event_{i}.html"
        map_path = os.path.join(output_dir, map_filename)
        create_map_for_frame(frame, global_bounds, map_path)

    total_frames = len(frames)
    master_html_path = os.path.join(output_dir, "_master.html")
    with open(master_html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Frames Master View</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    #controls {{
      background: #ececec;
      padding: 5px;
      flex: 0 0 auto;
    }}
    #mainContainer {{
      flex: 1 1 auto;
      display: flex;
      flex-direction: row;
      height: calc(100vh - 40px);
    }}
    #leftPane, #rightPane {{
      flex: 1 1 50%;
      border: none;
    }}
    button {{
      margin: 0 10px;
      padding: 6px 12px;
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <div id="controls">
    <button id="prevBtn">Previous</button>
    <span id="info"></span>
    <button id="nextBtn">Next</button>
  </div>

  <div id="mainContainer">
    <iframe id="leftPane"></iframe>
    <iframe id="rightPane"></iframe>
  </div>

  <script>
    let current = 0;
    let maxIndex = {total_frames} - 1;
    const leftFrame = document.getElementById('leftPane');
    const rightFrame = document.getElementById('rightPane');
    const infoSpan = document.getElementById('info');

    function updateView() {{
      leftFrame.src = "event_" + current + ".html";
      rightFrame.src = "all_frames.html#frame" + current;
      infoSpan.textContent = "Frame " + current + " / " + maxIndex;
    }}

    document.getElementById('prevBtn').addEventListener('click', () => {{
      if (current > 0) {{
        current--;
        updateView();
      }}
    }});

    document.getElementById('nextBtn').addEventListener('click', () => {{
      if (current < maxIndex) {{
        current++;
        updateView();
      }}
    }});

    updateView();
  </script>
</body>
</html>
""")

    print(f"Done! Open '{master_html_path}' in your browser to view the frames.")
    print("Use the Previous/Next buttons to change frames. The left pane shows the map; the right pane lists all events.")

if __name__ == "__main__":
    main()
