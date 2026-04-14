import json
import os
import requests
import subprocess
import glob
import ipaddress

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True)

def fetch_srs_as_json(url, name):
    resp = requests.get(url)
    srs_path = f"{name}_temp.srs"
    with open(srs_path, "wb") as f:
        f.write(resp.content)
    res = subprocess.check_output(f"sing-box rule-set decompile {srs_path}", shell=True)
    if os.path.exists(srs_path):
        os.remove(srs_path)
    return json.loads(res)

def compile_data(data, name):
    temp_json = f"{name}_temp.json"
    with open(temp_json, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    run_cmd(f"sing-box rule-set compile --output output/{name}.srs {temp_json}")
    if os.path.exists(temp_json):
        os.remove(temp_json)

def optimize_cidrs(cidr_list):
    try:
        networks = []
        for ip in set(cidr_list):
            ip = ip.strip()
            if ip:
                networks.append(ipaddress.ip_network(ip))
        optimized = ipaddress.collapse_addresses(networks)
        return [str(ip) for ip in optimized]
    except Exception:
        return list(set(cidr_list))

def main():
    with open("config.json", "r", encoding='utf-8') as f:
        conf = json.load(f)
    
    os.makedirs("output", exist_ok=True)
    os.makedirs("geolite2", exist_ok=True)

    geo_urls = conf.get("metadata", {}).get("geolite2_urls", {})
    for key, url in geo_urls.items():
        dest = f"geolite2/{os.path.basename(url)}"
        if not os.path.exists(dest):
            r = requests.get(url)
            with open(dest, "wb") as f:
                f.write(r.content)

    for task in conf["tasks"]:
        name = task["name"]
        t = task["type"]

        if t == "local_compile":
            run_cmd(f"sing-box rule-set compile --output output/{name}.srs {task['path']}")

        elif t == "geoip_build":
            if os.path.exists("./geoip-tool"):
                run_cmd("./geoip-tool convert --config config.json")
            
            raw_ips = []
            for txt in glob.glob("output/text/*.txt"):
                with open(txt, "r") as f:
                    raw_ips.extend(f.readlines())
            
            optimized_ips = optimize_cidrs(raw_ips)
            
            geo_json = {
                "version": 1,
                "rules": [{"ip_cidr": optimized_ips}]
            }
            compile_data(geo_json, name)

        elif t == "srs_diff":
            full = fetch_srs_as_json(task["full_url"], f"{name}_full")
            lite = fetch_srs_as_json(task["lite_url"], f"{name}_lite")
            
            lite_raw = {json.dumps(r, sort_keys=True) for r in lite.get("rules", [])}
            diff = [r for r in full.get("rules", []) if json.dumps(r, sort_keys=True) not in lite_raw]
            
            full["rules"] = diff
            compile_data(full, name)

if __name__ == "__main__":
    main()
