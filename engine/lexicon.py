"""Domain vocabulary: symptoms, action categories, informational headings, device models.

Everything the deterministic path "knows" about Galaxy troubleshooting lives here so it
can be reviewed in one place. Nothing in this file is copied into plans as a step — it is
only used to classify, name and rank text that comes from the SIIS reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Symptom:
    key: str
    pattern: re.Pattern
    title: str  # 2-3 word sentence-case plan title
    topic: str  # Title Case topic for the goal line
    phrase: str  # natural phrase used for paraphrases


def _s(key: str, pattern: str, title: str, topic: str, phrase: str) -> Symptom:
    return Symptom(key, re.compile(pattern, re.IGNORECASE), title, topic, phrase)


# Order matters: the first match wins for the title, all matches feed the cache signature.
SYMPTOMS: list[Symptom] = [
    _s("cracked", r"\b(crack(ed|s)?|shatter(ed)?|smash(ed)?|broken (screen|glass|display)|bleeding pixels?|ink blots?)\b",
       "Cracked screen repair", "Screen Damage", "the screen is cracked"),
    _s("half_black", r"\b(half (black|dark)|one side of the (display|screen)|part of the screen)\b",
       "Partial screen blackout", "Partial Display", "half of the screen is black"),
    _s("floating", r"\b(floating (circle|button|icon|bubble)|assistant menu|hovers? on (my )?screen)\b",
       "Floating button settings", "Floating Button", "a floating circle stays on the screen"),
    _s("small_screen", r"\b(screen (stays )?small|doesn'?t fill|not full (size|screen)|aspect ratio|shrunk|expand to full)\b",
       "Screen size display", "Screen Size", "the screen stays small and does not fill the display"),
    _s("flicker", r"\b(flicker(s|ing)?|flash(es|ing)?|blink(s|ing)?|strobe)\b",
       "Screen flicker issue", "Screen Flicker", "the screen flickers"),
    _s("touch", r"\b(touch(screen)?( (is|feels))? (lag(gy)?|delay(ed)?|unresponsive|not (working|responding))|inputs? (are )?delayed|laggy|ghost touch|touch doesn'?t work|doesn'?t respond to touch|not respond(ing)? to touch|touch responsiveness)\b",
       "Touchscreen responsiveness", "Touchscreen", "the touchscreen is laggy and unresponsive"),
    _s("distorted", r"\b(distort(ed|ion)|rotate|rotation|upside down|sideways)\b",
       "Screen display distortion", "Screen Distortion", "the screen looks distorted"),
    _s("blank", r"\b(blank|black|dark|no (image|display|picture)|won'?t turn on|nothing (is )?(visible|shows)|went off|blue screen|white screen|turns? (completely )?white|(hardly|barely|can'?t) see anything)\b",
       "Blank screen display", "Blank Screen", "the screen stays black"),
    _s("icons_dark", r"\b(icons? (are )?(dark|lit)|apps? won'?t open)\b",
       "Unresponsive app icons", "App Icons", "only a few app icons respond"),
    _s("email", r"\b(e-?mail|gmail|outlook)\b",
       "Email app display", "Email App", "the screen goes blank when opening email"),
    _s("transfer", r"\b(smart switch|transfer (my )?data|qr code|data transfer)\b",
       "Data Transfer setup", "Data Transfer", "Data Transfer cannot move data"),
    _s("fingerprint", r"\b(fingerprint|biometric)s?\b",
       "Fingerprint unlock issue", "Fingerprint Unlock", "the fingerprint sensor does not unlock the phone"),
    _s("battery", r"\b(battery|drain(s|ing)?|dies fast)\b",
       "Battery fast drain", "Battery Drain", "the battery drains fast"),
    _s("slow", r"\b(slow|sluggish|stutter(ing)?|lag)\b",
       "Slow device performance", "Slow Performance", "the phone is slow"),
    _s("navigation", r"\b(swipe|gesture|navigation bar|nav bar)\b",
       "Swipe navigation settings", "Swipe Navigation", "swipe navigation behaves wrongly"),
    _s("camera", r"\b(camera|photo|video)\b",
       "Camera display issue", "Camera", "the camera preview misbehaves"),
    _s("wifi", r"\b(wi-?fi|internet|mobile data|network)\b",
       "Network connection issue", "Network Connection", "the phone cannot connect to the internet"),
]

SYMPTOM_BY_KEY = {s.key: s for s in SYMPTOMS}

CONFIG_INTENT_RE = re.compile(
    r"\b(i want to (remove|turn off|turn on|enable|disable|change|hide|set)|how (do|can) i (remove|turn off|turn on|enable|disable|change|set up|hide)|get rid of)\b",
    re.IGNORECASE,
)

# --- action categories -------------------------------------------------------------

# Disruptive / irreversible (spec: factory reset, restart, firmware update, safe mode).
CRITICAL_RE = re.compile(
    r"\b(factory (data )?reset|reset (your|the) (phone|device|tablet)|safe mode|force (a )?restart|"
    r"restart(ing)? (your|the) (phone|device|tablet)|\brestart\b|reboot|software update|update (device|your|the) software|"
    r"firmware|wipe|clear data|delete all|erase all|remove the battery|uninstall)\b",
    re.IGNORECASE,
)
# Physical / human interventions — never carry an actionable deeplink.
MANUAL_RE = re.compile(
    r"\b(service cent(er|re)|repair|walk-in|mail-in|contact (samsung|techcorp|customer|your|the)|support cent(er|re)|samsung support|customer support|"
    r"premium care|inspect|physical damage|liquid|charger|charging port|charge (the|your) (device|phone)|"
    r"usb (cable|mouse|adapter)|hdmi|monitor|mouse|keyboard|adapter|screen protector|microfiber|cloth|"
    r"personal computer|on a pc|on your pc|lighting|flashlight|ejector|sim|service provider|email provider|"
    r"proof of purchase|power button|side button|volume down)\b",
    re.IGNORECASE,
)

# Headings that describe rather than instruct.
INFO_HEADING_RE = re.compile(
    r"^(overview|glossary|requirements|note|important notes?|what is|what are|understanding|about|useful|"
    r"introduction|background|why|screen mirroring vs|.* vs\.? .*|cracked screen|ink blots|bleeding pixels|"
    r"service options|device damage and repair options|troubleshooting steps for|troubleshooting .* issues?|"
    r"screen rotation troubleshooting|data transfer using|screen mirroring and casting explained)",
    re.IGNORECASE,
)

IMPERATIVE_VERBS = (
    "tap", "touch", "press", "hold", "swipe", "select", "open", "navigate", "go", "enter", "turn", "enable",
    "disable", "check", "inspect", "remove", "connect", "disconnect", "plug", "insert", "shine", "charge",
    "try", "visit", "schedule", "contact", "reach", "restart", "clear", "increase", "adjust", "change",
    "drag", "set", "use", "back", "search", "locate", "examine", "ensure", "make", "review", "confirm",
    "wait", "reinsert", "keep", "avoid", "wipe", "launch", "scan", "place", "power", "let", "perform",
    "update", "install", "choose", "add", "sign", "reconnect", "toggle", "switch", "find",
    "verify", "attempt", "force", "improve", "reduce", "fix", "get", "customize", "exit", "create",
    "mirror", "project", "access", "test", "schedule", "drag", "disconnect", "increase", "rotate",
)

LEAD_IN_RE = re.compile(
    r"^(first|then|next|now|finally|also|alternatively|afterward|afterwards|simply|please|additionally|"
    r"to do this|once connected|once in safe mode|after charging|otherwise)[,:]?\s+",
    re.IGNORECASE,
)

NON_PHONE_RE = re.compile(
    r"\b(on your pc|windows (10|11|key)|your pc|on a samsung tv|on your tv|from all settings on your tv|"
    r"iphone|ipad|airplay|chromecast|fire stick|google website|google device manager|\bpc\b|"
    r"device connect manager|external device manager)\b",
    re.IGNORECASE,
)

DEVICE_RE = re.compile(
    r"\b(galaxy\s+)?(z\s*(flip|fold)\s*\d*|s\d{2}\s*(ultra|plus|\+|fe)?|a\d{2,3}[a-z]?(/a\d{2})?|tab\s*s?\d*|note\s*\d+|tablet)\b",
    re.IGNORECASE,
)

# Everyday words customers use for settings, mapped to catalog vocabulary.
SETTING_SYNONYMS: dict[str, str] = {
    "floating circle": "assistant menu floating button",
    "blue light": "eye comfort shield",
    "screen size": "screen zoom",
    "wake up": "lift to wake double tap to turn on screen",
    "screen off": "screen timeout",
    "backup": "back up data",
    "cloud": "samsung cloud back up data",
    "nav bar": "navigation bar",
    "gestures": "navigation gestures swipe gestures",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "my", "your", "is", "it", "its",
    "i", "me", "this", "that", "be", "are", "was", "at", "by", "from", "as", "so", "if", "can", "cant",
    "can't", "do", "does", "doesn't", "dont", "don't", "when", "then", "than", "phone", "device", "samsung",
    "galaxy", "have", "has", "had", "after", "even", "any", "other", "too", "just", "very", "all", "some",
    "get", "got", "into", "up", "out", "no", "not", "won't", "will", "would", "could", "about", "only",
}
