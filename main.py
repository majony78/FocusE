import os
import sys
import threading
import webbrowser
import keyboard
import time
import sqlite3
import subprocess
import ctypes
import customtkinter as ctk
from datetime import datetime
from flask import Flask, render_template_string, send_from_directory, request, jsonify
from flask_socketio import SocketIO
from PIL import Image, ImageGrab
import google.generativeai as genai

# --- [1. CONFIGURACIÓN DE RUTAS] ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

CAPTURES_DIR = os.path.join(BASE_DIR, "capturas")
if not os.path.exists(CAPTURES_DIR): os.makedirs(CAPTURES_DIR)
DB_PATH = os.path.join(BASE_DIR, 'focus_e.db')

MODEL_NAME = 'gemini-3.1-flash-lite-preview'

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

capturing_lock = False

# --- [2. BASE DE DATOS Y GESTIÓN DE API KEY] ---
def get_db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_conn()
    # Tabla de capturas
    conn.execute('''CREATE TABLE IF NOT EXISTS screenshots 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     path TEXT, time TEXT, summary TEXT, details TEXT, text_content TEXT)''')
    # Tabla de configuración (NUEVA)
    conn.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def get_api_key():
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='api_key'")
    row = cur.fetchone(); conn.close()
    return row[0] if row else ""

def save_api_key(key_val):
    conn = get_db_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('api_key', ?)", (key_val,))
    conn.commit(); conn.close()

# --- [3. LÓGICA DE CENTRADO] ---
def center_window(window, width, height):
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = (sw // 2) - (width // 2)
    y = (sh // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

# --- [4. PLANTILLA HTML - INTACTA] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>FocusE — Session {{ captureId }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif; background: #ffffff; height: 100vh; overflow: hidden; }
        .app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        .image-area { flex: 1; background: #f5f5f5; overflow: auto; display: flex; justify-content: center; align-items: flex-start; min-height: 0; }
        .capture-image { max-width: 100%; height: auto; display: block; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .chat-area { background: #ffffff; border-top: 1px solid #e5e7eb; display: flex; flex-direction: column; height: 320px; min-height: 150px; max-height: 80vh; overflow: hidden; box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05); position: relative; }
        .resize-handle { position: absolute; top: -8px; left: 0; right: 0; height: 16px; cursor: ns-resize; background: transparent; z-index: 100; }
        .resize-handle:hover { background: rgba(79, 70, 229, 0.2); }
        .resize-handle::after { content: '↕️'; position: absolute; top: -2px; left: 50%; transform: translateX(-50%); font-size: 10px; color: #9ca3af; background: rgba(255,255,255,0.95); padding: 2px 8px; border-radius: 12px; pointer-events: none; white-space: nowrap; transition: opacity 0.2s; }
        .chat-header { display: flex; justify-content: center; align-items: center; padding: 8px 16px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; flex-shrink: 0; }
        .brand { display: flex; align-items: center; gap: 8px; }
        .logo { width: 28px; height: 28px; background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(79, 70, 229, 0.3); position: relative; overflow: hidden; }
        .logo svg { width: 18px; height: 18px; }
        .app-name { font-size: 16px; font-weight: 700; background: linear-gradient(135deg, #1f2937 0%, #4f46e5 100%); background-clip: text; -webkit-background-clip: text; color: transparent; }
        .badge { background: #e0e7ff; padding: 2px 8px; border-radius: 20px; font-size: 9px; color: #4f46e5; font-weight: 600; margin-left: 10px; }
        .messages { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; background: #ffffff; }
        .message { display: flex; gap: 10px; animation: fadeIn 0.3s ease; width: 100%; }
        .message.user { justify-content: flex-end; }
        .avatar { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
        .message.user .avatar { background: #4f46e5; order: 1; }
        .message.bot .avatar { background: #f3f4f6; }
        .content { max-width: 85%; padding: 8px 14px; border-radius: 18px; font-size: 13px; line-height: 1.45; word-wrap: break-word; user-select: text; }
        .message.user .content { background: #4f46e5; color: white; border-bottom-right-radius: 4px; }
        .message.bot .content { background: #f3f4f6; color: #1f2937; border-bottom-left-radius: 4px; }
        .content pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 12px; margin: 8px 0; white-space: pre-wrap; }
        .content code { background: #1e1e1e; color: #d4d4d4; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
        .input-area { padding: 10px 16px 14px 16px; border-top: 1px solid #e5e7eb; background: #ffffff; }
        .input-wrapper { display: flex; gap: 10px; background: #f9fafb; border-radius: 32px; padding: 3px 3px 3px 18px; border: 1px solid #e5e7eb; }
        .question-input { flex: 1; background: transparent; border: none; padding: 10px 0; color: #1f2937; font-size: 13px; outline: none; }
        .send-btn { background: #4f46e5; border: none; padding: 6px 18px; border-radius: 28px; color: white; font-weight: 500; font-size: 12px; cursor: pointer; }
        .typing-cursor { display: inline-block; width: 2px; height: 14px; background-color: #4f46e5; margin-left: 2px; animation: blink 1s infinite; vertical-align: middle; }
        @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="app">
        <div class="image-area"><img id="mainImage" src="{{ imagePath }}" class="capture-image"></div>
        <div class="chat-area" id="chatArea">
            <div class="resize-handle" id="resizeHandle"></div>
            <div class="chat-header">
                <div class="brand">
                    <div class="logo">
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <circle cx="12" cy="12" r="9" stroke="white" stroke-width="1.5" fill="none"/>
                            <line x1="12" y1="4" x2="12" y2="7" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
                            <line x1="12" y1="17" x2="12" y2="20" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
                            <line x1="4" y1="12" x2="7" y2="12" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
                            <line x1="17" y1="12" x2="20" y2="12" stroke="white" stroke-width="1.2" stroke-linecap="round"/>
                            <circle cx="12" cy="12" r="2.5" fill="white" stroke="white" stroke-width="1"/>
                            <circle cx="12" cy="11" r="0.8" fill="#4f46e5"/>
                        </svg>
                    </div>
                    <div class="app-name">FOCUSE <small>· session {{ captureId }}</small></div>
                    <div class="badge">Gemini 3 Flash</div>
                </div>
            </div>
            <div id="messages" class="messages"><div class="message bot"><div class="avatar">🤖</div><div class="content">¡Hola! 👋 Pregúntame lo que quieras sobre esta captura.</div></div></div>
            <div class="input-area"><div class="input-wrapper">
                <input type="text" id="questionInput" class="question-input" placeholder="Escribe tu pregunta aquí..." autocomplete="off">
                <button class="send-btn" onclick="sendQuestion()">Enviar →</button>
            </div></div>
        </div>
    </div>
    <script>
        let captureId = {{ captureId }};
        const messagesContainer = document.getElementById('messages'), inputField = document.getElementById('questionInput'), chatArea = document.getElementById('chatArea'), resizeHandle = document.getElementById('resizeHandle');

        let isResizing = false, startY = 0, startHeight = 0;
        resizeHandle.addEventListener('mousedown', (e) => {
            e.preventDefault(); isResizing = true; startY = e.clientY; startHeight = chatArea.offsetHeight;
            document.body.style.cursor = 'ns-resize';
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', stopResize);
        });
        function handleMouseMove(e) {
            if (!isResizing) return;
            const deltaY = startY - e.clientY;
            chatArea.style.height = Math.min(window.innerHeight * 0.8, Math.max(150, startHeight + deltaY)) + 'px';
        }
        function stopResize() {
            isResizing = false; document.body.style.cursor = '';
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', stopResize);
            localStorage.setItem('focusE_chatHeight', chatArea.offsetHeight);
        }

        function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
        function markdownToHtml(text) {
            if (!text) return '';
            let html = text;
            const codeBlocks = [];
            html = html.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (match, lang, code) => {
                const index = codeBlocks.length;
                codeBlocks.push(`<pre><code class="language-${lang || 'code'}">${escapeHtml(code.trim())}</code></pre>`);
                return `___CODE_BLOCK_${index}___`;
            });
            html = html.replace(/`([^`]+)`/g, (match, code) => {
                const index = codeBlocks.length;
                codeBlocks.push(`<code>${escapeHtml(code)}</code>`);
                return `___CODE_BLOCK_${index}___`;
            });
            html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            html = html.replace(/\\n/g, '<br>');
            for (let i = 0; i < codeBlocks.length; i++) html = html.replace(`___CODE_BLOCK_${i}___`, codeBlocks[i]);
            return html;
        }

        function sendQuestion() {
            const q = inputField.value.trim(); if (!q || !captureId) return;
            addMsg(q, 'user'); inputField.value = '';
            fetch(`/ui/ask/${captureId}?question=${encodeURIComponent(q)}`, {method:'POST'})
            .then(res => res.json()).then(data => { if(data.success) addMsgWithTyping(data.answer, 'bot'); });
        }
        function addMsg(text, type) {
            const div = document.createElement('div'); div.className = `message ${type}`;
            div.innerHTML = `<div class="avatar">${type === 'user' ? '👤' : '🤖'}</div><div class="content">${type === 'bot' ? markdownToHtml(text) : escapeHtml(text)}</div>`;
            messagesContainer.appendChild(div); messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        function addMsgWithTyping(text, type) {
            const div = document.createElement('div'); div.className = `message ${type}`;
            div.innerHTML = `<div class="avatar">🤖</div><div class="content"></div>`;
            messagesContainer.appendChild(div);
            const contentDiv = div.querySelector('.content');
            let index = 0, currentText = '';
            function typeNext() {
                if (index < text.length) {
                    currentText += text[index];
                    contentDiv.innerHTML = markdownToHtml(currentText) + '<span class="typing-cursor"></span>';
                    index++; messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    setTimeout(typeNext, 10);
                } else contentDiv.innerHTML = markdownToHtml(text);
            }
            typeNext();
        }
        inputField.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendQuestion(); });
        const savedHeight = localStorage.getItem('focusE_chatHeight');
        if (savedHeight) chatArea.style.height = savedHeight + 'px';
    </script>
</body>
</html>
"""

# --- [5. VENTANAS DE CONFIGURACIÓN Y NOTIFICACIÓN] ---
def prompt_for_api_key(is_first_time=False):
    dialog = ctk.CTk()
    dialog.title("FocusE - API Key")
    dialog.attributes("-topmost", True)
    dialog.configure(fg_color="#1a1c2e")
    center_window(dialog, 480, 280)
    
    f = ctk.CTkFrame(dialog, fg_color="#242742", corner_radius=15, border_width=2, border_color="#4f46e5")
    f.pack(fill="both", expand=True, padx=10, pady=10)
    
    ctk.CTkLabel(f, text="🔑 API Key de Gemini", font=("Segoe UI", 22, "bold"), text_color="#ffffff").pack(pady=(20, 5))
    
    if is_first_time:
        ctk.CTkLabel(f, text="¡Bienvenido! Pega tu clave de Google para poder empezar.", font=("Segoe UI", 13), text_color="#a5b4fc").pack(pady=(0, 15))
    else:
        ctk.CTkLabel(f, text="Actualiza o modifica tu clave de Google Gemini.", font=("Segoe UI", 13), text_color="#a5b4fc").pack(pady=(0, 15))
    
    entry = ctk.CTkEntry(f, width=380, font=("Segoe UI", 13), placeholder_text="AIzaSy...")
    current = get_api_key()
    if current:
        entry.insert(0, current)
    entry.pack(pady=10)
    
    def save():
        k = entry.get().strip()
        if k:
            save_api_key(k)
            dialog.destroy()
            if is_first_time:
                show_startup_notif() # Abre el menú principal tras configurar la primera vez
                
    ctk.CTkButton(f, text="GUARDAR CLAVE", font=("Segoe UI", 14, "bold"), fg_color="#4f46e5", hover_color="#4338ca", height=45, command=save).pack(pady=(15, 20), padx=50, fill="x")
    dialog.mainloop()

def show_startup_notif():
    n = ctk.CTk()
    n.overrideredirect(True)
    n.attributes("-topmost", True)
    n.configure(fg_color="#1a1c2e")
    center_window(n, 450, 430)
    
    f = ctk.CTkFrame(n, fg_color="#242742", corner_radius=15, border_width=2, border_color="#4f46e5")
    f.pack(fill="both", expand=True, padx=10, pady=10)
    
    ctk.CTkLabel(f, text="🎯", font=("Segoe UI", 60)).pack(pady=(20, 0))
    ctk.CTkLabel(f, text="FocusE Pro", font=("Segoe UI", 30, "bold"), text_color="#ffffff").pack()
    
    s_f = ctk.CTkFrame(f, fg_color="transparent")
    s_f.pack(pady=20, padx=30, fill="x")

    def add_shortcut(title, keys):
        row = ctk.CTkFrame(s_f, fg_color="#333752", corner_radius=10)
        row.pack(pady=6, fill="x")
        ctk.CTkLabel(row, text=title, font=("Segoe UI", 15), text_color="#a5b4fc").pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(row, text=keys, font=("Segoe UI", 15, "bold"), text_color="#ffffff").pack(side="right", padx=20, pady=10)

    add_shortcut("Nueva Captura", "CTRL + ALT + S")
    add_shortcut("Cerrar Programa", "CTRL + ALT + Q")

    def open_settings():
        n.destroy()
        prompt_for_api_key(is_first_time=False)

    ctk.CTkButton(f, text="COMENZAR", font=("Segoe UI", 16, "bold"), fg_color="#4f46e5", hover_color="#4338ca", height=50, corner_radius=12, command=n.destroy).pack(pady=(5, 5), padx=60, fill="x")
    
    # NUEVO BOTÓN: Para cambiar la clave
    ctk.CTkButton(f, text="⚙️ Configurar API Key", font=("Segoe UI", 12), fg_color="transparent", text_color="#a5b4fc", hover_color="#333752", command=open_settings).pack(pady=(5, 10))
    
    n.after(8000, lambda: n.destroy() if n.winfo_exists() else None)
    n.mainloop()

def confirm_exit():
    q = ctk.CTk(); q.attributes("-topmost", True); q.configure(fg_color="#1a1c2e")
    center_window(q, 400, 220)
    f = ctk.CTkFrame(q, fg_color="#242742", corner_radius=15, border_width=2, border_color="#ef4444"); f.pack(fill="both", expand=True, padx=10, pady=10)
    ctk.CTkLabel(f, text="¿Quieres cerrar FocusE?", font=("Segoe UI", 20, "bold"), text_color="#ffffff").pack(pady=(30, 25))
    b_f = ctk.CTkFrame(f, fg_color="transparent"); b_f.pack(fill="x", padx=30)
    ctk.CTkButton(b_f, text="SALIR", fg_color="#ef4444", hover_color="#b91c1c", font=("Segoe UI", 14, "bold"), width=140, height=45, command=lambda: os._exit(0)).pack(side="left", expand=True, padx=10)
    ctk.CTkButton(b_f, text="VOLVER", fg_color="#4b5563", hover_color="#374151", font=("Segoe UI", 14, "bold"), width=140, height=45, command=q.destroy).pack(side="right", expand=True, padx=10)
    q.mainloop()

# --- [6. SERVICIOS Y CONTROLADORES] ---
def optimizar_para_ia(path):
    img = Image.open(path)
    if img.width > 1024:
        w_p = (1024 / float(img.width))
        img = img.resize((1024, int(img.height * w_p)), Image.Resampling.LANCZOS)
        img.save(path, "PNG", optimize=True)
    return path

def focus_chrome():
    time.sleep(1.2)
    hwnd = ctypes.windll.user32.FindWindowW(None, None)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)

@app.route('/ui/capture/<int:cap_id>')
def ui_capture(cap_id):
    conn = get_db_conn(); cur = conn.cursor(); cur.execute("SELECT path FROM screenshots WHERE id=?", (cap_id,))
    row = cur.fetchone(); conn.close()
    if row:
        img = f"/capturas/{os.path.basename(row[0])}"
        return render_template_string(HTML_TEMPLATE, captureId=cap_id, imagePath=img)
    return "Error 404", 404

@app.route('/ui/ask/<int:cap_id>', methods=['POST'])
def ui_ask(cap_id):
    api_key = get_api_key()
    if not api_key:
        # Devuelve el error como si fuera un mensaje del bot para no romper el HTML
        return jsonify({"success": True, "answer": "⚠️ **API Key no configurada.**\n\nPor favor, reinicia la aplicación y configura tu clave de Google Gemini para poder responderme."})
    
    genai.configure(api_key=api_key) # Carga la API key del usuario
    q = request.args.get('question')
    conn = get_db_conn(); cur = conn.cursor(); cur.execute("SELECT path FROM screenshots WHERE id=?", (cap_id,)); row = cur.fetchone(); conn.close()
    
    if row:
        try:
            res = genai.GenerativeModel(MODEL_NAME).generate_content([genai.upload_file(optimizar_para_ia(row[0])), f"Responde en español: {q}"])
            return jsonify({"success": True, "answer": res.text})
        except Exception as e:
            return jsonify({"success": True, "answer": f"❌ **Error en la API:**\n\n{str(e)}"})
            
    return jsonify({"success": False})

@app.route('/capturas/<path:f>')
def serv_f(f): return send_from_directory(CAPTURES_DIR, f)

def do_shot():
    global capturing_lock
    if capturing_lock: return
    capturing_lock = True
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S"); fn = f"shot_{ts}.png"; fp = os.path.join(CAPTURES_DIR, fn)
        ImageGrab.grab().save(fp)
        conn = get_db_conn(); cur = conn.cursor(); cur.execute("INSERT INTO screenshots (path, time) VALUES (?, ?)", (fp, datetime.now().isoformat())); cid = cur.lastrowid; conn.commit(); conn.close()
        url = f"http://localhost:8095/ui/capture/{cid}"
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome):
            subprocess.Popen([chrome, "--new-window", "--start-fullscreen", url])
            threading.Thread(target=focus_chrome, daemon=True).start()
        else: webbrowser.open(url)
    finally:
        time.sleep(1); capturing_lock = False

# Hilo para gestionar la secuencia de inicio
def startup_flow():
    if not get_api_key():
        prompt_for_api_key(is_first_time=True)
    else:
        show_startup_notif()

if __name__ == '__main__':
    init_db()
    
    # Arranca el gestor de inicio en un hilo
    threading.Thread(target=startup_flow, daemon=True).start()
    
    keyboard.add_hotkey('ctrl+alt+s', do_shot)
    keyboard.add_hotkey('ctrl+alt+q', confirm_exit)
    socketio.run(app, port=8095, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)