#!/usr/bin/env python3
"""Build and open the real HUD view with an isolated, interactive sample session."""
import argparse
import json
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/work-like-musk/scripts/five_step.py"
APP = ROOT / ".build/HUDPreview.app"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "zh-CN"), default="en")
    language = parser.parse_args().language
    project = ROOT / ".build" / ("design-preview-" + language)
    config = project / "hud-config.json"
    project.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"language": language}) + "\n")
    command = [sys.executable, str(CLI)]
    scope = ["--project", str(project), "--task", "design-preview"]
    result = subprocess.run(command + ["setup", *scope, "--title", "设计预览" if language == "zh-CN" else "Design preview", "--no-open"],
                            check=True, capture_output=True, text=True)
    session = json.loads(result.stdout)["statePath"]
    for status in ("in_progress", "completed"):
        revision = json.loads(Path(session).read_text())["revision"]
        subprocess.run(command + ["update", *scope, "--stage", "question", "--status", status,
                                   "--expected-revision", str(revision),
                                   "--reason", "已明确预览的目标和约束" if language == "zh-CN" else "Established the preview goal and constraints"], check=True,
                       capture_output=True, text=True)
    executable = APP / "Contents/MacOS/HUDPreview"
    executable.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["xcrun", "swiftc", "-parse-as-library", "-swift-version", "5", "-warnings-as-errors",
                    "-target", f"{platform.machine()}-apple-macosx14.0",
                    "-framework", "AppKit", "-framework", "SwiftUI", "-framework", "CryptoKit",
                    *[str(ROOT / "native" / name) for name in
                      ("ProgressState.swift", "HUDPlacement.swift", "HUDLanguage.swift", "HUDPreferences.swift", "HUDView.swift", "HUDSettingsView.swift")],
                    str(ROOT / "tests/native/HUDPreview.swift"), "-o", str(executable)], check=True)
    (APP / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "org.worklikemusk.hud.designpreview",
        "CFBundleName": "Five Step Design Preview", "CFBundleExecutable": "HUDPreview",
        "CFBundlePackageType": "APPL", "NSHighResolutionCapable": True,
    }))
    subprocess.run(["open", "-n", str(APP), "--args", str(CLI), str(project), session, str(config)], check=True)

if __name__ == "__main__":
    main()
