#!/usr/bin/env python3
import sys
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApplicationDidChangeScreenParametersNotification,
    NSApp,
    NSNotificationCenter,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowCollectionBehaviorIgnoresCycle,
)
from WebKit import (
    WKProcessPool,
    WKWebsiteDataStore,
    WKWebView,
    WKWebViewConfiguration,
)
from Foundation import NSTimer, NSURL
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

    # Periodic self-heal interval (seconds)
    "health_check_interval": 5.0,
}


# ======================================================
# GLOBAL STATE
# ======================================================

WINDOWS = []
SCREEN_WINDOWS = {}
WEBVIEWS = {}
SCREEN_CHANGE_OBSERVER = None
HOT_RELOAD_OBSERVER = None
HEALTH_CHECK_TIMER = None
PROCESS_POOL = WKProcessPool.alloc().init()


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
    config.setProcessPool_(PROCESS_POOL)
    config.setWebsiteDataStore_(WKWebsiteDataStore.nonPersistentDataStore())
    webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)

    html_url = NSURL.fileURLWithPath_(html_path)
    base_url = NSURL.fileURLWithPath_(str(Path(html_path).parent))
    webview.loadFileURL_allowingReadAccessToURL_(html_url, base_url)

    window.setContentView_(webview)
    window.orderFrontRegardless()

    return window, webview


def screen_id(screen):
    return int(screen.deviceDescription()["NSScreenNumber"])


def resolve_htmls_for_screens(screens):
    if CONFIG["html_mode"] == "single":
        return [CONFIG["single_html_path"]] * len(screens)

    paths = CONFIG["multi_html_paths"]
    if not paths:
        raise ValueError("CONFIG['multi_html_paths'] must not be empty in multi mode.")

    if len(paths) >= len(screens):
        return paths[:len(screens)]

    # Reuse the last path so every screen always gets a window.
    return paths + [paths[-1]] * (len(screens) - len(paths))


def rebuild_webview_index():
    WEBVIEWS.clear()
    for _, (_, webview, html_path) in SCREEN_WINDOWS.items():
        WEBVIEWS.setdefault(html_path, []).append(webview)


def destroy_window(display_id):
    item = SCREEN_WINDOWS.pop(display_id, None)
    if not item:
        return

    window, webview, _ = item
    webview.stopLoading()
    webview.removeFromSuperview()
    window.orderOut_(None)
    window.close()

    if window in WINDOWS:
        WINDOWS.remove(window)


def sync_windows_to_screens():
    screens = sorted(NSScreen.screens(), key=lambda s: s.frame().origin.x)
    htmls = resolve_htmls_for_screens(screens)

    active_ids = {screen_id(s) for s in screens}
    stale_ids = [display_id for display_id in SCREEN_WINDOWS if display_id not in active_ids]
    for display_id in stale_ids:
        destroy_window(display_id)

    for screen, html in zip(screens, htmls):
        display_id = screen_id(screen)
        frame = screen.frame()
        existing = SCREEN_WINDOWS.get(display_id)

        if existing:
            window, webview, current_html = existing
            window.setFrame_display_(frame, True)
            webview.setFrame_(frame)

            if current_html != html:
                html_url = NSURL.fileURLWithPath_(html)
                base_url = NSURL.fileURLWithPath_(str(Path(html).parent))
                webview.loadFileURL_allowingReadAccessToURL_(html_url, base_url)
                SCREEN_WINDOWS[display_id] = (window, webview, html)
        else:
            window, webview = create_wallpaper_window(
                screen,
                html,
                CONFIG["interactive"],
            )
            WINDOWS.append(window)
            SCREEN_WINDOWS[display_id] = (window, webview, html)

    rebuild_webview_index()


def health_check_tick(_timer):
    try:
        sync_windows_to_screens()
        for _, (window, _webview, _html) in SCREEN_WINDOWS.items():
            if not window.isVisible():
                window.orderFrontRegardless()
    except Exception:
        # Keep app alive; next tick can self-heal after transient failures.
        pass


def start_health_check():
    global HEALTH_CHECK_TIMER
    interval = float(CONFIG.get("health_check_interval", 5.0))
    if interval <= 0:
        interval = 5.0

    HEALTH_CHECK_TIMER = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
        interval,
        True,
        lambda timer: health_check_tick(timer),
    )


def start_screen_change_monitor():
    global SCREEN_CHANGE_OBSERVER
    center = NSNotificationCenter.defaultCenter()

    def on_screens_changed(_notification):
        sync_windows_to_screens()

    SCREEN_CHANGE_OBSERVER = center.addObserverForName_object_queue_usingBlock_(
        NSApplicationDidChangeScreenParametersNotification,
        None,
        None,
        on_screens_changed,
    )


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
    global HOT_RELOAD_OBSERVER
    observer = Observer()
    handler = HTMLChangeHandler()

    folders = {str(Path(p).parent) for p in html_paths}
    for folder in folders:
        observer.schedule(handler, folder, recursive=False)

    observer.start()
    HOT_RELOAD_OBSERVER = observer


# ======================================================
# MAIN APP
# ======================================================

def run():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    NSApp.activateIgnoringOtherApps_(True)
    sync_windows_to_screens()
    start_screen_change_monitor()
    start_health_check()
    start_hot_reload(list(set(resolve_htmls_for_screens(NSScreen.screens()))))
    app.run()


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":
    run()
