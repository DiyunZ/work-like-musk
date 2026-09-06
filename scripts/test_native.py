#!/usr/bin/env python3
"""Run native state, placement, appearance, and interaction regression suites."""
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "ProgressStateTests": ["ProgressState.swift"],
    "HUDPlacementTests": ["HUDPlacement.swift"],
    "HUDPreferencesTests": ["HUDLanguage.swift", "HUDPreferences.swift"],
    "HUDLanguageTests": ["HUDLanguage.swift", "HUDPreferences.swift"],
    "HUDSessionTests": ["ProgressState.swift", "HUDSessions.swift"],
    "TitleAnchorTests": ["TitleAnchor.swift", "HUDPlacement.swift"],
    "StageReadinessTests": ["ProgressState.swift"],
    "HUDInteractionTests": ["ProgressState.swift", "HUDPlacement.swift", "HUDLanguage.swift", "HUDPreferences.swift", "HUDView.swift"],
}

def main():
    destination = ROOT / ".build" / "native-tests"
    destination.mkdir(parents=True, exist_ok=True)
    for name, sources in SUITES.items():
        executable = destination / name
        subprocess.run([
            "xcrun", "swiftc", "-parse-as-library", "-swift-version", "5",
            "-warnings-as-errors", "-target", f"{platform.machine()}-apple-macosx14.0",
            "-framework", "AppKit", "-framework", "SwiftUI", "-framework", "CryptoKit",
            "-lsqlite3",
            *[str(ROOT / "native" / source) for source in sources],
            str(ROOT / "tests" / "native" / f"{name}.swift"), "-o", str(executable),
        ], check=True)
        subprocess.run([str(executable)], check=True)

if __name__ == "__main__":
    main()
