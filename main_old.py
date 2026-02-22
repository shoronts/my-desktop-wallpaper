#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApp,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskBorderless,
)
from WebKit import WKWebView, WKWebViewConfiguration
from Foundation import NSURL
from Quartz import CGWindowLevelForKey, kCGDesktopWindowLevelKey

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# ======================================================
# CONFIG
# ======================================================

CONFIG = {
    # "single" or "multi"
    "html_mode": "multi",

    # Allow mouse interaction?
    "interactive": False,

    # Used if html_mode == "single"
    "single_html_path": "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",

    # Used if html_mode == "multi"
    # One HTML per monitor (order = left → right)
    "multi_html_paths": [
        "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",
        "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",
    ],
}


# ======================================================
# LAUNCHD SELF-INSTALL
# ======================================================

LABEL = "com.whiteking.htmlwallpaper"
PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
SCRIPT_PATH = Path(__file__).resolve()


def running_under_launchd():
    return os.environ.get("LAUNCHD_JOB") == "1"


def create_plist():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>python3</string>
        <string>{SCRIPT_PATH}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>ProcessType</key>
    <string>Interactive</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>LAUNCHD_JOB</key>
        <string>1</string>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/htmlwallpaper.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/htmlwallpaper.error.log</string>
</dict>
</plist>
"""


def install_and_launch():
    print("🛠 Installing HTML wallpaper service...")

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(create_plist())
    os.chmod(PLIST_PATH, 0o644)
    os.chmod(SCRIPT_PATH, 0o755)

    # Remove quarantine (important)
    subprocess.run(
        ["xattr", "-dr", "com.apple.quarantine", str(SCRIPT_PATH.parent)],
        stderr=subprocess.DEVNULL,
    )

    uid = os.getuid()

    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)],
        stderr=subprocess.DEVNULL,
    )

    subprocess.check_call(
        ["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)]
    )
    subprocess.check_call(
        ["launchctl", "enable", f"gui/{uid}/{LABEL}"]
    )
    subprocess.check_call(
        ["launchctl", "kickstart", f"gui/{uid}/{LABEL}"]
    )

    print("✅ Installed and running.")
    print("ℹ️ You can close Terminal safely.")
    sys.exit(0)


# ======================================================
# WALLPAPER WINDOW
# ======================================================

WINDOWS = {}
WEBVIEWS = {}


def create_wallpaper_window(screen, html_path, interactive):
    from os.path import dirname

    frame = screen.frame()

    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        NSWindowStyleMaskBorderless,
        2,
        False,
    )

    # Desktop level window
    window.setLevel_(CGWindowLevelForKey(kCGDesktopWindowLevelKey))
    window.setOpaque_(False)
    window.setBackgroundColor_(None)

    # All Spaces + Desktop
    window.setCollectionBehavior_(
        (1 << 0) | (1 << 1) | (1 << 3) | (1 << 6)
    )

    window.setIgnoresMouseEvents_(not interactive)

    config = WKWebViewConfiguration.alloc().init()
    webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)

    url = NSURL.fileURLWithPath_(html_path)
    directory_url = NSURL.fileURLWithPath_(dirname(html_path))

    webview.loadFileURL_allowingReadAccessToURL_(url, directory_url)

    window.setContentView_(webview)
    window.orderFrontRegardless()

    return window, webview


# ======================================================
# HOT RELOAD
# ======================================================

class HTMLChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.src_path.endswith(".html"):
            return
        for path, webviews in WEBVIEWS.items():
            if event.src_path == path:
                for w in webviews:
                    w.reload()


def start_hot_reload(paths):
    observer = Observer()
    handler = HTMLChangeHandler()

    for d in set(Path(p).parent for p in paths):
        observer.schedule(handler, str(d), recursive=False)

    observer.start()


# ======================================================
# MAIN RUNTIME
# ======================================================

def run_wallpaper():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    NSApp.activateIgnoringOtherApps_(True)

    screens = NSScreen.screens()

    if CONFIG["html_mode"] == "single":
        htmls = [CONFIG["single_html_path"]] * len(screens)
    else:
        htmls = CONFIG["multi_html_paths"]

    for screen, html in zip(screens, htmls):
        window, webview = create_wallpaper_window(
            screen, html, CONFIG["interactive"]
        )
        WINDOWS.setdefault(screen.localizedName(), []).append(window)
        WEBVIEWS.setdefault(html, []).append(webview)

    start_hot_reload(list(WEBVIEWS.keys()))
    app.run()


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":
    if not running_under_launchd():
        install_and_launch()
    else:
        run_wallpaper()