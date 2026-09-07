#!/usr/bin/env python3
"""Build and ad-hoc sign the standalone Five Step HUD application."""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "FiveStepHUD.app"
DESTINATION = ROOT / "dist" / APP_NAME


def main() -> None:
    temporary = ROOT / "dist" / f".{APP_NAME}.build-{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)

    executable = temporary / "Contents" / "MacOS" / "FiveStepHUD"
    executable.parent.mkdir(parents=True)
    source_files = [
        str(ROOT / "native" / "HUDLanguage.swift"),
        str(ROOT / "native" / "ProgressState.swift"),
        str(ROOT / "native" / "HUDSessions.swift"),
        str(ROOT / "native" / "HUDPlacement.swift"),
        str(ROOT / "native" / "TitleAnchor.swift"),
        str(ROOT / "native" / "HUDPreferences.swift"),
        str(ROOT / "native" / "HUDSettingsView.swift"),
        str(ROOT / "native" / "HUDView.swift"),
        str(ROOT / "native" / "App.swift"),
    ]

    try:
        subprocess.run(
            [
                "xcrun",
                "swiftc",
                "-parse-as-library",
                "-swift-version",
                "5",
                "-O",
                "-warnings-as-errors",
                "-target",
                f"{platform.machine()}-apple-macosx14.0",
                "-framework",
                "AppKit",
                "-framework",
                "SwiftUI",
                "-framework",
                "CryptoKit",
                "-framework",
                "CoreGraphics",
                "-lsqlite3",
                *source_files,
                "-o",
                str(executable),
            ],
            check=True,
        )

        info = {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": "Work Like Musk HUD",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeExtensions": ["json"],
                    "CFBundleTypeName": "Five Step Session",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["public.json"],
                }
            ],
            "CFBundleExecutable": "FiveStepHUD",
            "CFBundleIdentifier": "org.worklikemusk.hud",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": "FiveStepHUD",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "0.3.0",
            "CFBundleVersion": "1",
            "LSMinimumSystemVersion": "14.0",
            "LSSupportsOpeningDocumentsInPlace": True,
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
        }
        info_path = temporary / "Contents" / "Info.plist"
        with info_path.open("wb") as output:
            plistlib.dump(info, output, sort_keys=True)

        executable.chmod(0o755)
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(temporary)],
            check=True,
        )

        if DESTINATION.exists():
            shutil.rmtree(DESTINATION)
        temporary.replace(DESTINATION)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    print(DESTINATION)


if __name__ == "__main__":
    main()
