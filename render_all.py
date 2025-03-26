import os
import glob
import subprocess

def render_all_frames(input_folder="output", output_base="maps"):
    json_files = glob.glob(os.path.join(input_folder, "*.json"))
    if not json_files:
        print("No JSON files found to render.")
        return

    for json_path in json_files:
        file_name = os.path.basename(json_path)
        scenario_name = os.path.splitext(file_name)[0]
        output_dir = os.path.join(output_base, scenario_name)

        print(f"Rendering {file_name} -> {output_dir}...")
        
        subprocess.run([
            "python", "render.py",
            "--input_file", json_path,
            "--output_dir", output_dir
        ], check=True)

    print("Done rendering all JSON files!")

if __name__ == "__main__":
    render_all_frames()
