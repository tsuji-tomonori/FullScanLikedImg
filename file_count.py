from pathlib import Path

root = Path.cwd()
yyyys = [dir_path for dir_path in root.iterdir() if dir_path.is_dir()]
mms = [dir_path for y in yyyys for dir_path in y.iterdir() if dir_path.is_dir()]
dds = [dir_path for m in mms for dir_path in m.iterdir() if dir_path.is_dir()]

for dd in dds:
    files = [file for file in dd.iterdir() if file.suffix in [".png"]]
    print(f"{dd}: {len(files)}")
