import json
import re
import sys
from pathlib import Path


ENTITY_RE = re.compile(r"^\s*#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\((.*)\)\s*;\s*$", re.S)


def split_values(text: str) -> list[str]:
    values: list[str] = []
    start = 0
    depth = 0
    quoted = False
    i = 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    i += 2
                    continue
                quoted = False
        elif ch == "'":
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            values.append(text[start:i].strip())
            start = i + 1
        i += 1
    values.append(text[start:].strip())
    return values if values != [""] else []


def parse_value(value: str):
    value = value.strip()
    if value in {"$", "*"}:
        return value
    if value.startswith("#") and value[1:].isdigit():
        return {"ref": int(value[1:])}
    if value.startswith("(") and value.endswith(")"):
        return [parse_value(item) for item in split_values(value[1:-1])]
    if value.startswith("'") and value.endswith("'"):
        return {"string": value[1:-1].replace("''", "'") , "raw": value}
    if value.startswith(".") and value.endswith("."):
        return {"enum": value[1:-1], "raw": value}
    typed = re.match(r"^([A-Za-z0-9_]+)\((.*)\)$", value, re.S)
    if typed:
        return {"type": typed.group(1), "value": parse_value(typed.group(2))}
    try:
        return float(value) if any(c in value for c in ".Ee") else int(value)
    except ValueError:
        return {"raw": value}


def read_records(path: Path):
    record = ""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as source:
        in_header = True
        for line in source:
            if in_header:
                if line.strip().upper() == "DATA;":
                    in_header = False
                continue
            record += line
            if ";" not in line:
                continue
            for match in re.finditer(r"#\d+\s*=.*?;", record, re.S):
                yield match.group(0)
            record = record[record.rfind(";") + 1 :]


def read_header(path: Path) -> str:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as source:
        for line in source:
            lines.append(line)
            if line.strip().upper() == "DATA;":
                break
    return "".join(lines)


def header_sections(header: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("ISO-10303-21", "HEADER", "FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA", "ENDSEC", "DATA"):
        result[name] = ""
    for section in ("FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA"):
        start = re.search(section + r"\s*\(", header, re.I)
        if not start:
            continue
        pos = start.start()
        quoted = False
        end = pos
        while end < len(header):
            ch = header[end]
            if quoted:
                if ch == "'":
                    if end + 1 < len(header) and header[end + 1] == "'":
                        end += 2
                        continue
                    quoted = False
            elif ch == "'":
                quoted = True
            elif ch == ";":
                break
            end += 1
        result[section] = header[pos : end + 1]
    result["raw"] = header
    return result


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: ifc_to_json.py input.ifc output.json")
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8", newline="\n") as output:
        output.write("{\n  \"source_file\": ")
        json.dump(str(source), output, ensure_ascii=False)
        output.write(",\n  \"file_size_bytes\": ")
        output.write(str(source.stat().st_size))
        output.write(",\n  \"header\": ")
        json.dump(header_sections(read_header(source)), output, ensure_ascii=False)
        output.write(",\n  \"entities\": [\n")
        first = True
        for raw in read_records(source):
            match = ENTITY_RE.match(raw)
            if not match:
                continue
            entity_id = int(match.group(1))
            entity_type = match.group(2).upper()
            attributes = split_values(match.group(3))
            if not first:
                output.write(",\n")
            first = False
            json.dump(
                {
                    "id": entity_id,
                    "type": entity_type,
                    "attribute_count": len(attributes),
                    "attributes": [parse_value(item) for item in attributes],
                    "raw": raw,
                },
                output,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            count += 1
            if count % 100000 == 0:
                print(f"parsed {count} entities", file=sys.stderr, flush=True)
        output.write("\n  ],\n  \"entity_count\": ")
        output.write(str(count))
        output.write("\n}\n")
    print(f"wrote {count} entities to {target}")


if __name__ == "__main__":
    main()
