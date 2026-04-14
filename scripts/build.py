import json, os, requests, subprocess, glob

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True)

def fetch_srs_as_json(url, name):
    resp = requests.get(url)
    with open(f"{name}.srs", "wb") as f:
        f.write(resp.content)
    res = subprocess.check_output(f"sing-box rule-set decompile {name}.srs", shell=True)
    os.remove(f"{name}.srs")
    return json.loads(res)

def compile_data(data, name):
    with open(f"{name}.json", "w") as f:
        json.dump(data, f)
    run_cmd(f"sing-box rule-set compile --output output/{name}.srs {name}.json")
    os.remove(f"{name}.json")

def main():
    with open("config.json", "r") as f:
        conf = json.load(f)
    
    os.makedirs("output", exist_ok=True)
    os.makedirs("geolite2", exist_ok=True)

    for task in conf["tasks"]:
        name = task["name"]
        t = task["type"]

        if t == "local_compile":
            run_cmd(f"sing-box rule-set compile --output output/{name}.srs {task['path']}")

        elif t == "geoip_build":
            geo_urls = conf["metadata"]["geolite2_urls"]
            for key, url in geo_urls.items():
                dest = f"geolite2/{os.path.basename(url)}"
                if not os.path.exists(dest):
                    r = requests.get(url)
                    with open(dest, "wb") as f:
                        f.write(r.content)
            
            if os.path.exists("./geoip-tool"):
                run_cmd("./geoip-tool convert -c config.json")
                
            ip_list = []
            for txt in glob.glob("output/text/*.txt"):
                with open(txt, "r") as f:
                    ip_list.extend([line.strip() for line in f if line.strip()])
            
            geo_json = {
                "version": 1,
                "rules": [{"ip_cidr": list(set(ip_list))}]
            }
            compile_data(geo_json, name)

        elif t == "srs_diff":
            full = fetch_srs_as_json(task["full_url"], "full")
            lite = fetch_srs_as_json(task["lite_url"], "lite")
            lite_raw = {json.dumps(r, sort_keys=True) for r in lite.get("rules", [])}
            diff = [r for r in full.get("rules", []) if json.dumps(r, sort_keys=True) not in lite_raw]
            full["rules"] = diff
            compile_data(full, name)

if __name__ == "__main__":
    main()
