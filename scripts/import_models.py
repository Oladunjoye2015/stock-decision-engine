import argparse, hashlib, json, shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Copy an approved model into this repository; never links to source runtime state.")
    p.add_argument("source", type=Path); p.add_argument("--name", required=True); args = p.parse_args()
    destination = Path("model_artifacts/artifacts") / args.name; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(args.source, destination)
    print(json.dumps({"artifact": str(destination), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}))


if __name__ == "__main__": main()

