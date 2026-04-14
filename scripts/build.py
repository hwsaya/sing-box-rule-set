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

def get_lite_values(rules):
    lite_values = set()
    condition_keys = {"domain", "domain_suffix", "domain_keyword", "domain_regex", "geosite", "ip_cidr", "ip_cidr_ext"}
    def _extract(r_list):
        for r in r_list:
            if "rules" in r and isinstance(r["rules"], list):
                _extract(r["rules"])
            for k, v in r.items():
                if k in condition_keys:
                    if isinstance(v, list):
                        lite_values.update(str(x).strip().lstrip('.') for x in v)
                    else:
                        lite_values.add(str(v).strip().lstrip('.'))
    _extract(rules)
    return lite_values

def filter_rules(rules, lite_values):
    condition_keys = {"domain", "domain_suffix", "domain_keyword", "domain_regex", "geosite", "ip_cidr", "ip_cidr_ext"}
    diff = []
    for r in rules:
        new_rule = {}
        has_condition = False
        for k, v in r.items():
            if k == "rules" and isinstance(v, list):
                filtered_sub = filter_rules(v, lite_values)
                if filtered_sub:
                    new_rule[k] = filtered_sub
                    has_condition = True
            elif k in condition_keys:
                if isinstance(v, list):
                    filtered = [x for x in v if str(x).strip().lstrip('.') not in lite_values]
                    if filtered:
                        new_rule[k] = filtered
                        has_condition = True
                elif str(v).strip().lstrip('.') not in lite_values:
                    new_rule[k] = v
                    has_condition = True
            else:
                new_rule[k] = v
                
        if "type" in new_rule and new_rule["type"] == "logical":
            if "rules" in new_rule and new_rule["rules"]:
                diff.append(new_rule)
        elif has_condition:
            diff.append(new_rule)
            
    return diff

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
            
            # 提取特征池
            lite_values = get_lite_values(lite.get("rules", []))
            print(f"[{name}] 提取到 Lite 规则条件数量: {len(lite_values)}")
            
            # 执行过滤
            full_rules_len = len(full.get("rules", []))
            diff_rules = filter_rules(full.get("rules", []), lite_values)
            print(f"[{name}] 完整规则条数: {full_rules_len} -> 过滤后条数: {len(diff_rules)}")
            
            full["rules"] = diff_rules
            compile_data(full, name)

if __name__ == "__main__":
    main()
