# 🖱️ Pico Web HID

Control any USB computer wirelessly from your phone or browser — using a **Raspberry Pi Pico W** as a USB HID device.

No app install needed. Just connect to the WiFi hotspot and open a browser.

![PicoHID UI](https://img.shields.io/badge/CircuitPython-9.x-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

| Tab | What it does |
|-----|-------------|
| 🖱️ **Mouse** | Full gesture trackpad — 1-finger move, 2-finger scroll, tap click, double-tap, 2-finger tap right-click |
| ⌨️ **Keys** | Type text, special keys (F1–F12, arrows, etc.) |
| ⚡ **Hotkeys** | One-tap shortcuts: Ctrl+C/V/Z, Win+R, Alt+F4, media keys, volume |
| 🦆 **Ducky** | Run DuckyScript payloads with presets |
| 📋 **Clips** | Save text snippets — tap to type instantly |
| 📡 **WiFi** | Connect to home router, LED control |
| 💻 **Terminal** | Run ducky commands with live log |
| 🐍 **Snake** | Playable Snake game |

---

## 🛒 What You Need

- Raspberry Pi Pico W (~$6)
- USB-A to Micro-USB cable (data cable, not charge-only)
- A computer to control (Windows / Mac / Linux)
- Your phone or any browser

---

## 🚀 Quick Start

### 1. Install CircuitPython

Download **CircuitPython 9.x** for Pico W from [circuitpython.org](https://circuitpython.org/board/raspberry_pi_pico_w/)

Hold **BOOTSEL** button while plugging in USB → drag `.uf2` file onto the `RPI-RP2` drive.

### 2. Install Libraries

Download the [CircuitPython Library Bundle](https://circuitpython.org/libraries) and copy these to `CIRCUITPY/lib/`:

```
adafruit_hid/
```

That's the only library needed — everything else is built-in.

### 3. Copy the firmware

Copy `code.py` to the root of your `CIRCUITPY` drive.

```
CIRCUITPY/
├── code.py          ← this file
└── lib/
    └── adafruit_hid/
```

### 4. Enable USB HID

CircuitPython 9 requires a `boot.py` to enable all HID devices. Create `CIRCUITPY/boot.py`:

```python
import usb_hid

usb_hid.enable((
    usb_hid.Device.MOUSE,
    usb_hid.Device.KEYBOARD,
    usb_hid.Device.CONSUMER_CONTROL,
))
```

**Unplug and replug** the Pico W after creating `boot.py`.

### 5. Connect

1. On your phone, connect to WiFi: **`PicoHID`** / password: **`pico1234`**
2. Open browser → `http://192.168.4.1/login`
3. Login: **`admin`** / **`admin`**

---

## ⚙️ Configuration

Edit the top of `code.py`:

```python
AP_SSID     = "PicoHID"      # hotspot name
AP_PASS     = "pico1234"     # hotspot password (min 8 chars)
LOGIN_USER  = "admin"        # web UI username
LOGIN_PASS  = "admin"        # web UI password
```

---

## 📡 WiFi Modes

The Pico W runs **both AP and STA simultaneously**:

- **AP mode** always on → your phone connects directly to Pico
- **STA mode** optional → Pico also joins your home router

To connect to your router: go to **WiFi tab** → enter SSID + password → Connect.  
The connection is saved to `/wifi.json` and auto-reconnects on boot.

---

## 💡 LED Status

| Pattern | Meaning |
|---------|---------|
| 2 slow blinks | Boot OK, AP ready |
| Solid ON | Connected to home WiFi (STA) |
| 5 fast blinks | WiFi connection failed |
| Flicker | Web requests being processed |

---

## 🦆 DuckyScript Reference

Supported commands:

```
STRING hello world    → types text
DELAY 500             → wait 500ms
ENTER / TAB / ESC / SPACE / BACKSPACE
GUI R                 → Win+R
CTRL C / CTRL V / CTRL Z / CTRL A / CTRL S
ALT F4 / ALT TAB
CTRL ALT DELETE
GUI SHIFT S           → Snipping tool
```

---

## 🔧 Troubleshooting

**Web page won't load**
- Make sure your phone is connected to `PicoHID` WiFi, not your home router
- Try `http://192.168.4.1` directly (not https)

**HID not working (mouse/keyboard does nothing)**
- Check `boot.py` exists and has the correct content
- Replug the USB cable after creating/editing `boot.py`
- Open serial console to see boot messages (`HID OK` = good)

**Page loads but actions are slow**
- This is normal for the first few requests as WiFi stabilises
- Movement speed: use the SPD + ACC sliders on the trackpad

**Serial console shows errors**
- Connect with Thonny or `screen /dev/ttyACM0 115200`
- Most errors show the exact line and fix

---

## 📁 Files

```
code.py      Main firmware — copy to CIRCUITPY root
boot.py      USB HID config — copy to CIRCUITPY root (create manually)
README.md    This file
```

---

## 📜 License

MIT — free to use, modify, share.
