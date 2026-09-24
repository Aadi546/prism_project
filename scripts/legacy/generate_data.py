#!/usr/bin/env python3
"""Synthesize deeplink catalog, SIIS articles, queries, and gold samples."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SAMPLES = DATA / "samples"


def dl(
    slug: str,
    description: str,
    message: str,
    qna: str,
    domain: str,
    depth: int,
    parent: str | None = None,
    original: str | None = None,
) -> dict:
    return {
        "deeplink": f"bixby://masked/act/{slug}",
        "description": description,
        "message": message,
        "qna_description": qna,
        "domain": domain,
        "depth": depth,
        "parent": parent,
        "originalType": original or "Settings",
        "classes": {"screen": slug, "domain": domain},
    }


DEEPLINKS = [
    # Battery
    dl("battery", "Open Battery settings", "View battery level and power options", "battery parent menu", "battery", 1),
    dl("battery_usage", "Open battery usage by app", "See which apps drain the battery", "app battery consumption list", "battery", 2, "battery"),
    dl("adaptive_battery", "Open Adaptive battery", "Limit battery for unused apps", "adaptive battery unused apps", "battery", 2, "battery"),
    dl("power_saving", "Open Power saving mode", "Turn on power saving", "power saving battery saver", "battery", 2, "battery"),
    dl("battery_protection", "Open battery protection", "Limit charge to protect battery health", "protect battery max 80 95 charging", "battery", 2, "battery"),
    dl("charging_settings", "Open charging settings", "Choose fast charging options", "fast charging wireless charging toggle", "battery", 2, "battery"),
    dl("fast_charging", "Open fast charging", "Enable or disable fast charging", "super fast charging cable", "battery", 3, "charging_settings"),
    dl("wireless_charging", "Open wireless charging", "Enable wireless charging", "wireless charger pad", "battery", 3, "charging_settings"),
    dl("show_battery_percentage", "Show battery percentage", "Display remaining battery percent in status bar", "battery percent icon", "battery", 2, "battery"),
    dl("background_usage_limits", "Open background usage limits", "Put unused apps to sleep", "sleeping apps deep sleeping background", "battery", 2, "battery"),
    dl("put_apps_to_sleep", "Put unused apps to sleep", "Sleep apps that drain battery in background", "put apps to sleep", "battery", 3, "background_usage_limits"),
    dl("deep_sleeping_apps", "Open deep sleeping apps", "Deep sleep apps that should never run", "deep sleeping apps list", "battery", 3, "background_usage_limits"),
    dl("app_power_management", "Open app power management", "Control per-app battery usage", "never sleeping apps battery", "battery", 2, "battery"),
    dl("wireless_power_share", "Open Wireless power share", "Share battery with another device", "battery share reverse wireless", "battery", 2, "battery"),
    dl("battery_information", "Open battery information", "See battery health and cycle count", "battery capacity health", "battery", 2, "battery"),
    dl("sleep_standby_optimization", "Open sleep standby optimization", "Save battery overnight", "sleep charging optimization", "battery", 2, "battery"),
    dl("extra_dim_battery", "Open extra dim related power tips", "Lower brightness to save battery", "dim screen save power", "battery", 2, "battery"),
    dl("adaptive_refresh_battery", "Open motion smoothness for battery", "Use standard refresh to save power", "120hz battery drain refresh rate", "battery", 2, "battery"),
    dl("charging_notification", "Open charging notification settings", "Show charging speed alerts", "charging notification", "battery", 3, "charging_settings"),
    dl("protect_battery_basic", "Open basic battery protection", "Stop charging at 100 percent after rest", "basic protection charging pause", "battery", 3, "battery_protection"),
    dl("protect_battery_maximum", "Open maximum battery protection", "Cap charge around eighty percent", "maximum protection 80 percent", "battery", 3, "battery_protection"),
    dl("battery_graph", "Open battery usage graph", "Review drain over the last days", "battery graph history", "battery", 3, "battery_usage"),
    dl("optimize_battery_usage", "Optimize battery usage for an app", "Allow or restrict background activity", "optimize battery usage permission", "battery", 3, "app_power_management"),
    # Display
    dl("display", "Open Display settings", "Change brightness theme and screen options", "display parent menu", "display", 1),
    dl("brightness", "Open brightness settings", "Set screen brightness level", "brightness slider too dark too bright", "display", 2, "display"),
    dl("adaptive_brightness", "Open adaptive brightness", "Let the phone auto adjust brightness", "auto brightness adaptive", "display", 3, "brightness"),
    dl("dark_mode", "Open Dark mode", "Switch between light and dark theme", "dark mode night theme", "display", 2, "display"),
    dl("motion_smoothness", "Open motion smoothness", "Choose standard or adaptive refresh rate", "120hz 60hz motion smoothness", "display", 2, "display"),
    dl("screen_timeout", "Open screen timeout", "Set when the screen turns off", "screen timeout sleep", "display", 2, "display"),
    dl("font_size_and_style", "Open font size and style", "Change text size and font", "font size too small large", "display", 2, "display"),
    dl("screen_zoom", "Open screen zoom", "Make items larger or smaller", "screen zoom density", "display", 2, "display"),
    dl("navigation_bar", "Open navigation bar settings under Display", "Choose navigation type", "buttons or swipe gestures navigation bar", "display", 2, "display"),
    dl("swipe_gestures", "Open swipe gesture navigation", "Use swipe gestures instead of buttons", "full screen gestures swipe from bottom", "display", 3, "navigation_bar"),
    dl("button_navigation", "Open button navigation", "Use three buttons instead of swipes", "navigation buttons recents home back", "display", 3, "navigation_bar"),
    dl("gesture_hint", "Open gesture hint", "Show guidance lines at the bottom of the screen", "gesture hint bar lines", "display", 3, "navigation_bar"),
    dl("button_order", "Open button order", "Swap recents and back button positions", "button order left right", "display", 3, "navigation_bar"),
    dl("screen_mode", "Open screen mode", "Choose vivid or natural colors", "vivid natural screen mode", "display", 2, "display"),
    dl("eye_comfort_shield", "Open Eye comfort shield", "Reduce blue light at night", "blue light filter night comfort", "display", 2, "display"),
    dl("always_on_display", "Open Always On Display", "Show clock on a sleeping screen", "aod always on display", "display", 2, "display"),
    dl("screen_resolution", "Open screen resolution", "Choose FHD or QHD resolution", "wqhd fhd resolution battery", "display", 2, "display"),
    dl("accidental_touch_protection", "Open accidental touch protection", "Block touches when in a dark pocket", "pocket touch accidental", "display", 2, "display"),
    dl("touch_sensitivity", "Open touch sensitivity", "Improve touches with a screen protector", "touch sensitivity protector", "display", 2, "display"),
    dl("one_handed_mode", "Open one handed mode", "Shrink the screen for one hand use", "one handed mode", "display", 2, "display"),
    dl("edge_panels", "Open Edge panels", "Handle apps from the screen edge", "edge panel handle", "display", 2, "display"),
    dl("extra_dim", "Open Extra dim", "Make the screen dimmer than the slider allows", "extra dim flickering night", "display", 2, "display"),
    dl("screen_protection", "Open screen protector related display options", "Reduce flicker with a protector on", "screen flicker pwm", "display", 2, "display"),
    dl("screensaver", "Open screensaver", "Show a screensaver while charging", "screensaver dock", "display", 2, "display"),
    dl("lift_to_wake", "Open lift to wake", "Turn the screen on when you pick up the phone", "lift to wake", "display", 2, "display"),
    dl("double_tap_to_wake", "Open double tap to wake or sleep", "Tap the screen to wake it", "double tap wake", "display", 2, "display"),
    dl("navigation_sensitivity", "Open gesture sensitivity", "Adjust how far from the edge a swipe starts", "back gesture sensitivity", "display", 3, "swipe_gestures"),
    # Camera
    dl("camera", "Open Camera app settings", "Change how the camera captures photos", "camera parent menu", "camera", 1),
    dl("camera_settings", "Open Camera settings", "Configure photo and video options", "camera settings gear", "camera", 2, "camera"),
    dl("scene_optimizer", "Open scene optimizer", "Automatically enhance scenes", "scene optimizer food sky", "camera", 3, "camera_settings"),
    dl("auto_hdr", "Open auto HDR", "Capture more detail in bright and dark areas", "hdr auto hdr photos", "camera", 3, "camera_settings"),
    dl("grid_lines", "Open grid lines", "Show composition grid in viewfinder", "camera grid rule of thirds", "camera", 3, "camera_settings"),
    dl("location_tags", "Open location tags", "Save location with photos", "geotag location camera", "camera", 3, "camera_settings"),
    dl("video_stabilization", "Open video stabilization", "Reduce shake in videos", "super steady stabilization", "camera", 3, "camera_settings"),
    dl("advanced_recording", "Open advanced recording options", "Change video resolution and fps", "4k 60fps high efficiency video", "camera", 3, "camera_settings"),
    dl("pro_mode", "Open Pro mode help", "Manually set ISO shutter and focus", "pro camera manual focus", "camera", 3, "camera_settings"),
    dl("focus_and_tracking", "Open auto focus tracking", "Track a subject while it moves", "autofocus tracking blur", "camera", 3, "camera_settings"),
    dl("shot_suggestions", "Open shot suggestions", "Get composition guides while shooting", "shot suggestions composition", "camera", 3, "camera_settings"),
    dl("selfie_color_tone", "Open selfie color tone", "Warm or cool selfie processing", "selfie tone yellowish", "camera", 3, "camera_settings"),
    dl("wide_angle", "Open wide lens correction", "Correct distortion on ultra wide shots", "ultra wide distortion", "camera", 3, "camera_settings"),
    dl("scan_documents_qr", "Open scan QR codes and documents", "Detect QR codes automatically", "scan qr document", "camera", 3, "camera_settings"),
    dl("save_options", "Open save options", "Choose HEIF JPEG and copy destination", "heif heic jpeg save", "camera", 3, "camera_settings"),
    dl("shutter_sound", "Open shutter sound", "Mute or keep the shutter click", "camera shutter sound mute", "camera", 3, "camera_settings"),
    dl("watermark", "Open watermarks", "Stamp date or brand on photos", "camera watermark", "camera", 3, "camera_settings"),
    dl("picture_formats", "Open picture formats", "Switch between JPEG and high efficiency", "picture format heif", "camera", 3, "save_options"),
    dl("auto_lens_switching", "Open auto lens switching", "Stop the camera jumping between lenses", "lens switching zoom jump", "camera", 3, "camera_settings"),
    dl("hold_camera_button", "Open hold camera button to", "Choose what a long shutter press does", "hold shutter video", "camera", 3, "camera_settings"),
    dl("intelligent_optimization", "Open intelligent optimization", "Reduce overprocessed look in photos", "oversharpened processed camera", "camera", 3, "scene_optimizer"),
    dl("front_video_size", "Open front camera video size", "Change selfie video resolution", "front camera video quality", "camera", 3, "advanced_recording"),
    dl("restore_camera_defaults", "Reset camera settings", "Restore default camera options", "reset camera settings", "camera", 3, "camera_settings"),
    # Performance / Device care
    dl("device_care", "Open Device care", "Clean battery storage and memory", "device care parent menu", "performance", 1),
    dl("memory", "Open memory care", "Free RAM used by background apps", "ram memory cleaning", "performance", 2, "device_care"),
    dl("storage", "Open storage", "Free space used by files and apps", "storage full clean now", "performance", 2, "device_care"),
    dl("ram_plus", "Open RAM Plus", "Use storage as extra virtual memory", "ram plus virtual memory lag", "performance", 3, "memory"),
    dl("auto_optimization", "Open auto optimization", "Restart and optimize on a schedule", "auto optimize restart schedule", "performance", 2, "device_care"),
    dl("software_update", "Open software update", "Check for system updates", "software update after update slow", "performance", 2, "device_care"),
    dl("app_optimization", "Open app optimization in device care", "Close heavy apps that slow the phone", "optimize apps performance", "performance", 2, "device_care"),
    dl("processing_speed", "Open processing speed", "Prefer optimized or high performance", "processing speed high performance", "performance", 2, "device_care"),
    dl("thermal_control", "Open thermal related game and performance options", "Reduce heat throttling during games", "phone hot thermal throttle", "performance", 2, "device_care"),
    dl("game_booster", "Open Game Booster", "Limit background activity while gaming", "game booster lag fps", "performance", 2, "device_care"),
    dl("developer_options", "Open developer options", "Change animation scales and drawing", "developer options animation scale", "performance", 2, "performance"),
    dl("window_animation_scale", "Open window animation scale", "Speed up or disable window animations", "animation scale 0.5", "performance", 3, "developer_options"),
    dl("transition_animation_scale", "Open transition animation scale", "Speed up screen transitions", "transition animation", "performance", 3, "developer_options"),
    dl("animator_duration_scale", "Open animator duration scale", "Speed up in-app animations", "animator duration", "performance", 3, "developer_options"),
    dl("safe_mode_info", "Open recovery and safe mode guidance", "Boot with third party apps disabled", "safe mode boot", "performance", 2, "device_care"),
    dl("reset_settings", "Open reset settings", "Reset app preferences without erasing data", "reset settings preferences", "performance", 2, "device_care"),
    dl("factory_reset", "Open factory data reset", "Erase all data and restore factory software", "factory reset erase", "performance", 3, "reset_settings"),
    dl("cache_partition", "Open storage cache cleaning", "Clear cached files that pile up after updates", "clear cache partition", "performance", 3, "storage"),
    dl("background_check", "Open unused app permissions", "Stop unused apps waking the device", "unused apps pause", "performance", 2, "device_care"),
    dl("adaptive_refresh_performance", "Open motion smoothness for performance", "Raise refresh rate for smoother scrolling", "stutter scroll refresh", "performance", 2, "display"),
    dl("home_screen_light", "Open Home screen settings", "Reduce heavy live wallpapers", "live wallpaper lag", "performance", 2, "performance"),
    dl("digital_wellbeing", "Open Digital Wellbeing", "Limit distracting apps that keep waking the phone", "digital wellbeing focus", "performance", 2, "performance"),
    dl("notifications_asleep", "Open notifications that wake the device", "Reduce wakeups from noisy apps", "notification wake drain", "performance", 2, "performance"),
    dl("airplane_mode", "Open Airplane mode", "Cut radios when the phone is overheating on standby", "airplane mode radios", "performance", 2, "performance"),
]

assert len({d["deeplink"] for d in DEEPLINKS}) == len(DEEPLINKS)
assert "bixby://dummy_positive" not in {d["deeplink"] for d in DEEPLINKS}


def article(
    aid: str,
    domain: str,
    title: str,
    hints: list[str],
    body: str,
    topic: str,
    kind: str,
    plan_title: str,
    actions: list[dict],
) -> dict:
    return {
        "id": aid,
        "domain": domain,
        "title": title,
        "query_hints": hints,
        "body": body,
        "plan": {
            "topic": topic,
            "kind": kind,
            "title": plan_title,
            "actions": actions,
        },
    }


def action(name, desc, category, screen, steps, extra_steps=None):
    groups = [{"screen_key": screen, "steps": steps}]
    if extra_steps:
        groups.append({"screen_key": extra_steps[0], "steps": extra_steps[1]})
    return {
        "actionName": name,
        "description": desc,
        "category": category,
        "stepGroups": groups,
    }


ARTICLES = [
    article(
        "siis_swipe_axis",
        "display",
        "Swipe navigation moves vertically instead of horizontally",
        [
            "phone swipe gestures wrong direction after app install",
            "swipe navigation scrolls up and down instead of left right",
            "navigation swipes on samsung respond in the wrong axis",
        ],
        """Customers report that after installing an app, swipe navigation moves the screen up and down instead of switching apps left and right.

Do not visit samsung.com/support or any web page. Use on-device Settings.

1. Open Settings.
2. Tap Display.
3. Tap Navigation bar.
4. Select Buttons or Swipe gestures.
5. If using swipe gestures, turn on Gesture hint so the guidance line appears at the bottom.
6. Adjust gesture sensitivity if back gestures feel inverted.

If a recently installed app overlays the navigation area, boot to Safe mode and uninstall it. Restart only after trying settings. Factory reset is last resort.
""",
        "Swipe Navigation",
        "Troubleshooting",
        "Swipe navigation settings",
        [
            action(
                "Configure Navigation Bar Settings",
                "It will let you choose navigation type",
                "auto",
                "navigation_bar",
                [
                    "Navigate to and open Settings.",
                    "Tap on Display.",
                    "Tap on Navigation bar.",
                    "Select your preferred navigation type between Buttons and Swipe gestures.",
                    "Optionally toggle on Gesture hint to display guidance lines at the bottom of the screen.",
                ],
            ),
            action(
                "Adjust Gesture Sensitivity",
                "It will tune edge swipe distance",
                "auto",
                "navigation_sensitivity",
                [
                    "Stay in Navigation bar settings.",
                    "Tap More options or Swipe gestures.",
                    "Drag sensitivity until back gestures feel natural.",
                ],
            ),
            action(
                "Check Conflicting App Overlay",
                "It will find apps covering navigation",
                "manual",
                "app_optimization",
                [
                    "Note any app installed just before the issue started.",
                    "Disable that app or turn off its display overlay permission.",
                    "Test swipe navigation again on the home screen.",
                ],
            ),
            action(
                "Restart In Safe Mode",
                "It will isolate third party interference",
                "critical",
                "safe_mode_info",
                [
                    "Press and hold the power key.",
                    "Touch and hold Power off until Safe mode appears.",
                    "Tap Safe mode and test navigation.",
                    "Uninstall the conflicting app if swipes work in Safe mode.",
                ],
            ),
        ],
    ),
    article(
        "siis_battery_fast_drain",
        "battery",
        "Battery drains quickly during the day",
        [
            "battery dies fast",
            "my battery drains overnight",
            "phone battery percentage drops too quickly",
        ],
        """Battery drain is usually background apps, high refresh rate, or adaptive battery being off.

1. Open Settings then Battery and device care then Battery.
2. Open Battery usage and identify the top draining app.
3. Put unused apps to sleep or deep sleep.
4. Turn on Adaptive battery.
5. Switch motion smoothness to Standard to save power.
6. Enable battery protection if the device stays on a charger.

Restart the phone if usage looks normal but drain continues. Do not factory reset first.
""",
        "Battery Drain",
        "Troubleshooting",
        "Battery drain settings",
        [
            action(
                "Review Battery Usage",
                "It will show apps wasting power",
                "auto",
                "battery_usage",
                [
                    "Navigate to and open Settings.",
                    "Tap Battery and device care.",
                    "Tap Battery then Battery usage.",
                    "Note apps using unusual power since last full charge.",
                ],
            ),
            action(
                "Sleep Unused Apps",
                "It will stop background battery drain",
                "auto",
                "put_apps_to_sleep",
                [
                    "Open Background usage limits.",
                    "Turn on Put unused apps to sleep.",
                    "Add the draining app to Deep sleeping apps if it should never run.",
                ],
            ),
            action(
                "Enable Adaptive Battery",
                "It will limit power for idle apps",
                "auto",
                "adaptive_battery",
                [
                    "Open Battery settings.",
                    "Turn on Adaptive battery.",
                    "Keep the phone unplugged for a few cycles so it can learn usage.",
                ],
            ),
            action(
                "Lower Motion Smoothness",
                "It will cut refresh related drain",
                "manual",
                "motion_smoothness",
                [
                    "Open Display settings.",
                    "Tap Motion smoothness.",
                    "Select Standard instead of Adaptive.",
                ],
            ),
            action(
                "Restart The Phone",
                "It will clear a runaway process",
                "critical",
                "auto_optimization",
                [
                    "Press and hold the side key.",
                    "Tap Restart.",
                    "Watch battery usage for one hour after reboot.",
                ],
            ),
        ],
    ),
    article(
        "siis_screen_flicker",
        "display",
        "Screen flickers at low brightness",
        [
            "screen flickers and the battery dies fast",
            "display flickering at night",
            "galaxy screen flashes on dim",
        ],
        """Flicker at low brightness is often Extra dim, adaptive brightness hunting, or a screen protector increasing touch sensitivity.

1. Open Settings Display.
2. Turn Extra dim off and raise brightness.
3. Toggle Adaptive brightness off then on.
4. Disable Eye comfort shield to test.
5. If a protector is installed, raise Touch sensitivity.

Avoid factory reset for flicker. Visit a service center only if the panel still flashes at max brightness — that step is manual and has no deeplink.
""",
        "Screen Flicker",
        "Troubleshooting",
        "Display flicker settings",
        [
            action(
                "Disable Extra Dim",
                "It will stop aggressive dimming flicker",
                "auto",
                "extra_dim",
                [
                    "Navigate to and open Settings.",
                    "Tap Display.",
                    "Turn Extra dim off.",
                    "Raise brightness above the lowest two steps.",
                ],
            ),
            action(
                "Reset Adaptive Brightness",
                "It will stop brightness hunting",
                "auto",
                "adaptive_brightness",
                [
                    "Open Brightness settings.",
                    "Turn Adaptive brightness off.",
                    "Set a stable brightness then turn Adaptive brightness on again.",
                ],
            ),
            action(
                "Test Eye Comfort Shield",
                "It will rule out blue light scheduling",
                "auto",
                "eye_comfort_shield",
                [
                    "Open Eye comfort shield.",
                    "Turn it off and watch the panel for flicker.",
                    "If flicker stops, use a later schedule instead of Adaptive.",
                ],
            ),
            action(
                "Raise Touch Sensitivity",
                "It will compensate for a screen protector",
                "manual",
                "touch_sensitivity",
                [
                    "Open Display settings.",
                    "Turn Touch sensitivity on if a protector is installed.",
                ],
            ),
        ],
    ),
    article(
        "siis_camera_blur",
        "camera",
        "Photos look blurry or overprocessed after an app install",
        [
            "camera got blurry after update",
            "galaxy photos look smeared",
            "autofocus hunting and soft pictures",
        ],
        """Soft photos are usually dirty glass, scene optimizer overprocessing, or auto lens switching.

1. Wipe the lenses.
2. Open Camera Settings.
3. Turn Scene optimizer off to test.
4. Turn Intelligent optimization to Minimum.
5. Disable Auto HDR and Auto lens switching.
6. Reset camera settings if a third party camera overlay changed defaults.

Do not factory reset for blur. Manual cleaning of the lens is required and has no Settings deeplink.
""",
        "Camera Focus",
        "Troubleshooting",
        "Camera focus settings",
        [
            action(
                "Reduce Scene Optimizer",
                "It will stop overprocessed soft photos",
                "auto",
                "scene_optimizer",
                [
                    "Open the Camera app.",
                    "Tap the settings gear.",
                    "Turn Scene optimizer off and capture a test photo.",
                ],
            ),
            action(
                "Lower Intelligent Optimization",
                "It will keep more natural detail",
                "auto",
                "intelligent_optimization",
                [
                    "Stay in Camera settings.",
                    "Open Intelligent optimization.",
                    "Select Minimum and retake the same scene.",
                ],
            ),
            action(
                "Disable Auto Lens Switching",
                "It will prevent jump focus blur",
                "auto",
                "auto_lens_switching",
                [
                    "Open Camera settings.",
                    "Turn Auto lens switching off.",
                    "Pinch zoom slowly and confirm the lens stays put.",
                ],
            ),
            action(
                "Reset Camera Settings",
                "It will undo overlay changed defaults",
                "manual",
                "restore_camera_defaults",
                [
                    "Open Camera settings.",
                    "Tap Reset settings.",
                    "Confirm and test autofocus on a high contrast object.",
                ],
            ),
            action(
                "Clean The Lenses",
                "It will remove smudges causing haze",
                "manual",
                None,
                [
                    "Wipe the rear lenses with a clean microfiber cloth.",
                    "Avoid paper towels that scratch coatings.",
                    "Retake the same photo in the same light.",
                ],
            ),
        ],
    ),
    article(
        "siis_slow_after_update",
        "performance",
        "Phone got slow after a software update",
        [
            "my phone got slow after the update",
            "galaxy laggy after one ui update",
            "stuttering scrolling after software update",
        ],
        """Updates trigger indexing, cache growth, and animation defaults. Device care plus animation scales usually recover smoothness.

1. Open Device care and run Optimization.
2. Clear cached data in Storage.
3. Set RAM Plus to 2 GB or off if storage is slow.
4. In developer options, set animation scales to 0.5x.
5. Schedule Auto optimization overnight.
6. Restart. Factory reset only if the device remains unusable after two days of indexing.
""",
        "System Performance",
        "Troubleshooting",
        "Performance after update",
        [
            action(
                "Run Device Care Optimize",
                "It will free memory and cached files",
                "auto",
                "device_care",
                [
                    "Navigate to and open Settings.",
                    "Tap Battery and device care.",
                    "Tap Optimize now and wait for the scan to finish.",
                ],
            ),
            action(
                "Clear Cached Files",
                "It will drop leftover update caches",
                "auto",
                "cache_partition",
                [
                    "Open Storage in Device care.",
                    "Tap Clean now on cached files.",
                    "Remove large junk files if storage is under ten percent free.",
                ],
            ),
            action(
                "Tune Ram Plus",
                "It will stop slow virtual memory",
                "auto",
                "ram_plus",
                [
                    "Open Memory in Device care.",
                    "Tap RAM Plus.",
                    "Choose 2 GB or Off if the phone stutters while swapping.",
                ],
            ),
            action(
                "Reduce Animation Scales",
                "It will make transitions feel faster",
                "manual",
                "window_animation_scale",
                [
                    "Enable developer options by tapping Build number seven times.",
                    "Set Window, Transition, and Animator scales to 0.5x.",
                ],
            ),
            action(
                "Restart After Indexing",
                "It will finish leftover update work",
                "critical",
                "auto_optimization",
                [
                    "Leave the device plugged in on Wi-Fi for one hour.",
                    "Restart from the power menu.",
                    "If it is still unusable after two days, consider a factory reset as last resort.",
                ],
            ),
        ],
    ),
    article(
        "siis_overheat_charge",
        "battery",
        "Phone gets hot while charging overnight",
        [
            "phone overheats while charging",
            "battery hot on wireless charger",
            "charging very slow and warm",
        ],
        """Heat during charge is often fast wireless charging plus a case.

1. Open Charging settings and turn off Fast wireless charging.
2. Enable Maximum battery protection.
3. Turn Sleep standby optimization on.
4. Remove the case while charging.
""",
        "Charging Heat",
        "Troubleshooting",
        "Charging heat settings",
        [
            action(
                "Disable Fast Wireless Charging",
                "It will lower overnight charge heat",
                "auto",
                "wireless_charging",
                [
                    "Open Settings Battery Charging settings.",
                    "Turn Fast wireless charging off.",
                    "Use a slower pad overnight.",
                ],
            ),
            action(
                "Enable Maximum Protection",
                "It will cap overnight charge level",
                "auto",
                "protect_battery_maximum",
                [
                    "Open Battery protection.",
                    "Select Maximum to keep the charge near eighty percent.",
                ],
            ),
            action(
                "Turn On Sleep Optimization",
                "It will delay full charge until morning",
                "auto",
                "sleep_standby_optimization",
                [
                    "Open Battery settings.",
                    "Turn Sleep standby optimization on.",
                ],
            ),
        ],
    ),
    article(
        "siis_dark_mode_apps",
        "display",
        "Some apps stay blinding white at night",
        [
            "dark mode not applying to apps",
            "night theme missing in chrome",
            "want dark mode everywhere",
        ],
        """Dark mode is under Display. Third party apps may ignore it unless forced.

1. Settings Display Dark mode.
2. Turn Dark mode on and set a schedule.
3. For apps that stay white, use their in-app theme.
""",
        "Dark Mode",
        "Configuration",
        "Dark mode settings",
        [
            action(
                "Schedule Dark Mode",
                "It will dim the system theme at night",
                "auto",
                "dark_mode",
                [
                    "Navigate to and open Settings.",
                    "Tap Display then Dark mode.",
                    "Turn Dark mode on and set Sunset to sunrise.",
                ],
            )
        ],
    ),
    article(
        "siis_video_shake",
        "camera",
        "Videos look shaky when walking",
        [
            "walking videos are jittery",
            "need super steady video",
            "stabilize galaxy video",
        ],
        """Enable video stabilization or Super steady. High fps helps.

1. Camera settings Video stabilization on.
2. Use Super steady for walk-and-talk clips.
""",
        "Video Shake",
        "Configuration",
        "Video stabilization settings",
        [
            action(
                "Enable Video Stabilization",
                "It will smooth handheld walking video",
                "auto",
                "video_stabilization",
                [
                    "Open Camera settings.",
                    "Turn Video stabilization on.",
                    "For walking shots, swipe to More and choose Super steady.",
                ],
            )
        ],
    ),
    article(
        "siis_storage_full",
        "performance",
        "Phone storage is full and apps crash",
        [
            "storage almost full",
            "cannot install apps no space",
            "gallery cannot save photos",
        ],
        """Clear cached files and large videos from Storage in Device care before uninstalling apps.

1. Settings Battery and device care Storage.
2. Clean cached files and trash.
3. Move photos off device.
""",
        "Storage Space",
        "Troubleshooting",
        "Storage cleanup settings",
        [
            action(
                "Clean Cached Storage",
                "It will reclaim space from junk files",
                "auto",
                "storage",
                [
                    "Open Device care then Storage.",
                    "Tap Clean now.",
                    "Delete trash and unused installation files.",
                ],
            )
        ],
    ),
    article(
        "siis_unknown_ir_remote",
        "performance",
        "Television remote app cannot find the IR blaster",
        [
            "ir blaster missing on galaxy a series",
            "universal remote not working",
            "control tv from phone infrared",
        ],
        """This device family does not include an infrared blaster. There is no Settings screen that enables IR. Do not invent steps or service-center URLs.
""",
        "Infrared Remote",
        "Troubleshooting",
        "Infrared remote missing",
        [],
    ),
]


QUERIES = [
    {"id": "q_swipe", "domain": "display", "text": "phone swipe gestures wrong direction after app install"},
    {"id": "q_battery", "domain": "battery", "text": "the battery dies fast even when I barely use the phone"},
    {"id": "q_flicker", "domain": "display", "text": "Screen flickers and the battery dies fast"},
    {"id": "q_camera", "domain": "camera", "text": "camera got blurry after the update"},
    {"id": "q_slow", "domain": "performance", "text": "My phone got slow after the update"},
    {"id": "q_heat", "domain": "battery", "text": "phone gets really hot on the wireless charger overnight"},
    {"id": "q_dark", "domain": "display", "text": "dark mode is not applying and apps stay bright at night"},
    {"id": "q_video", "domain": "camera", "text": "videos shake too much when I walk"},
    {"id": "q_storage", "domain": "performance", "text": "storage is full so gallery cannot save photos"},
    {"id": "q_ir", "domain": "performance", "text": "universal remote cannot find the infrared blaster"},
    {"id": "q_typo_swipe", "domain": "display", "text": "swype navigaton going up down not sideways after app"},
    {"id": "q_formal_battery", "domain": "battery", "text": "Device exhibits accelerated battery discharge during idle periods"},
]


GOLD = [
    {
        "file": "01_swipe_navigation.json",
        "query": "The mobile phone swipe navigation moves up or down instead of left or right after downloading an app",
        "article_id": "siis_swipe_axis",
    },
    {
        "file": "02_battery_drain.json",
        "query": "My battery dies fast even on standby",
        "article_id": "siis_battery_fast_drain",
    },
    {
        "file": "03_screen_flicker.json",
        "query": "Screen flickers at night when the brightness is low",
        "article_id": "siis_screen_flicker",
    },
    {
        "file": "04_camera_blur.json",
        "query": "Photos look smeared and the camera hunts for focus",
        "article_id": "siis_camera_blur",
    },
    {
        "file": "05_slow_update.json",
        "query": "Galaxy got laggy after the software update",
        "article_id": "siis_slow_after_update",
    },
]


def main() -> None:
    raise SystemExit(
        "Legacy synthetic-data generator. data/ now holds the official Theme 2 kit; "
        "running this would overwrite it. Kept only for history."
    )
    DATA.mkdir(parents=True, exist_ok=True)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    (DATA / "deeplinks.json").write_text(json.dumps(DEEPLINKS, indent=2) + "\n")
    (DATA / "siis_responses.json").write_text(json.dumps(ARTICLES, indent=2) + "\n")
    (DATA / "queries.json").write_text(json.dumps(QUERIES, indent=2) + "\n")
    (DATA / "samples" / "index.json").write_text(
        json.dumps(
            [{"file": g["file"], "query": g["query"], "article_id": g["article_id"]} for g in GOLD],
            indent=2,
        )
        + "\n"
    )
    print(f"deeplinks={len(DEEPLINKS)} articles={len(ARTICLES)} queries={len(QUERIES)}")


if __name__ == "__main__":
    main()
