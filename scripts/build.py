import json
import os
import requests
import subprocess
import glob
import ipaddress

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True)

def fetch_srs_as_json(url, name):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()

def compile_data(data, name):
    temp_json = f"{name}_build.json"
    with open(temp_json, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    run_cmd(f"sing-box rule-set compile --output output/{name}.srs {temp_json}")
    if os.path.exists(temp_json):
        os.remove(temp_json)

def optimize_cidrs(cidr_list):
    clean_ips = [ip.strip() for ip in set(cidr_list) if ip.strip()]
    try:
        networks = [ipaddress.ip_network(ip, strict=False) for ip in clean_ips]
        return [str(ip) for ip in ipaddress.collapse_addresses(networks)]
    except Exception:
        return clean_ips

def filter_rule_items(full_rules, lite_rules):
    lite_items = {}
    for r in lite_rules:
        for k, v in r.items():
            if isinstance(v, list):
                lite_items.setdefault(k, set()).update(v)
            else:
                lite_items.setdefault(k, set()).add(v)

    diff_rules = []
    condition_keys = {"domain", "domain_suffix", "domain_keyword", "domain_regex", "geosite", "ip_cidr", "ip_cidr_ext"}
    for r in full_rules:
        new_rule = {}
        for k, v in r.items():
            if k in lite_items:
                if isinstance(v, list):
                    filtered = [x for x in v if x not in lite_items[k]]
                    if filtered:
                        new_rule[k] = filtered
                elif v not in lite_items[k]:
                    new_rule[k] = v
            else:
                new_rule[k] = v
        
        if any(k in new_rule for k in condition_keys):
            diff_rules.append(new_rule)
    return diff_rules

def main():
    with open("config.json", "r", encoding='utf-8') as f:
        conf = json.load(f)
    os.makedirs("output", exist_ok=True)
    os.makedirs("geolite2", exist_ok=True)

    geo_urls = conf.get("metadata", {}).get("geolite2_urls", {})
    for key, url in geo_urls.items():
        dest = f"geolite2/{os.path.basename(url)}"
        if not os.path.exists(dest):
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(dest, "wb") as f: f.write(r.content)

    for task in conf["tasks"]:
        name, t = task["name"], task["type"]
        if t == "local_compile":
            run_cmd(f"sing-box rule-set compile --output output/{name}.srs {task['path']}")
        elif t == "geoip_build":
            if os.path.exists("./geoip-tool"):
                for c in ["./geoip-tool convert config.json", "./geoip-tool convert", "./geoip-tool"]:
                    try:
                        run_cmd(c)
                        break
                    except: continue
            raw_ips = []
            for txt in glob.glob("output/text/*.txt"):
                with open(txt, "r") as f:
                    raw_ips.extend([line.strip() for line in f.readlines() if line.strip()])
            if raw_ips:
                compile_data({"version": 1, "rules": [{"ip_cidr": optimize_cidrs(raw_ips)}]}, name)
        elif t == "srs_diff":
            full = fetch_srs_as_json(task["full_url"], f"{name}_full")
            lite = fetch_srs_as_json(task["lite_url"], f"{name}_lite")
            
            diff_rules = filter_rule_items(full.get("rules", []), lite.get("rules", []))
            full["rules"] = diff_rules
            compile_data(full, name)

if __name__ == "__main__":
    main()
