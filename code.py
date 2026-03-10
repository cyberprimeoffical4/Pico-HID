import wifi, time, usb_hid, json, random, socketpool
import board, digitalio

# ── LED ──────────────────────────────────────────────────────────────
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

def led_on():  led.value = True
def led_off(): led.value = False
def led_blink(n=3, fast=False):
    t = 0.08 if fast else 0.2
    for _ in range(n):
        led.value = True;  time.sleep(t)
        led.value = False; time.sleep(t)

# ── HID ──────────────────────────────────────────────────────────────
try:
    from adafruit_hid.mouse import Mouse
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.keycode import Keycode
    from adafruit_hid.consumer_control import ConsumerControl
    from adafruit_hid.consumer_control_code import ConsumerControlCode
    mouse_dev    = Mouse(usb_hid.devices)
    keyboard_dev = Keyboard(usb_hid.devices)
    cc_dev       = ConsumerControl(usb_hid.devices)
    print("HID OK")
except Exception as e:
    print("HID fail:", e)
    mouse_dev = keyboard_dev = cc_dev = None

# ── CONFIG ────────────────────────────────────────────────────────────
AP_SSID     = "PicoHID"
AP_PASS     = "pico1234"
LOGIN_USER  = "admin"
LOGIN_PASS  = "admin"
CFG_FILE    = "/wifi.json"

# ── WIFI ──────────────────────────────────────────────────────────────
ap_ip = "192.168.4.1"
sta_ip = None
sta_ok = False

def ap_start():
    global ap_ip
    for _ in range(5):
        try:
            wifi.radio.start_ap(ssid=AP_SSID, password=AP_PASS)
            time.sleep(1)
            ip = wifi.radio.ipv4_address_ap
            if ip:
                ap_ip = str(ip)
                print("AP:", ap_ip)
                return True
        except Exception as e:
            print("AP err:", e)
            time.sleep(1)
    return False

def sta_connect(ssid, pw, timeout=15):
    global sta_ip, sta_ok
    sta_ip = None; sta_ok = False
    if not ssid: return False
    for n in range(3):
        try:
            print("STA try", n+1, ssid)
            wifi.radio.connect(ssid, pw, timeout=timeout)
            time.sleep(2)
            ip = wifi.radio.ipv4_address
            if ip:
                sta_ip = str(ip); sta_ok = True
                print("STA OK:", sta_ip)
                led_on()          # solid = STA connected
                # re-assert AP
                try: wifi.radio.start_ap(ssid=AP_SSID, password=AP_PASS)
                except: pass
                return True
        except Exception as e:
            print("STA fail:", e)
            time.sleep(2)
    led_blink(5, fast=True)  # fast blink = STA failed
    led_off()
    return False

def wifi_load():
    try:
        with open(CFG_FILE) as f: return json.load(f)
    except: return None

def wifi_save(s, p):
    try:
        with open(CFG_FILE, "w") as f: json.dump({"s":s,"p":p}, f)
    except: pass

ap_start()
led_blink(2)          # 2 blinks = AP ready
cfg = wifi_load()
if cfg: sta_connect(cfg.get("s",""), cfg.get("p",""))

# ── KEYMAP ────────────────────────────────────────────────────────────
KM = {}
if keyboard_dev:
    KM = {
        "a":(Keycode.A,0),"b":(Keycode.B,0),"c":(Keycode.C,0),"d":(Keycode.D,0),
        "e":(Keycode.E,0),"f":(Keycode.F,0),"g":(Keycode.G,0),"h":(Keycode.H,0),
        "i":(Keycode.I,0),"j":(Keycode.J,0),"k":(Keycode.K,0),"l":(Keycode.L,0),
        "m":(Keycode.M,0),"n":(Keycode.N,0),"o":(Keycode.O,0),"p":(Keycode.P,0),
        "q":(Keycode.Q,0),"r":(Keycode.R,0),"s":(Keycode.S,0),"t":(Keycode.T,0),
        "u":(Keycode.U,0),"v":(Keycode.V,0),"w":(Keycode.W,0),"x":(Keycode.X,0),
        "y":(Keycode.Y,0),"z":(Keycode.Z,0),
        "0":(Keycode.ZERO,0),"1":(Keycode.ONE,0),"2":(Keycode.TWO,0),
        "3":(Keycode.THREE,0),"4":(Keycode.FOUR,0),"5":(Keycode.FIVE,0),
        "6":(Keycode.SIX,0),"7":(Keycode.SEVEN,0),"8":(Keycode.EIGHT,0),
        "9":(Keycode.NINE,0)," ":(Keycode.SPACE,0),"\n":(Keycode.ENTER,0),
        "-":(Keycode.MINUS,0),"_":(Keycode.MINUS,1),"=":(Keycode.EQUALS,0),
        "+":(Keycode.EQUALS,1),".":(Keycode.PERIOD,0),",":(Keycode.COMMA,0),
        "/":(Keycode.FORWARD_SLASH,0),"?":(Keycode.FORWARD_SLASH,1),
        "!":(Keycode.ONE,1),"@":(Keycode.TWO,1),"#":(Keycode.THREE,1),
        "$":(Keycode.FOUR,1),"%":(Keycode.FIVE,1),"^":(Keycode.SIX,1),
        "&":(Keycode.SEVEN,1),"*":(Keycode.EIGHT,1),"(":(Keycode.NINE,1),
        ")":(Keycode.ZERO,1),
    }

# ── HELPERS ───────────────────────────────────────────────────────────
def udec(s):
    s = s.replace("+", " ")
    o = ""; i = 0
    while i < len(s):
        if s[i] == "%" and i+2 < len(s):
            try: o += chr(int(s[i+1:i+3], 16)); i += 3
            except: o += s[i]; i += 1
        else: o += s[i]; i += 1
    return o

sessions = set()
def mktok():
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(24))

def getcook(hdrs, name):
    for p in hdrs.get("cookie","").split(";"):
        p = p.strip()
        if p.startswith(name+"="): return p[len(name)+1:]
    return None

def authed(hdrs):
    t = getcook(hdrs, "t")
    return t in sessions if t else False

# ── DUCKY ─────────────────────────────────────────────────────────────
def ducky(script):
    if not keyboard_dev: return
    SHORTCUTS = {
        "GUI R":(Keycode.GUI,Keycode.R), "GUI D":(Keycode.GUI,Keycode.D),
        "GUI L":(Keycode.GUI,Keycode.L), "GUI E":(Keycode.GUI,Keycode.E),
        "GUI SHIFT S":(Keycode.GUI,Keycode.SHIFT,Keycode.S),
        "ALT TAB":(Keycode.ALT,Keycode.TAB), "ALT F4":(Keycode.ALT,Keycode.F4),
        "CTRL C":(Keycode.CONTROL,Keycode.C), "CTRL V":(Keycode.CONTROL,Keycode.V),
        "CTRL Z":(Keycode.CONTROL,Keycode.Z), "CTRL A":(Keycode.CONTROL,Keycode.A),
        "CTRL S":(Keycode.CONTROL,Keycode.S), "CTRL X":(Keycode.CONTROL,Keycode.X),
        "CTRL ALT DELETE":(Keycode.CONTROL,Keycode.ALT,Keycode.DELETE),
    }
    for line in script.split("\n"):
        line = line.strip()
        if not line: continue
        if line.startswith("DELAY"):
            try: time.sleep(int(line.split()[1])/1000)
            except: pass
        elif line.startswith("STRING"):
            for c in line[7:]:
                cl = c.lower()
                if cl in KM:
                    k, sh = KM[cl]
                    if c.isupper(): sh = 1
                    if sh: keyboard_dev.send(Keycode.SHIFT, k)
                    else:  keyboard_dev.send(k)
                    time.sleep(0.03)
        elif line == "ENTER":     keyboard_dev.send(Keycode.ENTER)
        elif line == "TAB":       keyboard_dev.send(Keycode.TAB)
        elif line == "ESC":       keyboard_dev.send(Keycode.ESCAPE)
        elif line == "SPACE":     keyboard_dev.send(Keycode.SPACE)
        elif line == "BACKSPACE": keyboard_dev.send(Keycode.BACKSPACE)
        elif line in SHORTCUTS:   keyboard_dev.send(*SHORTCUTS[line])
        keyboard_dev.release_all()
        time.sleep(0.03)

# ── HTTP HELPERS ──────────────────────────────────────────────────────
def resp_hdr(status, ctype, blen, extra=""):
    return ("HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
            "Connection: close\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Cache-Control: no-cache\r\n"
            "{}\r\n").format(
            status, ctype, blen, extra).encode()

def resp(status, ctype, body, extra=""):
    if isinstance(body, str): body = body.encode()
    return resp_hdr(status, ctype, len(body), extra), body

def redir(loc):
    return resp("302 Found","text/plain",b"",extra="Location: {}\r\n".format(loc))

def json_resp(d):
    s = json.dumps(d)
    return resp("200 OK","application/json",s)

def parse_req(data):
    try:
        sep = b"\r\n\r\n"
        hi = data.find(sep)
        if hi < 0:
            sep = b"\n\n"
            hi = data.find(sep)
        if hi < 0: return "GET","/",{},{},""
        head = data[:hi].decode("utf-8","ignore")
        body = data[hi+len(sep):].decode("utf-8","ignore")
        lines = head.split("\r\n") if "\r\n" in head else head.split("\n")
        parts = lines[0].split()
        method = parts[0] if parts else "GET"
        full   = parts[1] if len(parts)>1 else "/"
        path, qs = (full+"?").split("?",1)[:2]
        qs = qs.rstrip("?")
        hdrs = {}
        for ln in lines[1:]:
            if ":" in ln:
                k,v = ln.split(":",1)
                hdrs[k.strip().lower()] = v.strip()
        args = {}
        for p in qs.split("&"):
            if "=" in p:
                k,v = p.split("=",1)
                args[udec(k)] = udec(v)
        return method, path, args, hdrs, body
    except Exception as e:
        print("parse err:", e)
        return "GET","/",{},{},""

# ── HTML (split into chunks to avoid large string literals in RAM) ────
# Login page — kept tiny
P_LOGIN = (
b"<!DOCTYPE html><html><head>"
b"<meta charset=UTF-8>"
b"<meta name=viewport content='width=device-width,initial-scale=1'>"
b"<title>PicoHID</title>"
b"<style>"
b"*{box-sizing:border-box;margin:0;padding:0}"
b"body{background:#07090f;color:#c8d8ff;font-family:monospace;"
b"min-height:100vh;display:flex;align-items:center;justify-content:center}"
b".b{width:280px;padding:28px;background:#0d1020;border:1px solid #1a2a4a;border-radius:10px}"
b"h2{color:#00f0ff;letter-spacing:3px;font-size:1rem;text-align:center;margin-bottom:20px}"
b"label{display:block;font-size:.6rem;letter-spacing:2px;color:#4a5a7a;margin-bottom:4px}"
b"input{width:100%;background:#07090f;border:1px solid #1a2a4a;border-radius:5px;"
b"color:#c8d8ff;font-family:monospace;font-size:.9rem;padding:9px;outline:none;margin-bottom:12px}"
b"input:focus{border-color:#00f0ff}"
b"button{width:100%;padding:11px;background:transparent;border:1px solid #00f0ff;"
b"border-radius:5px;color:#00f0ff;font-family:monospace;font-size:.7rem;letter-spacing:3px;cursor:pointer}"
b"button:hover{background:rgba(0,240,255,.08)}"
b".e{color:#ff2d78;font-size:.7rem;text-align:center;margin-top:10px;min-height:16px}"
b"</style></head><body>"
b"<div class=b><h2>PICO HID</h2>"
b"<label>USER</label><input id=u value=admin>"
b"<label>PASS</label><input id=p type=password value=admin>"
b"<button onclick=go()>LOGIN</button>"
b"<div class=e id=e></div></div>"
b"<script>"
b"document.getElementById('p').onkeydown=e=>{if(e.key==='Enter')go()};"
b"async function go(){"
b"const r=await fetch('/login',{method:'POST',"
b"headers:{'Content-Type':'application/x-www-form-urlencoded'},"
b"body:'u='+encodeURIComponent(document.getElementById('u').value)"
b"+'&p='+encodeURIComponent(document.getElementById('p').value)});"
b"const j=await r.json();"
b"if(j.ok)location.href='/';"
b"else document.getElementById('e').textContent='WRONG CREDENTIALS';}"
b"</script></body></html>"
)

# Main page CSS — stored as bytes constant
P_CSS = (
b"<style>"
b"*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}"
b":root{--bg:#07090f;--s1:#0d1020;--s2:#111530;--ac:#00f0ff;--r:#ff2d78;--g:#00ff9d;--y:#ffcc00;--t:#c8d8ff;--m:#4a5a7a;--br:rgba(0,240,255,.1)}"
b"body{background:var(--bg);color:var(--t);font-family:monospace;height:100vh;display:flex;flex-direction:column;overflow:hidden}"
b"header{display:flex;align-items:center;justify-content:space-between;padding:7px 12px;"
b"border-bottom:1px solid var(--br);background:var(--s1);flex-shrink:0}"
b".logo{font-size:.8rem;letter-spacing:3px;color:var(--ac)}"
b".dot{width:6px;height:6px;border-radius:50%;background:var(--g);display:inline-block;"
b"box-shadow:0 0 5px var(--g);animation:bk 2s infinite;margin-right:4px}"
b"@keyframes bk{0%,100%{opacity:1}50%{opacity:.15}}"
b".xb{font-family:monospace;font-size:.58rem;color:var(--m);background:none;"
b"border:1px solid var(--m);border-radius:4px;padding:3px 7px;cursor:pointer}"
b"nav{display:flex;background:var(--s1);border-bottom:1px solid var(--br);"
b"overflow-x:auto;flex-shrink:0;scrollbar-width:none}"
b"nav::-webkit-scrollbar{display:none}"
b".tb{flex:0 0 auto;padding:8px 12px;font-family:monospace;font-size:.58rem;"
b"letter-spacing:1px;color:var(--m);border:none;background:none;cursor:pointer;"
b"border-bottom:2px solid transparent;white-space:nowrap}"
b".tb.on{color:var(--ac);border-bottom-color:var(--ac)}"
b"main{flex:1;overflow-y:auto;padding:12px}"
b".pn{display:none}.pn.on{display:block}"
b".st{font-size:.52rem;letter-spacing:3px;color:var(--m);margin-bottom:7px;"
b"display:flex;align-items:center;gap:7px}"
b".st::after{content:'';flex:1;height:1px;background:var(--br)}"
b".sec{margin-bottom:14px}"
b"#pad{width:100%;height:180px;background:var(--s2);border:1px solid var(--br);"
b"border-radius:10px;touch-action:none;cursor:crosshair;position:relative}"
b"#pad.t{border-color:var(--ac)}"
b".sr{display:flex;align-items:center;gap:8px;margin-top:6px}"
b".sr label{font-size:.58rem;color:var(--m);white-space:nowrap}"
b"input[type=range]{flex:1;accent-color:var(--ac)}"
b".sv{width:18px;text-align:right;font-size:.72rem;color:var(--ac)}"
b".g2{display:grid;grid-template-columns:1fr 1fr;gap:6px}"
b".g3{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}"
b".g4{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}"
b".btn{padding:10px 6px;border:1px solid var(--br);border-radius:6px;background:var(--s2);"
b"color:var(--t);font-family:monospace;font-size:.68rem;cursor:pointer;text-align:center;transition:.1s}"
b".btn:hover{border-color:var(--ac);color:var(--ac)}.btn:active{opacity:.6}"
b".ac{border-color:var(--ac);color:var(--ac)}.rc{border-color:var(--r);color:var(--r)}"
b".gc{border-color:var(--g);color:var(--g)}.yc{border-color:var(--y);color:var(--y)}"
b"textarea{width:100%;background:var(--s2);border:1px solid var(--br);border-radius:6px;"
b"color:var(--g);font-family:monospace;font-size:.75rem;padding:8px;resize:vertical;"
b"min-height:70px;outline:none;line-height:1.5}"
b"textarea:focus{border-color:var(--ac)}"
b".row{display:flex;gap:6px;margin-top:6px}.row .btn{flex:1}"
b".mc{background:var(--s2);border:1px solid var(--br);border-radius:7px;"
b"padding:10px;cursor:pointer;transition:.12s}"
b".mc:hover{border-color:var(--ac)}.mc:active{transform:scale(.97)}"
b".mn{font-size:.52rem;letter-spacing:2px;color:var(--ac);margin-bottom:2px}"
b".md{font-size:.62rem;color:var(--m)}"
b".wc{background:var(--s2);border:1px solid var(--br);border-radius:7px;padding:11px;margin-bottom:7px}"
b".wc h3{font-size:.55rem;letter-spacing:2px;color:var(--ac);margin-bottom:9px}"
b".fi{margin-bottom:8px}.fi label{display:block;font-size:.55rem;letter-spacing:2px;color:var(--m);margin-bottom:3px}"
b".fi input{width:100%;background:rgba(0,240,255,.02);border:1px solid var(--br);"
b"border-radius:5px;color:var(--t);font-family:monospace;font-size:.78rem;padding:7px 9px;outline:none}"
b".fi input:focus{border-color:var(--ac)}"
b".ir{display:flex;justify-content:space-between;padding:5px 0;"
b"border-bottom:1px solid rgba(255,255,255,.04);font-size:.68rem}"
b".ir:last-child{border:none}"
b".il{color:var(--m)}.iv{color:var(--ac)}.ivg{color:var(--g)}.ivr{color:var(--r)}"
b"#log{background:var(--s1);border:1px solid var(--br);border-radius:6px;"
b"padding:9px;height:160px;overflow-y:auto;font-size:.68rem;line-height:1.7}"
b".lok{color:var(--g)}.lerr{color:var(--r)}.linf{color:var(--ac)}.lsys{color:var(--m)}"
b".ti{display:flex;gap:6px;margin-top:6px;align-items:center}"
b".ti span{color:var(--ac);font-size:.75rem}"
b".ti input{flex:1;background:var(--s2);border:1px solid var(--br);border-radius:5px;"
b"color:var(--g);font-family:monospace;font-size:.75rem;padding:6px 8px;outline:none}"
b"#snk{display:block;margin:0 auto 8px;border:1px solid var(--br);border-radius:6px;max-width:100%}"
b".sd{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;max-width:150px;margin:0 auto}"
b"#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%) translateY(55px);"
b"background:var(--s2);border:1px solid var(--ac);border-radius:6px;padding:7px 16px;"
b"font-size:.68rem;color:var(--ac);transition:transform .22s;z-index:999;pointer-events:none;white-space:nowrap}"
b"#toast.on{transform:translateX(-50%) translateY(0)}"
b"</style>"
)

# Main page HTML body
P_BODY = (
b"<header>"
b"<span class=logo>PICO HID</span>"
b"<div><span class=dot id=dot></span>"
b"<span id=sip style='font-size:.58rem;color:var(--m)'></span>"
b"<button class=xb onclick=\"fetch('/logout').then(()=>location.href='/login')\">EXIT</button></div>"
b"</header>"
b"<nav>"
b"<button class='tb on' onclick=\"go('mo',this)\">MOUSE</button>"
b"<button class=tb onclick=\"go('kb',this)\">KEYS</button>"
b"<button class=tb onclick=\"go('hk',this)\">HOTKEYS</button>"
b"<button class=tb onclick=\"go('dk',this)\">DUCKY</button>"
b"<button class=tb onclick=\"go('cl',this)\">CLIPS</button>"
b"<button class=tb onclick=\"go('wf',this)\">WIFI</button>"
b"<button class=tb onclick=\"go('tm',this)\">TERM</button>"
b"<button class=tb onclick=\"go('sn',this)\">SNAKE</button>"
b"</nav><main>"
# MOUSE
b"<div id=p-mo class='pn on'>"
b"<div class=sec><div class=st>TRACKPAD</div>"
b"<div id=pad style='position:relative'>"
b"<div id=pgst style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:.55rem;letter-spacing:2px;color:rgba(0,240,255,.18);pointer-events:none;text-align:center'>TOUCH TO MOVE</div>"
b"</div>"
b"<div style='display:flex;gap:8px;margin-top:6px;align-items:center'>"
b"<label style='font-size:.55rem;color:var(--m);white-space:nowrap'>SPD</label>"
b"<input type=range id=spd min=1 max=10 value=4 style='flex:1;accent-color:var(--ac)' oninput='document.getElementById(\"sv\").textContent=this.value'>"
b"<span id=sv style='width:18px;text-align:right;font-size:.72rem;color:var(--ac)'>4</span>"
b"<label style='font-size:.55rem;color:var(--m);white-space:nowrap;margin-left:4px'>ACC</label>"
b"<input type=range id=acc min=1 max=5 value=2 style='flex:1;accent-color:var(--y)' oninput='document.getElementById(\"ac2\").textContent=this.value'>"
b"<span id=ac2 style='width:18px;text-align:right;font-size:.72rem;color:var(--y)'>2</span>"
b"</div>"
b"<div style='display:flex;gap:6px;margin-top:5px'>"
b"<div id=tl style='flex:1;padding:11px 0;text-align:center;border:1px solid var(--br);border-radius:6px;background:var(--s2);font-size:.58rem;color:var(--m);cursor:pointer;user-select:none'>LEFT</div>"
b"<div id=tm style='flex:1;padding:11px 0;text-align:center;border:1px solid var(--br);border-radius:6px;background:var(--s2);font-size:.58rem;color:var(--m);cursor:pointer;user-select:none'>MID</div>"
b"<div id=tr style='flex:1;padding:11px 0;text-align:center;border:1px solid var(--br);border-radius:6px;background:var(--s2);font-size:.58rem;color:var(--m);cursor:pointer;user-select:none'>RIGHT</div>"
b"</div>"
b"<div style='margin-top:5px;font-size:.5rem;color:var(--m);text-align:center'>1-finger MOVE &nbsp;2-finger SCROLL &nbsp;TAP left &nbsp;2-TAP right &nbsp;2x TAP dblclick</div>"
b"</div></div>"
# KEYS
b"<div id=p-kb class=pn>"
b"<div class=sec><div class=st>TYPE TEXT</div>"
b"<textarea id=kt placeholder='Text to type...'></textarea>"
b"<div class=row><button class='btn ac' onclick=sendText()>TYPE</button>"
b"<button class=btn id=kclr>CLR</button></div></div>"
b"<div class=sec><div class=st>SPECIAL</div><div class=g4>"
b"<button class=btn onclick=\"sk('ENTER')\">ENT</button>"
b"<button class=btn onclick=\"sk('TAB')\">TAB</button>"
b"<button class=btn onclick=\"sk('ESC')\">ESC</button>"
b"<button class=btn onclick=\"sk('SPACE')\">SPC</button>"
b"<button class=btn onclick=\"sk('BACKSPACE')\">BSP</button>"
b"<button class=btn onclick=\"sk('DELETE')\">DEL</button>"
b"<button class=btn onclick=\"sk('HOME')\">HOM</button>"
b"<button class=btn onclick=\"sk('END')\">END</button>"
b"<button class=btn onclick=\"sk('PAGEUP')\">PGU</button>"
b"<button class=btn onclick=\"sk('PAGEDOWN')\">PGD</button>"
b"<button class=btn onclick=\"sk('UP')\">&#x25B2;</button>"
b"<button class=btn onclick=\"sk('DOWN')\">&#x25BC;</button>"
b"<button class=btn onclick=\"sk('LEFT')\">&#x25C4;</button>"
b"<button class=btn onclick=\"sk('RIGHT')\">&#x25BA;</button>"
b"<button class=btn onclick=\"sk('INSERT')\">INS</button>"
b"<button class=btn onclick=\"sk('PRINTSCREEN')\">PRT</button>"
b"</div></div>"
b"<div class=sec><div class=st>FN KEYS</div><div class=g4>"
b"<button class=btn onclick=\"sk('F1')\">F1</button><button class=btn onclick=\"sk('F2')\">F2</button>"
b"<button class=btn onclick=\"sk('F3')\">F3</button><button class=btn onclick=\"sk('F4')\">F4</button>"
b"<button class=btn onclick=\"sk('F5')\">F5</button><button class=btn onclick=\"sk('F6')\">F6</button>"
b"<button class=btn onclick=\"sk('F7')\">F7</button><button class=btn onclick=\"sk('F8')\">F8</button>"
b"<button class=btn onclick=\"sk('F9')\">F9</button><button class=btn onclick=\"sk('F10')\">F10</button>"
b"<button class=btn onclick=\"sk('F11')\">F11</button><button class=btn onclick=\"sk('F12')\">F12</button>"
b"</div></div></div>"
# HOTKEYS
b"<div id=p-hk class=pn>"
b"<div class=sec><div class=st>WINDOWS</div><div class=g2>"
b"<button class='btn yc' onclick=\"sh('GUI R')\">Run</button>"
b"<button class='btn yc' onclick=\"sh('GUI D')\">Desktop</button>"
b"<button class='btn yc' onclick=\"sh('GUI L')\">Lock</button>"
b"<button class='btn yc' onclick=\"sh('GUI E')\">Explorer</button>"
b"</div></div>"
b"<div class=sec><div class=st>EDIT</div><div class=g3>"
b"<button class=btn onclick=\"sh('CTRL C')\">Copy</button>"
b"<button class=btn onclick=\"sh('CTRL X')\">Cut</button>"
b"<button class=btn onclick=\"sh('CTRL V')\">Paste</button>"
b"<button class=btn onclick=\"sh('CTRL Z')\">Undo</button>"
b"<button class=btn onclick=\"sh('CTRL Y')\">Redo</button>"
b"<button class=btn onclick=\"sh('CTRL A')\">All</button>"
b"<button class=btn onclick=\"sh('CTRL S')\">Save</button>"
b"<button class=btn onclick=\"sh('CTRL F')\">Find</button>"
b"<button class=btn onclick=\"sh('CTRL P')\">Print</button>"
b"</div></div>"
b"<div class=sec><div class=st>SYSTEM</div><div class=g2>"
b"<button class=btn onclick=\"sh('ALT TAB')\">Alt+Tab</button>"
b"<button class='btn rc' onclick=\"sh('ALT F4')\">Alt+F4</button>"
b"<button class='btn rc' onclick=\"sh('CTRL ALT DELETE')\">CAD</button>"
b"<button class=btn onclick=\"sh('CTRL SHIFT ESC')\">TaskMgr</button>"
b"</div></div>"
b"<div class=sec><div class=st>MEDIA</div><div class=g4>"
b"<button class=btn onclick=\"sh('MEDIA_PREV')\">|&lt;</button>"
b"<button class=btn onclick=\"sh('MEDIA_PLAY')\">||</button>"
b"<button class=btn onclick=\"sh('MEDIA_NEXT')\">|&gt;</button>"
b"<button class=btn onclick=\"sh('MUTE')\">MUTE</button>"
b"<button class='btn gc' onclick=\"sh('VOL_UP')\">VOL+</button>"
b"<button class='btn rc' onclick=\"sh('VOL_DOWN')\">VOL-</button>"
b"</div></div></div>"
# DUCKY
b"<div id=p-dk class=pn>"
b"<div class=sec><div class=st>PRESETS</div><div class=g2>"
b"<div class=mc onclick=\"lm('hello')\"><div class=mn>HELLO</div><div class=md>Notepad</div></div>"
b"<div class=mc onclick=\"lm('sysinfo')\"><div class=mn>SYSINFO</div><div class=md>CMD info</div></div>"
b"<div class=mc onclick=\"lm('rick')\"><div class=mn>RICKROLL</div><div class=md>Browser</div></div>"
b"<div class=mc onclick=\"lm('snip')\"><div class=mn>SNIP</div><div class=md>Screenshot</div></div>"
b"<div class=mc onclick=\"lm('ip')\"><div class=mn>IPCONFIG</div><div class=md>Network</div></div>"
b"<div class=mc onclick=\"lm('lock')\"><div class=mn>LOCK</div><div class=md>Lock screen</div></div>"
b"</div></div>"
b"<div class=sec><div class=st>EDITOR</div>"
b"<textarea id=dk rows=7 placeholder='GUI R&#10;DELAY 800&#10;STRING hello&#10;ENTER'></textarea>"
b"<div class=row><button class='btn ac' onclick=runDk()>RUN</button>"
b"<button class=btn id=dclr>CLR</button></div></div></div>"
# CLIPS
b"<div id=p-cl class=pn>"
b"<div class=sec><div class=st>CLIPS - TAP TO TYPE</div>"
b"<div id=cl></div>"
b"<textarea id=nc rows=2 placeholder='New clip...'></textarea>"
b"<div class=row><button class='btn ac' onclick=addClip()>+ ADD</button>"
b"<button class='btn rc' onclick='clips=[];renderClips()'>CLEAR</button></div>"
b"</div></div>"
# WIFI
b"<div id=p-wf class=pn>"
b"<div class=sec><div class=st>STATUS</div><div class=wc>"
b"<div class=ir><span class=il>AP SSID</span><span class=iv>PicoHID</span></div>"
b"<div class=ir><span class=il>AP PASS</span><span class=iv>pico1234</span></div>"
b"<div class=ir><span class=il>AP IP</span><span class=iv id=apip>...</span></div>"
b"<div class=ir><span class=il>INTERNET</span><span id=sstat class=ivr>NO</span></div>"
b"<div class=ir><span class=il>STA IP</span><span class=iv id=stip>-</span></div>"
b"</div></div>"
b"<div class=sec><div class=st>LED</div><div class=g3>"
b"<button class='btn gc' onclick=\"fetch('/led?a=on')\">ON</button>"
b"<button class='btn rc' onclick=\"fetch('/led?a=off')\">OFF</button>"
b"<button class='btn ac' onclick=\"fetch('/led?a=blink')\">BLINK</button>"
b"</div></div>"
b"<div class=sec><div class=st>CONNECT</div><div class=wc>"
b"<div class=fi><label>SSID</label><input id=ws placeholder='WiFi name'></div>"
b"<div class=fi><label>PASSWORD</label><input id=wp type=password placeholder='password'></div>"
b"<div class=row><button class='btn ac' onclick=connWifi()>CONNECT</button>"
b"<button class='btn rc' onclick=discWifi()>DISCONNECT</button></div>"
b"</div></div></div>"
# TERMINAL
b"<div id=p-tm class=pn>"
b"<div class=sec><div class=st>LOG</div><div id=log></div>"
b"<div class=ti><span>$</span>"
b"<input id=ti placeholder='STRING hi | GUI R' autocomplete=off>"
b"<button class='btn ac' style='padding:6px 10px;white-space:nowrap' onclick=trun()>RUN</button>"
b"</div></div>"
b"<div class=sec><div class=st>QUICK</div><div class=g2>"
b"<button class=btn onclick=\"texec('GUI R')\">Run</button>"
b"<button class=btn onclick=\"texec('GUI L')\">Lock</button>"
b"<button class='btn rc' onclick=\"texec('CTRL ALT DELETE')\">CAD</button>"
b"<button class=btn id=lclr>Clear</button>"
b"</div></div></div>"
# SNAKE
b"<div id=p-sn class=pn style='text-align:center'>"
b"<canvas id=snk width=280 height=280></canvas>"
b"<div class=sd>"
b"<div></div><button class=btn onclick=\"sd('U')\">^</button><div></div>"
b"<button class=btn onclick=\"sd('L')\">&lt;</button>"
b"<button class='btn gc' id=sb onclick=st()>GO</button>"
b"<button class=btn onclick=\"sd('R')\">&gt;</button>"
b"<div></div><button class=btn onclick=\"sd('D')\">v</button><div></div>"
b"</div>"
b"<div style='margin-top:7px;font-size:.65rem;color:var(--m)'>"
b"SCORE <span id=sc style='color:var(--ac)'>0</span> "
b"HI <span id=hi style='color:var(--y)'>0</span></div>"
b"</div></main>"
b"<div id=toast></div>"
)

P_JS = (
b"<script>"
# nav
b"function go(id,el){"
b"document.querySelectorAll('.pn').forEach(p=>p.classList.remove('on'));"
b"document.querySelectorAll('.tb').forEach(t=>t.classList.remove('on'));"
b"document.getElementById('p-'+id).classList.add('on');el.classList.add('on')}"
# toast
b"let _tt;"
b"function toast(m,c){"
b"const t=document.getElementById('toast');"
b"t.textContent=m;t.style.color=c||'var(--ac)';t.style.borderColor=c||'var(--ac)';"
b"t.classList.add('on');clearTimeout(_tt);_tt=setTimeout(()=>t.classList.remove('on'),1600)}"
# pad - full gesture trackpad
b"const pad=document.getElementById('pad'),pgst=document.getElementById('pgst');"
b"let lx=0,ly=0,dn=false,vx=0,vy=0;"
b"let mt=false,mtTO=0;"                                  
b"let _tapT=0,_tapN=0,_tapMoved=false;"
b"let _scrlY=0,_scrl2=false,smt=false,smtTO=0;"
b"function gspd(){return+document.getElementById('spd').value}"
b"function gacc(){return+document.getElementById('acc').value}"
b"function accel(d,a){const sg=d<0?-1:1,ab=Math.abs(d);return sg*Math.pow(ab,1+(a-1)*0.3)}"
b"function clamp(v){return Math.max(-127,Math.min(127,Math.round(v)))}"
b"function mv(x,y){"
b"if(mt)return;"
b"mt=true;"
b"clearTimeout(mtTO);"
b"mtTO=setTimeout(function(){mt=false},400);"  # safety: always unlock after 400ms
b"fetch('/move?x='+x+'&y='+y)"
b".then(function(){mt=false;clearTimeout(mtTO);})"
b".catch(function(){mt=false;clearTimeout(mtTO);});}"
b"function scrl(d){"
b"if(smt)return;"
b"smt=true;"
b"clearTimeout(smtTO);"
b"smtTO=setTimeout(function(){smt=false},200);"
b"fetch('/scroll?d='+d)"
b".then(function(){smt=false;clearTimeout(smtTO);})"
b".catch(function(){smt=false;clearTimeout(smtTO);});}"
# touch
b"pad.addEventListener('touchstart',function(e){"
b"e.preventDefault();"
b"const tc=e.touches;"
b"if(tc.length===1){"
b"lx=tc[0].clientX;ly=tc[0].clientY;"
b"vx=0;vy=0;dn=true;_scrl2=false;_tapMoved=false;"
b"pad.classList.add('t');pgst.style.opacity='0';"
b"}else if(tc.length===2){"
b"dn=false;_scrl2=true;"
b"_scrlY=(tc[0].clientY+tc[1].clientY)/2;"
b"}},{passive:false});"
b"pad.addEventListener('touchmove',function(e){"
b"e.preventDefault();"
b"const tc=e.touches,spd=gspd(),acc=gacc();"
b"if(tc.length===1&&dn){"
b"const dx=tc[0].clientX-lx,dy=tc[0].clientY-ly;"
b"if(Math.abs(dx)>4||Math.abs(dy)>4)_tapMoved=true;"
b"vx=vx*0.2+accel(dx*spd,acc)*0.8;"
b"vy=vy*0.2+accel(dy*spd,acc)*0.8;"
b"lx=tc[0].clientX;ly=tc[0].clientY;"
b"mv(clamp(vx),clamp(vy));"
b"}else if(tc.length===2&&_scrl2){"
b"const ny=(tc[0].clientY+tc[1].clientY)/2,dy=_scrlY-ny;"
b"if(Math.abs(dy)>6){scrl(dy>0?4:-4);_scrlY=ny;}"
b"}},{passive:false});"
b"pad.addEventListener('touchend',function(e){"
b"e.preventDefault();"
b"const now=Date.now(),rc=e.touches.length,fc=e.changedTouches.length;"
b"if(rc===0){"
b"dn=false;_scrl2=false;pad.classList.remove('t');"
b"if(!_tapMoved){"
b"if(fc>=2){fetch('/mouse?dir=right');toast('RIGHT CLICK','var(--r)');_tapN=0;return;}"
b"const dt=now-_tapT;"
b"if(_tapN===1&&dt<380){"       # second tap arrived fast = double click
b"clearTimeout(_tapN_to);"
b"_tapN=0;"
b"fetch('/mouse?dir=left');"
b"setTimeout(function(){fetch('/mouse?dir=left');},80);"  # slight gap between clicks
b"toast('DBL CLICK');"
b"}else{"
b"_tapN=1;_tapT=now;"
b"_tapN_to=setTimeout(function(){"
b"if(_tapN===1){_tapN=0;fetch('/mouse?dir=left');toast('CLICK');}"
b"},370);"
b"}"
b"}"
b"}else if(rc===1&&_scrl2){"    # went from 2 fingers to 1, reset for move
b"_scrl2=false;"
b"lx=e.touches[0].clientX;ly=e.touches[0].clientY;"
b"vx=0;vy=0;dn=true;"
b"}},{passive:false});"
# desktop mouse fallback
b"pad.addEventListener('mousedown',function(e){"
b"e.preventDefault();"
b"lx=e.clientX;ly=e.clientY;dn=true;vx=0;vy=0;_tapMoved=false;_tapT=Date.now();"
b"pad.classList.add('t');pgst.style.opacity='0'});"
b"document.addEventListener('mousemove',function(e){"
b"if(!dn)return;"
b"const dx=e.clientX-lx,dy=e.clientY-ly,spd=gspd(),acc=gacc();"
b"if(Math.abs(dx)>4||Math.abs(dy)>4)_tapMoved=true;"
b"mv(clamp(accel(dx*spd,acc)),clamp(accel(dy*spd,acc)));"
b"lx=e.clientX;ly=e.clientY});"
b"document.addEventListener('mouseup',function(e){"
b"if(!dn)return;"
b"if(!_tapMoved){fetch('/mouse?dir=left');toast('CLICK');}"
b"dn=false;pad.classList.remove('t')});"
# click buttons - prevent event bubbling and use press/release properly
b"function btn_click(dir,el,col){"
b"el.style.borderColor=col;"
b"fetch('/mouse?dir='+dir);"
b"setTimeout(function(){el.style.borderColor='var(--br)'},180);}"
b"document.getElementById('tl').addEventListener('pointerdown',function(e){e.stopPropagation();btn_click('left',this,'var(--ac)')});"
b"document.getElementById('tm').addEventListener('pointerdown',function(e){e.stopPropagation();btn_click('middle',this,'var(--ac)')});"
b"document.getElementById('tr').addEventListener('pointerdown',function(e){e.stopPropagation();btn_click('right',this,'var(--r)')});"
b"let _tapN_to=0;"

# mouse
b"function mc(b){fetch('/mouse?dir='+b);toast(b.toUpperCase())}"
b"let _si;"
b"function ss(d){fetch('/scroll?d='+d);_si=setInterval(()=>fetch('/scroll?d='+d),110)}"
b"function sc(){clearInterval(_si)}"
# keyboard
b"function sendText(){const t=document.getElementById('kt').value;"
b"if(!t)return;fetch('/type?t='+encodeURIComponent(t));toast('TYPED '+t.length)}"
b"function sk(k){fetch('/key?k='+k);toast(k,'var(--t)')}"
b"function sh(s){fetch('/shortcut?s='+encodeURIComponent(s));toast(s)}"
# ducky
b"const MACROS={"
b"hello:'GUI R\\nDELAY 800\\nSTRING notepad\\nENTER\\nDELAY 1200\\nSTRING Hello from Pico HID!',"
b"sysinfo:'GUI R\\nDELAY 800\\nSTRING cmd\\nENTER\\nDELAY 1000\\nSTRING systeminfo\\nENTER',"
b"rick:'GUI R\\nDELAY 800\\nSTRING https://youtu.be/dQw4w9WgXcQ\\nENTER',"
b"snip:'GUI SHIFT S',"
b"ip:'GUI R\\nDELAY 800\\nSTRING cmd\\nENTER\\nDELAY 1000\\nSTRING ipconfig /all\\nENTER',"
b"lock:'GUI R\\nDELAY 800\\nSTRING cmd\\nENTER\\nDELAY 800\\nSTRING msg * Pico was here!\\nENTER\\nDELAY 800\\nGUI L'"
b"};"
b"function lm(n){document.getElementById('dk').value=MACROS[n]||'';toast('LOADED','var(--y)')}"
b"function runDk(){const s=document.getElementById('dk').value;"
b"if(!s)return;fetch('/duck?s='+encodeURIComponent(s));toast('RUNNING...')}"
# clips
b"let clips=[];"
b"function renderClips(){"
b"const l=document.getElementById('cl');l.innerHTML='';"
b"clips.forEach(function(c,i){"
b"const d=document.createElement('div');"
b"d.style.cssText='display:flex;gap:5px;margin-bottom:5px';"
b"const tx=document.createElement('div');"
b"tx.style.cssText='flex:1;background:var(--s2);border:1px solid var(--br);'"
b"+' border-radius:5px;padding:6px 8px;font-size:.65rem;cursor:pointer;'"
b"+' overflow:hidden;text-overflow:ellipsis;white-space:nowrap';"
b"tx.textContent=c.substring(0,50);"
b"tx.dataset.i=i;"
b"tx.onclick=function(){fetch('/type?t='+encodeURIComponent(clips[this.dataset.i]));toast('TYPED')};"
b"const rm=document.createElement('button');"
b"rm.className='btn rc';rm.style.cssText='padding:4px 8px;font-size:.65rem;flex-shrink:0';"
b"rm.textContent='X';rm.dataset.i=i;"
b"rm.onclick=function(){clips.splice(+this.dataset.i,1);renderClips()};"
b"d.appendChild(tx);d.appendChild(rm);l.appendChild(d)})}"
b"function addClip(){const t=document.getElementById('nc').value.trim();"
b"if(!t)return;clips.push(t);document.getElementById('nc').value='';"
b"renderClips();toast('ADDED','var(--g)')}"
b"renderClips();"
# wifi status
b"async function loadStat(){"
b"try{const r=await fetch('/status');const j=await r.json();"
b"document.getElementById('apip').textContent=j.ap_ip||'-';"
b"document.getElementById('stip').textContent=j.sta_ip||'-';"
b"document.getElementById('sip').textContent=j.sta_ip?(' '+j.sta_ip):'';"
b"const s=document.getElementById('sstat');"
b"if(j.sta_ok){s.textContent='YES';s.className='ivg';}else{s.textContent='NO';s.className='ivr';}}"
b"catch(e){}}"
b"loadStat();setInterval(loadStat,7000);"
b"async function connWifi(){"
b"const s=document.getElementById('ws').value.trim();"
b"const p=document.getElementById('wp').value;"
b"if(!s){toast('ENTER SSID','var(--r)');return;}"
b"toast('CONNECTING...','var(--y)');"
b"const r=await fetch('/wifi/connect?ssid='+encodeURIComponent(s)+'&pass='+encodeURIComponent(p));"
b"const j=await r.json();"
b"if(j.ok){toast('OK: '+j.ip,'var(--g)');loadStat();}else toast('FAIL: '+(j.msg||'?'),'var(--r)');}"
b"async function discWifi(){await fetch('/wifi/disconnect');toast('DISCONNECTED','var(--r)');loadStat()}"
# terminal
b"function tlog(m,c){const l=document.getElementById('log');"
b"const d=document.createElement('div');d.className=c;"
b"const n=new Date();"
b"d.textContent='['+n.getHours().toString().padStart(2,'0')+':'"
b"+n.getMinutes().toString().padStart(2,'0')+'] '+m;"
b"l.appendChild(d);l.scrollTop=l.scrollHeight}"
b"async function trun(){const v=document.getElementById('ti').value.trim();"
b"if(!v)return;tlog('> '+v,'linf');document.getElementById('ti').value='';"
b"const r=await fetch('/duck?s='+encodeURIComponent(v));tlog(await r.text(),'lok')}"
b"function texec(c){tlog('> '+c,'linf');fetch('/shortcut?s='+encodeURIComponent(c)).then(()=>tlog('OK','lok'))}"
b"document.getElementById('ti').addEventListener('keydown',e=>{if(e.key==='Enter')trun()});"
b"tlog('PICO HID ONLINE','lok');"
# snake
b"const cv=document.getElementById('snk'),cx=cv.getContext('2d');"
b"let sn=[],sd2='R',snd='R',sf={x:5,y:5},sg,sr=false,ssc=0,shi=0,sfc=0;"
b"const SB=9,SC=31;"
b"function st(){sr?snStop():snStart()}"
b"function snStart(){sn=[{x:15,y:15},{x:14,y:15},{x:13,y:15}];sd2='R';snd='R';ssc=0;sfc=0;"
b"plF();if(sg)clearInterval(sg);sg=setInterval(snStep,115);sr=true;"
b"document.getElementById('sb').textContent='STOP'}"
b"function snStop(){clearInterval(sg);sr=false;document.getElementById('sb').textContent='GO'}"
b"function plF(){sf.x=Math.floor(Math.random()*SC);sf.y=Math.floor(Math.random()*SC)}"
b"function sd(d){if((d==='L'&&sd2!=='R')||(d==='R'&&sd2!=='L')||"
b"(d==='U'&&sd2!=='D')||(d==='D'&&sd2!=='U'))snd=d}"
b"document.addEventListener('keydown',e=>{"
b"if(e.key==='ArrowUp')sd('U');if(e.key==='ArrowDown')sd('D');"
b"if(e.key==='ArrowLeft')sd('L');if(e.key==='ArrowRight')sd('R')});"
b"function snStep(){sfc++;sd2=snd;"
b"cx.fillStyle='#07090f';cx.fillRect(0,0,280,280);"
b"cx.fillStyle='rgba(0,240,255,.025)';"
b"for(let x=0;x<SC;x++)for(let y=0;y<SC;y++)cx.fillRect(x*SB+3,y*SB+3,2,2);"
b"cx.fillStyle='#ff2d78';cx.fillRect(sf.x*SB+1,sf.y*SB+1,SB-2,SB-2);"
b"sn.forEach((s,i)=>{"
b"const t=1-i/sn.length;"
b"cx.fillStyle=i===0?'#00f0ff':'rgba(0,'+(140+Math.floor(t*115))+',"
b"'+(180+Math.floor(t*75))+','+(0.35+t*.65)+')';"
b"cx.fillRect(s.x*SB+1,s.y*SB+1,SB-2,SB-2)});"
b"let h={x:sn[0].x,y:sn[0].y};"
b"if(sd2==='R')h.x++;if(sd2==='L')h.x--;if(sd2==='U')h.y--;if(sd2==='D')h.y++;"
b"sn.unshift(h);"
b"if(h.x===sf.x&&h.y===sf.y){ssc++;document.getElementById('sc').textContent=ssc;plF();}else sn.pop();"
b"if(h.x<0||h.x>=SC||h.y<0||h.y>=SC||sn.slice(1).some(s=>s.x===h.x&&s.y===h.y)){"
b"clearInterval(sg);sr=false;"
b"if(ssc>shi){shi=ssc;document.getElementById('hi').textContent=shi;}"
b"document.getElementById('sb').textContent='GO';"
b"cx.fillStyle='rgba(7,9,15,.82)';cx.fillRect(0,0,280,280);"
b"cx.font='bold 14px monospace';cx.fillStyle='#ff2d78';cx.textAlign='center';"
b"cx.fillText('GAME OVER',140,120);"
b"cx.font='11px monospace';cx.fillStyle='#00f0ff';"
b"cx.fillText('SCORE: '+ssc,140,140);"
b"if(ssc===shi&&ssc>0)cx.fillText('NEW HIGH!',140,158);"
b"cx.fillText('TAP GO TO RETRY',140,176);}}"
b"cx.fillStyle='#07090f';cx.fillRect(0,0,280,280);"
b"cx.font='10px monospace';cx.fillStyle='rgba(0,240,255,.15)';cx.textAlign='center';"
b"cx.fillText('TAP GO TO PLAY',140,142);"
b"document.getElementById('kclr').onclick=function(){document.getElementById('kt').value=''};"
b"document.getElementById('dclr').onclick=function(){document.getElementById('dk').value=''};"
b"document.getElementById('lclr').onclick=function(){document.getElementById('log').innerHTML=''};"
b"document.getElementById('clclr').onclick=function(){clips=[];renderClips()};"
b"</script>"
)

# Full main page assembled from parts (never one giant string)
def get_main_page():
    return (b"<!DOCTYPE html><html><head>"
            b"<meta charset=UTF-8>"
            b"<meta name=viewport content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no'>"
            b"<title>PicoHID</title>"
            + P_CSS
            + b"</head><body>"
            + P_BODY
            + P_JS
            + b"</body></html>")

# ── SHORTCUT MAP ─────────────────────────────────────────────────────
def _sc():
    if not keyboard_dev: return {}
    K = Keycode
    return {
        "GUI R":(K.GUI,K.R),"GUI D":(K.GUI,K.D),"GUI L":(K.GUI,K.L),
        "GUI E":(K.GUI,K.E),"GUI TAB":(K.GUI,K.TAB),
        "GUI SHIFT S":(K.GUI,K.SHIFT,K.S),
        "ALT TAB":(K.ALT,K.TAB),"ALT F4":(K.ALT,K.F4),
        "ALT LEFT":(K.ALT,K.LEFT_ARROW),"ALT RIGHT":(K.ALT,K.RIGHT_ARROW),
        "CTRL ALT DELETE":(K.CONTROL,K.ALT,K.DELETE),
        "CTRL SHIFT ESC":(K.CONTROL,K.SHIFT,K.ESCAPE),
        "CTRL C":(K.CONTROL,K.C),"CTRL V":(K.CONTROL,K.V),
        "CTRL Z":(K.CONTROL,K.Z),"CTRL Y":(K.CONTROL,K.Y),
        "CTRL X":(K.CONTROL,K.X),"CTRL A":(K.CONTROL,K.A),
        "CTRL S":(K.CONTROL,K.S),"CTRL F":(K.CONTROL,K.F),
        "CTRL P":(K.CONTROL,K.P),"CTRL W":(K.CONTROL,K.W),
        "CTRL T":(K.CONTROL,K.T),"CTRL R":(K.CONTROL,K.R),

    }
SC_MAP = _sc()
print("SC_MAP entries:", len(SC_MAP))

# ── REQUEST HANDLER ───────────────────────────────────────────────────

def handle(method, path, args, hdrs, body):
    global sta_ip, sta_ok

    # ── LOGIN ──
    if path == "/login":
        if method == "POST":
            params = {}
            for p in body.split("&"):
                if "=" in p:
                    k,v = p.split("=",1); params[udec(k)] = udec(v)
            if params.get("u") == LOGIN_USER and params.get("p") == LOGIN_PASS:
                tok = mktok(); sessions.add(tok)
                return resp("200 OK","application/json",'{"ok":true}',
                    extra="Set-Cookie: t={}; Path=/\r\n".format(tok))
            return resp("200 OK","application/json",'{"ok":false}')
        return resp("200 OK","text/html",P_LOGIN)

    if path == "/logout":
        tok = getcook(hdrs,"t")
        if tok: sessions.discard(tok)
        return redir("/login")

    if not authed(hdrs):
        return redir("/login")

    # ── MAIN ──
    if path in ("/",""):
        pg = get_main_page()
        return resp("200 OK","text/html",pg)

    if path == "/status":
        return json_resp({"ap_ip":ap_ip,"sta_ip":sta_ip,"sta_ok":sta_ok})

    if path == "/wifi/connect":
        ssid = args.get("ssid","").strip()
        pw   = args.get("pass","")
        if not ssid:
            return json_resp({"ok":False,"msg":"No SSID"})
        ok = sta_connect(ssid, pw)
        if ok:
            wifi_save(ssid, pw)
            return json_resp({"ok":True,"ip":sta_ip})
        return json_resp({"ok":False,"msg":"Failed - check password"})

    if path == "/wifi/disconnect":
        try: wifi.radio.connect("","")
        except: pass
        sta_ip = None; sta_ok = False
        return json_resp({"ok":True})

    if path == "/mouse":
        d = args.get("dir","")
        if mouse_dev:
            try:
                mouse_dev.release_all()          # ensure clean state
                if d=="left":
                    mouse_dev.press(Mouse.LEFT_BUTTON)
                    time.sleep(0.02)
                    mouse_dev.release(Mouse.LEFT_BUTTON)
                elif d=="right":
                    mouse_dev.press(Mouse.RIGHT_BUTTON)
                    time.sleep(0.02)
                    mouse_dev.release(Mouse.RIGHT_BUTTON)
                elif d=="middle":
                    mouse_dev.press(Mouse.MIDDLE_BUTTON)
                    time.sleep(0.04)
                    mouse_dev.release(Mouse.MIDDLE_BUTTON)
            except Exception as e:
                print("mouse err:", e)
                try: mouse_dev.release_all()
                except: pass
        return resp("200 OK","text/plain","OK")

    if path == "/move":
        if mouse_dev:
            try:
                x = max(-127, min(127, int(float(args.get("x", 0)))))
                y = max(-127, min(127, int(float(args.get("y", 0)))))
                mouse_dev.move(x, y)
            except Exception as e:
                print("move err:", e)
        return resp("200 OK","text/plain","OK")

    if path == "/scroll":
        if mouse_dev:
            try:
                d2 = max(-127, min(127, int(args.get("d", 0))))
                mouse_dev.move(wheel=d2)
            except Exception as e:
                print("scroll err:", e)
        return resp("200 OK","text/plain","OK")

    if path == "/type":
        txt = args.get("t","")
        if keyboard_dev:
            for c in txt:
                cl = c.lower()
                if cl in KM:
                    k,sh = KM[cl]
                    if c.isupper(): sh = 1
                    if sh: keyboard_dev.send(Keycode.SHIFT, k)
                    else:  keyboard_dev.send(k)
                    time.sleep(0.03)
            keyboard_dev.release_all()
        return resp("200 OK","text/plain","OK")

    if path == "/key":
        k = args.get("k","")
        if keyboard_dev:
            km = {"ENTER":Keycode.ENTER,"TAB":Keycode.TAB,"ESC":Keycode.ESCAPE,
                  "SPACE":Keycode.SPACE,"BACKSPACE":Keycode.BACKSPACE,"DELETE":Keycode.DELETE,
                  "HOME":Keycode.HOME,"END":Keycode.END,"PAGEUP":Keycode.PAGE_UP,
                  "PAGEDOWN":Keycode.PAGE_DOWN,"INSERT":Keycode.INSERT,
                  "UP":Keycode.UP_ARROW,"DOWN":Keycode.DOWN_ARROW,
                  "LEFT":Keycode.LEFT_ARROW,"RIGHT":Keycode.RIGHT_ARROW,
                  "F1":Keycode.F1,"F2":Keycode.F2,"F3":Keycode.F3,"F4":Keycode.F4,
                  "F5":Keycode.F5,"F6":Keycode.F6,"F7":Keycode.F7,"F8":Keycode.F8,
                  "F9":Keycode.F9,"F10":Keycode.F10,"F11":Keycode.F11,"F12":Keycode.F12,
                  "PRINTSCREEN":Keycode.PRINT_SCREEN}
            if k in km:
                keyboard_dev.send(km[k])
                keyboard_dev.release_all()
        return resp("200 OK","text/plain","OK")

    if path == "/shortcut":
        s = args.get("s","")
        CC = ConsumerControlCode
        MEDIA = {
            "VOL_UP":CC.VOLUME_INCREMENT,"VOL_DOWN":CC.VOLUME_DECREMENT,
            "MUTE":CC.MUTE,"MEDIA_PLAY":CC.PLAY_PAUSE,
            "MEDIA_NEXT":CC.SCAN_NEXT_TRACK,"MEDIA_PREV":CC.SCAN_PREVIOUS_TRACK,
        }
        if cc_dev and s in MEDIA:
            cc_dev.send(MEDIA[s])
        elif keyboard_dev and s in SC_MAP:
            keyboard_dev.send(*SC_MAP[s])
            keyboard_dev.release_all()
        return resp("200 OK","text/plain","OK")

    if path == "/duck":
        ducky(args.get("s",""))
        return resp("200 OK","text/plain","OK")

    if path == "/led":
        a = args.get("a","")
        if a == "on":    led_on()
        elif a == "off": led_off()
        elif a == "blink": led_blink(3)
        return resp("200 OK","text/plain","OK")

    return resp("404 Not Found","text/plain","404")

# ── SERVER ────────────────────────────────────────────────────────────
def run():
    pool = socketpool.SocketPool(wifi.radio)
    s = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    s.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(3)
    s.setblocking(True)
    print("Ready: http://{}/login".format(ap_ip))
    buf = bytearray(512)
    while True:
        conn = None
        try:
            conn, addr = s.accept()
            conn.settimeout(1.5)
            # recv request - read headers then body
            data = b""
            while True:
                try:
                    n = conn.recv_into(buf)
                    if n == 0: break
                    data += bytes(buf[:n])
                    # Check if we have full headers
                    hi = data.find(b"\r\n\r\n")
                    if hi < 0: hi = data.find(b"\n\n")
                    if hi >= 0:
                        # For POST read Content-Length more bytes
                        hpart = data[:hi].decode("utf-8","ignore")
                        clen = 0
                        for ln in hpart.split("\n"):
                            if ln.lower().startswith("content-length:"):
                                try: clen = int(ln.split(":",1)[1].strip())
                                except: pass
                        sep_len = 4 if b"\r\n\r\n" in data else 2
                        body_so_far = len(data) - hi - sep_len
                        if body_so_far >= clen:
                            break
                except OSError: break
            if not data:
                continue
            method, path, args, hdrs, body = parse_req(data)
            hdr, bdy = handle(method, path, args, hdrs, body)
            # send header
            conn.sendall(hdr)
            # send body in 512-byte chunks
            total = len(bdy)
            off = 0
            mv = memoryview(bdy)
            while off < total:
                chunk = min(256, total - off)
                sent = conn.send(mv[off : off+chunk])
                if sent <= 0: break
                off += sent
        except Exception as e:
            print("err:", e)
        finally:
            if conn:
                try: conn.close()
                except: pass
            led.value = not led.value  # toggle on each request (non-blocking)

run()