from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

ADMIN_PASSWORD = "0902"
ROOM_PASSWORD = "6969"

MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")
BANS_FILE = os.path.join(BASE_DIR, "bans.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PFP_FOLDER = os.path.join(BASE_DIR, "pfps")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PFP_FOLDER, exist_ok=True)

online_users = {}
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGES

def load_json(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def get_user():
    return request.headers.get("X-User", request.form.get("user", "Unknown"))

def get_device_id():
    return request.headers.get("X-Device-ID", request.form.get("device_id", ""))

def check_access():
    room = request.headers.get("X-Room-Password", request.form.get("room_password", ""))
    if room != ROOM_PASSWORD:
        return False

    bans = load_json(BANS_FILE, [])
    if get_user() in bans or get_device_id() in bans:
        return False

    online_users[get_user()] = time.time()
    return True

html = """
<!DOCTYPE html>
<html>
<head>
<title>Pi Chat</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { box-sizing:border-box; }

body {
    margin:0;
    font-family:Arial, sans-serif;
    background:#111;
    color:white;
    overflow:hidden;
}

header {
    position:fixed;
    top:0;
    left:0;
    right:0;
    z-index:10;
    background:#222;
    padding:8px;
    display:flex;
    gap:6px;
    align-items:center;
    overflow-x:auto;
    white-space:nowrap;
    border-bottom:1px solid #333;
}

button {
    border:0;
    border-radius:12px;
    padding:9px 11px;
    background:#007aff;
    color:white;
    font-size:14px;
}

.red { background:#ff3b30; }

#users {
    font-size:13px;
    opacity:.85;
    flex:0 0 auto;
}

#chat {
    position:fixed;
    top:58px;
    bottom:76px;
    left:0;
    right:0;
    overflow-y:auto;
    padding:12px;
}

.msg-wrap {
    display:flex;
    gap:8px;
    margin:10px 0;
    align-items:flex-end;
}

.msg-wrap.me {
    justify-content:flex-end;
}

.msg {
    background:#333;
    padding:10px 13px;
    border-radius:18px;
    max-width:78%;
    word-wrap:break-word;
}

.msg-wrap.me .msg {
    background:#007aff;
}

.name {
    font-size:12px;
    opacity:.75;
    margin-bottom:3px;
}

.time {
    font-size:10px;
    opacity:.6;
    margin-top:4px;
}

.chatimg {
    max-width:220px;
    max-height:260px;
    border-radius:12px;
    margin-top:8px;
    display:block;
}

.pfp {
    width:34px;
    height:34px;
    border-radius:50%;
    object-fit:cover;
    background:#555;
    flex:0 0 auto;
}

form {
    position:fixed;
    bottom:0;
    left:0;
    right:0;
    background:#222;
    display:flex;
    gap:6px;
    padding:8px;
    border-top:1px solid #333;
}

#message {
    flex:1;
    min-width:0;
    padding:11px;
    border-radius:14px;
    border:0;
    font-size:16px;
}

#image {
    max-width:92px;
    color:white;
    font-size:11px;
}

@media (max-width:600px) {
    button {
        font-size:12px;
        padding:8px 9px;
    }

    #chat {
        top:54px;
        bottom:73px;
    }

    .msg {
        max-width:82%;
    }

    .chatimg {
        max-width:190px;
    }

    #image {
        max-width:76px;
    }
}
</style>
</head>
<body>

<header>
    <b>Pi Chat</b>
    <span id="users">Online:</span>
    <button onclick="changeName()">Name</button>
    <button onclick="pickProfilePhoto()">PFP</button>
    <button class="red" onclick="clearChat()">Clear</button>
    <button class="red" onclick="banUser()">Ban</button>
    <button onclick="unbanUser()">Unban</button>
    <button onclick="viewBans()">Bans</button>
</header>

<div id="chat"></div>

<form onsubmit="sendMessage(event)">
    <input id="message" placeholder="Message" autocomplete="off">
    <input id="image" type="file" accept="image/*">
    <button>Send</button>
</form>

<input id="pfpInput" type="file" accept="image/*" style="display:none" onchange="uploadProfilePhoto(this.files[0])">

<script>
let username = localStorage.getItem("username");
let roomPassword = localStorage.getItem("roomPassword");
let deviceId = localStorage.getItem("deviceId");
let profilePhoto = localStorage.getItem("profilePhoto") || "";
let firstLoad = true;

if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem("deviceId", deviceId);
}

if (!username) {
    username = prompt("Enter your name:");
    localStorage.setItem("username", username);
}

if (!roomPassword) {
    roomPassword = prompt("Room password:");
    localStorage.setItem("roomPassword", roomPassword);
}

function makeHeaders(extra={}) {
    return {
        "X-User": username,
        "X-Room-Password": roomPassword,
        "X-Device-ID": deviceId,
        ...extra
    };
}

function isNearBottom() {
    const chat = document.getElementById("chat");
    return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 90;
}

async function api(url, options={}) {
    options.headers = makeHeaders(options.headers || {});
    return fetch(url, options);
}

async function loadMessages(forceScroll=false) {
    const chat = document.getElementById("chat");
    const shouldScroll = firstLoad || forceScroll || isNearBottom();

    const res = await api("/messages");

    if (res.status === 403) {
        alert("Wrong room password or banned.");
        localStorage.removeItem("roomPassword");
        location.reload();
        return;
    }

    const data = await res.json();

    document.getElementById("users").innerText =
        "Online: " + data.online.join(", ");

    chat.innerHTML = "";

    data.messages.forEach(m => {
        const wrap = document.createElement("div");
        wrap.className = "msg-wrap " + (m.device_id === deviceId ? "me" : "");

        const avatar = m.pfp
            ? `<img class="pfp" src="${m.pfp}">`
            : `<div class="pfp"></div>`;

        const bubble = `
            <div class="msg">
                <div class="name">${escapeHtml(m.user)}</div>
                <div>${escapeHtml(m.text || "")}</div>
                ${m.image ? `<img class="chatimg" src="${m.image}">` : ""}
                <div class="time">${m.time}</div>
            </div>
        `;

        wrap.innerHTML = m.device_id === deviceId ? bubble + avatar : avatar + bubble;
        chat.appendChild(wrap);
    });

    if (shouldScroll) {
        chat.scrollTop = chat.scrollHeight;
    }

    firstLoad = false;
}

async function sendMessage(e) {
    e.preventDefault();

    const text = document.getElementById("message").value.trim();
    const image = document.getElementById("image").files[0];

    if (!text && !image) return;

    let form = new FormData();
    form.append("user", username);
    form.append("device_id", deviceId);
    form.append("room_password", roomPassword);
    form.append("pfp", profilePhoto);
    form.append("text", text);

    if (image) form.append("image", image);

    const res = await fetch("/send", {
        method:"POST",
        body:form
    });

    if (!res.ok) {
        alert("Message failed to send.");
        return;
    }

    document.getElementById("message").value = "";
    document.getElementById("image").value = "";

    await loadMessages(true);
}

function changeName() {
    const newName = prompt("New name:");
    if (!newName) return;

    username = newName.trim();
    localStorage.setItem("username", username);
    loadMessages();
}

function pickProfilePhoto() {
    document.getElementById("pfpInput").click();
}

async function uploadProfilePhoto(file) {
    if (!file) return;

    let form = new FormData();
    form.append("user", username);
    form.append("device_id", deviceId);
    form.append("room_password", roomPassword);
    form.append("pfp", file);

    const res = await fetch("/upload_pfp", {
        method:"POST",
        body:form
    });

    if (!res.ok) {
        alert("Profile photo failed.");
        return;
    }

    const data = await res.json();
    profilePhoto = data.url;
    localStorage.setItem("profilePhoto", profilePhoto);

    alert("Profile photo saved.");
    loadMessages();
}

async function clearChat() {
    const password = prompt("Admin password:");
    if (!password) return;

    await api("/admin/clear", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({admin: password})
    });

    await loadMessages(true);
}

async function banUser() {
    const password = prompt("Admin password:");
    if (!password) return;

    const target = prompt("Username or device ID to ban:");
    if (!target) return;

    await api("/admin/ban", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({admin: password, target: target})
    });

    alert("Ban sent.");
}

async function unbanUser() {
    const password = prompt("Admin password:");
    if (!password) return;

    const target = prompt("Username or device ID to unban:");
    if (!target) return;

    await api("/admin/unban", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({admin: password, target: target})
    });

    alert("Unban sent.");
}

async function viewBans() {
    const password = prompt("Admin password:");
    if (!password) return;

    const res = await api("/admin/list_bans", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({admin: password})
    });

    const data = await res.json();

    alert(data.bans.length ? data.bans.join("\\n") : "No bans.");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
}

setInterval(loadMessages, 1500);
loadMessages(true);
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(html)

@app.route("/messages")
def messages():
    if not check_access():
        return jsonify({"error": "denied"}), 403

    now = time.time()
    active = [name for name, last in online_users.items() if now - last < 12]

    return jsonify({
        "messages": load_json(MESSAGES_FILE, []),
        "online": active
    })

@app.route("/send", methods=["POST"])
def send():
    if not check_access():
        return jsonify({"error": "denied"}), 403

    messages = load_json(MESSAGES_FILE, [])

    user = request.form.get("user", "Unknown")
    device_id = request.form.get("device_id", "")
    text = request.form.get("text", "")
    pfp = request.form.get("pfp", "")
    image_url = ""

    if "image" in request.files:
        img = request.files["image"]

        if img.filename and allowed_file(img.filename):
            filename = str(int(time.time())) + "_" + secure_filename(img.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            img.save(path)
            image_url = "/uploads/" + filename

    messages.append({
        "user": user,
        "device_id": device_id,
        "pfp": pfp,
        "text": text,
        "image": image_url,
        "time": datetime.now().strftime("%m/%d %I:%M %p")
    })

    messages = messages[-500:]
    save_json(MESSAGES_FILE, messages)

    return jsonify({"status": "sent"})

@app.route("/upload_pfp", methods=["POST"])
def upload_pfp():
    if not check_access():
        return jsonify({"error": "denied"}), 403

    if "pfp" not in request.files:
        return jsonify({"error": "no file"}), 400

    img = request.files["pfp"]

    if not img.filename or not allowed_file(img.filename):
        return jsonify({"error": "bad file"}), 400

    device_id = secure_filename(request.form.get("device_id", str(int(time.time()))))
    ext = img.filename.rsplit(".", 1)[1].lower()
    filename = device_id + "." + ext
    path = os.path.join(PFP_FOLDER, filename)
    img.save(path)

    return jsonify({"url": "/pfps/" + filename})

@app.route("/uploads/<filename>")
def uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/pfps/<filename>")
def pfps(filename):
    return send_from_directory(PFP_FOLDER, filename)

@app.route("/admin/clear", methods=["POST"])
def clear():
    data = request.json

    if data.get("admin") != ADMIN_PASSWORD:
        return jsonify({"error": "wrong admin password"}), 403

    save_json(MESSAGES_FILE, [])
    return jsonify({"status": "cleared"})

@app.route("/admin/ban", methods=["POST"])
def ban():
    data = request.json

    if data.get("admin") != ADMIN_PASSWORD:
        return jsonify({"error": "wrong admin password"}), 403

    bans = load_json(BANS_FILE, [])
    target = data.get("target")

    if target and target not in bans:
        bans.append(target)

    save_json(BANS_FILE, bans)
    return jsonify({"status": "banned"})

@app.route("/admin/unban", methods=["POST"])
def unban():
    data = request.json

    if data.get("admin") != ADMIN_PASSWORD:
        return jsonify({"error": "wrong admin password"}), 403

    bans = load_json(BANS_FILE, [])
    target = data.get("target")

    if target in bans:
        bans.remove(target)

    save_json(BANS_FILE, bans)
    return jsonify({"status": "unbanned"})

@app.route("/admin/list_bans", methods=["POST"])
def list_bans():
    data = request.json

    if data.get("admin") != ADMIN_PASSWORD:
        return jsonify({"error": "wrong admin password"}), 403

    return jsonify({"bans": load_json(BANS_FILE, [])})

app.run(host="0.0.0.0", port=5000)
