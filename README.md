# ⚡ PyDesk - Remote Desktop Software (AnyDesk Alternative)

Python மற்றும் CustomTkinter மூலம் உருவாக்கப்பட்ட AnyDesk போன்ற அதிவேக Remote Desktop மென்பொருள்.

---

## 📁 உருவாக்கப்பட்ட `.exe` கோப்புகள் (Ready to Use)

உங்களின் அனைத்து கோப்புகளும் `D:\anydesk\dist\` கோப்புறையில் உள்ளன:

1. **`PyDesk.exe`** (Client Application):
   - AnyDesk போன்ற நவீன மற்றும் எளிய UI.
   - இரட்டைப் பயன்முறை: **Host** (திரையைப் பகிர்பவர்) மற்றும் **Remote Viewer** (மற்றொரு கணினியைக் கட்டுப்படுத்துபவர்).
   - தனித்துவமான 9-Digit ID (எ.கா: `481 920 183`) மற்றும் பாதுகாப்பு கடவுச்சொல்.
   - மவுஸ் கிளிக், ஸ்க்ரோல் மற்றும் கீபோர்டு உள்ளீடுகளை Real-time-ல் அனுப்பும் வசதி.

2. **`PyDeskServer.exe`** (Relay / Signaling Server):
   - இணையத்தில் எங்கிருந்தாலும் (Anywhere over the Internet) இரண்டு கணினிகளை இணைக்கும் பிரத்யேக Relay Server.
   - எந்தவொரு VPS, கிளவுட் சர்வர் அல்லது உங்கள் PC-யில் இயக்கி வைக்கலாம்.

---

## 🚀 பயன்படுத்துவது எப்படி? (How to Use)

### முறை 1: Internet வழியாக இணைக்க (Anywhere in the World)
1. உங்கள் Server-ல் அல்லது PC-ல் `PyDeskServer.exe`-ஐ இயக்கவும்.
2. இரு கணினிகளிலும் `PyDesk.exe`-ஐ திறக்கவும்.
3. கீழே உள்ள **"Change Server"** பட்டனை கிளிக் செய்து உங்கள் Relay Server IP / Domain-ஐ உள்ளிடவும்.
4. **Host PC**-ல் தோன்றும் 9-இலக்க ID-ஐ எடுத்து, **Client PC**-ல் உள்ள "Remote Desk" பெட்டியில் தட்டச்சு செய்து **"Connect"** கொடுக்கவும்.
5. Host PC-ல் தோன்றும் அனுமதி பாப்-அப்பில் **"Accept"** கொடுத்ததும் உடனடியாக திரை தெரியும்!

### முறை 2: ஒரே Wi-Fi / LAN நெட்வொர்க்கில் இணைக்க
- இரு கணினிகளிலும் `PyDesk.exe`-ஐ திறக்கவும்.
- Host PC-ல் காட்டப்படும் **Direct LAN IP**-ஐ (எ.கா: `192.168.1.5:8766`) Client PC-ல் உள்ளிட்டு நேரடியாக இணைத்துக் கொள்ளலாம்.

### முறை 3: உங்கள் PC-யையே Server-ஆக மாற்ற
- `PyDesk.exe`-ன் கீழ் வலதுபுறத்தில் உள்ள **"Host Local Relay"** பட்டனை கிளிக் செய்தால், கூடுதல் சர்வர் எதுவுமின்றி உங்கள் PC-யே Server-ஆக மாறிவிடும்.

---

## 🛠️ தொழில்நுட்ப விவரங்கள் (Architecture)
- **GUI**: CustomTkinter (Dark Modern Theme)
- **Screen Capture**: `mss` (Ultra-fast 30 FPS capturing)
- **Image Compression**: `Pillow` (Optimized JPEG frame streaming)
- **Input Control**: `pynput` (Mouse position normalization & keystrokes)
- **Networking**: Raw TCP packet framing protocol with big-endian length prefix.
