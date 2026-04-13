import os
import yaml


def load_yaml_files(file1: str, file2: str):
    if not os.path.exists(file1):
        raise FileNotFoundError(f"YAML file not found: {file1}")
    if not os.path.exists(file2):
        raise FileNotFoundError(f"YAML file not found: {file2}")

    with open(file1, "r", encoding="utf-8") as f:
        data1 = yaml.safe_load(f)
    with open(file2, "r", encoding="utf-8") as f:
        data2 = yaml.safe_load(f)

    if data1 is None:
        data1 = []
    if data2 is None:
        data2 = []

    if not isinstance(data1, list):
        raise ValueError(f"Expected list at top level of {file1}")
    if not isinstance(data2, list):
        raise ValueError(f"Expected list at top level of {file2}")

    return data1, data2


def compare_names(file1: str, file2: str, output_file: str):
    data1, data2 = load_yaml_files(file1, file2)

    names1 = {str(item.get("name", "")).strip() for item in data1 if item and item.get("name") is not None}
    names2 = {str(item.get("name", "")).strip() for item in data2 if item and item.get("name") is not None}

    diff1 = sorted(names1 - names2)
    diff2 = sorted(names2 - names1)

    if not diff1 and not diff2:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("NO DIFFERENCES IN REGARDS TO ELEMENT NAMES")
        return

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Names in file1 but not in file2:\n")
        if diff1:
            f.write("\n".join(diff1))
        f.write("\n\n")
        f.write("Names in file2 but not in file1:\n")
        if diff2:
            f.write("\n".join(diff2))


def _normalize_requirements(requirements):
    if requirements is None:
        return []
    if isinstance(requirements, str):
        return [requirements.strip()]
    if not isinstance(requirements, list):
        return [str(requirements).strip()]
    return [str(r).strip() for r in requirements if r is not None]


def compare_full(file1: str, file2: str, output_file: str):
    data1, data2 = load_yaml_files(file1, file2)

    def build_map(data):
        result = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name is None:
                continue
            name = str(name).strip()
            result[name] = _normalize_requirements(item.get("requirements"))
        return result

    map1 = build_map(data1)
    map2 = build_map(data2)

    diff1 = []
    diff2 = []

    names_all = sorted(set(map1) | set(map2))
    for name in names_all:
        if name not in map2:
            diff1.append((name, map1[name]))
        elif name not in map1:
            diff2.append((name, map2[name]))
        else:
            reqs1 = map1[name]
            reqs2 = map2[name]
            if reqs1 != reqs2:
                diff1.append((name, reqs1))
                diff2.append((name, reqs2))

    if not diff1 and not diff2:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS")
        return

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("KDEs in file1 but not in file2 or with different requirements:\n")
        if diff1:
            for name, reqs in diff1:
                f.write(f"file1: {name}, requirements: {reqs}\n")
        f.write("\n")
        f.write("KDEs in file2 but not in file1 or with different requirements:\n")
        if diff2:
            for name, reqs in diff2:
                f.write(f"file2: {name}, requirements: {reqs}\n")
