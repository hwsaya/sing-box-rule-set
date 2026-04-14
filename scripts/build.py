import json, os, requests, subprocess

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True)

def fetch_and_decompile(url, name):
    print(f"处理上游文件: {name}")
    resp = requests.get(url)
    srs_path = f"temp_{name}.srs"
    with open(srs_path, "wb") as f:
        f.write(resp.content)
    # 调用 sing-box 反编译成 json
    res = subprocess.check_output(f"sing-box rule-set decompile {srs_path}", shell=True)
    os.remove(srs_path)
    return json.loads(res)

def compile_srs(data, output_name):
    temp_json = f"temp_{output_name}.json"
    with open(temp_json, "w") as f:
        json.dump(data, f)
    run_cmd(f"sing-box rule-set compile --output output/{output_name}.srs {temp_json}")
    os.remove(temp_json)

def main():
    with open("config.json", "r") as f:
        config = json.load(f)
    
    os.makedirs("output", exist_ok=True)

    for task in config["tasks"]:
        t = task["type"]
        name = task["name"]

        if t == "local_compile":
            run_cmd(f"sing-box rule-set compile --output output/{name}.srs {task['path']}")

        elif t == "s_diff":
            full = fetch_and_decompile(task["full_url"], "full")
            lite = fetch_and_decompile(task["lite_url"], "lite")
                        
            lite_rules_set = {json.dumps(r, sort_keys=True) for r in lite.get("rules", [])}            
            diff_rules = [r for r in full.get("rules", []) if json.dumps(r, sort_keys=True) not in lite_rules_set]
            
            full["rules"] = diff_rules
            compile_srs(full, name)

        elif t == "geoip_build":            