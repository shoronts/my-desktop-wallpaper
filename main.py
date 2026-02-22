#!/usr/bin/env python3
import sys
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApp,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowCollectionBehaviorIgnoresCycle,
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

    # Allow mouse interaction
    "interactive": False,

    # Used if html_mode == "single"
    "single_html_path": "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",

    # Used if html_mode == "multi"
    # Order = left → right monitors
    "multi_html_paths": [
        "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",
        "/Users/whiteking/Applications/my-desktop-wallpaper/index.html",
    ],
}


# ======================================================
# GLOBAL STATE
# ======================================================

WINDOWS = []
WEBVIEWS = {}


# ======================================================
# WALLPAPER WINDOW
# ======================================================

def create_wallpaper_window(screen, html_path, interactive):
    frame = screen.frame()

    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        NSWindowStyleMaskBorderless,
        2,      # NSBackingStoreBuffered
        False,
    )

    # Put window at desktop level
    window.setLevel_(CGWindowLevelForKey(kCGDesktopWindowLevelKey))

    # Window behavior (SAFE COMBINATION)
    window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces |
        NSWindowCollectionBehaviorStationary |
        NSWindowCollectionBehaviorIgnoresCycle
    )

    window.setOpaque_(False)
    window.setBackgroundColor_(None)
    window.setIgnoresMouseEvents_(not interactive)

    # WebView
    config = WKWebViewConfiguration.alloc().init()
    webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)

    html_url = NSURL.fileURLWithPath_(html_path)
    base_url = NSURL.fileURLWithPath_(str(Path(html_path).parent))
    webview.loadFileURL_allowingReadAccessToURL_(html_url, base_url)

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
        for path, views in WEBVIEWS.items():
            if event.src_path == path:
                for v in views:
                    v.reload()


def start_hot_reload(html_paths):
    observer = Observer()
    handler = HTMLChangeHandler()

    folders = {str(Path(p).parent) for p in html_paths}
    for folder in folders:
        observer.schedule(handler, folder, recursive=False)

    observer.start()


# ======================================================
# MAIN APP
# ======================================================

def run():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    NSApp.activateIgnoringOtherApps_(True)

    screens = NSScreen.screens()

    if CONFIG["html_mode"] == "single":
        htmls = [CONFIG["single_html_path"]] * len(screens)
    else:
        htmls = CONFIG["multi_html_paths"][:len(screens)]

    for screen, html in zip(screens, htmls):
        window, webview = create_wallpaper_window(
            screen,
            html,
            CONFIG["interactive"],
        )
        WINDOWS.append(window)
        WEBVIEWS.setdefault(html, []).append(webview)

    start_hot_reload(list(WEBVIEWS.keys()))
    app.run()


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":
    run()