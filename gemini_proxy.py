#!/usr/bin/env python3
"""
Gemini API Key Rotation Proxy & UI
==================================
Rota automaticamente entre multiples API keys de Gemini.
Expone endpoint OpenAI compatible para LiteLLM.
Expone Web UI en http://localhost:19090 para administrar llaves.
"""

import json
import os
import sys
import threading
import time
import uuid
import datetime
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

# ── Configuracion ──────────────────────────────────────────────────────────────
PROXY_HOST = "0.0.0.0"
PROXY_PORT = 19090
MAX_RETRIES = 6
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE_GEMINI = os.path.join(BASE_DIR, "keys_store.json")
KEYS_FILE_OR = os.path.join(BASE_DIR, "keys_store2.json")
KEYS_FILE_NVIDIA = os.path.join(BASE_DIR, "keys_store3.json")
GEMINI_BASE = "https://generativelanguage.googleapis.com"
OPENROUTER_BASE = "https://openrouter.ai/api"
NVIDIA_BASE = "https://integrate.api.nvidia.com"
PROXY_CONFIG_FILE = os.path.join(BASE_DIR, "proxy_config.json")
# ──────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nanobot - LLM Proxy</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --container-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 50% 0%, #1e293b 0%, transparent 70%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem;
        }
        .container {
            width: 100%;
            max-width: 600px;
            background: var(--container-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; }
        p.subtitle { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
        .section-title { font-size: 1.1rem; font-weight: 500; margin-bottom: 1rem; color: var(--text-main); border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;}
        
        .provider-switch {
            display: flex;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 2rem;
            overflow: hidden;
        }
        .switch-btn {
            flex: 1;
            padding: 0.75rem;
            background: transparent;
            color: var(--text-muted);
            border: none;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s;
            border-radius: 0;
        }
        .switch-btn.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
        }

        .form-group { margin-bottom: 1rem; }
        label { display: block; font-size: 0.85rem; font-weight: 500; color: var(--text-muted); margin-bottom: 0.5rem; }
        input {
            width: 100%; padding: 0.75rem 1rem;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px; color: var(--text-main);
            font-size: 0.95rem; outline: none; transition: border-color 0.2s;
        }
        input:focus { border-color: var(--primary); }
        button.action-btn {
            width: 100%; padding: 0.75rem;
            background: var(--primary); color: white;
            border: none; border-radius: 8px;
            font-size: 0.95rem; font-weight: 500;
            cursor: pointer; transition: background 0.2s, transform 0.1s;
        }
        button.action-btn:hover { background: var(--primary-hover); }
        button.action-btn:active { transform: scale(0.98); }
        
        .keys-list { margin-top: 2rem; display: flex; flex-direction: column; gap: 0.5rem; max-height: 350px; overflow-y: auto; padding-right: 5px; }
        .key-item {
            display: flex; justify-content: space-between; align-items: center;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            padding: 0.75rem 1rem; border-radius: 8px;
            animation: fadeIn 0.3s ease-in-out;
        }
        .key-label { font-weight: 500; color: #fff; display: flex; align-items: center; gap: 0.5rem;}
        .key-val { font-family: monospace; color: var(--text-muted); font-size: 0.85rem; }
        .badge { background: rgba(16, 185, 129, 0.2); color: var(--success); padding: 0.2rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        .toast {
            position: fixed; bottom: 2rem; right: 2rem;
            background: var(--success); color: white;
            padding: 1rem 1.5rem; border-radius: 8px;
            font-weight: 500; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
            transform: translateY(100px); opacity: 0; transition: all 0.3s;
            z-index: 1000;
        }
        .toast.show { transform: translateY(0); opacity: 1; }
        .toast.error { background: var(--danger); }
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>
</head>
<body>
    <div class="container">
        <h1 id="mainTitle">✨ LLM Proxy</h1>
        <p class="subtitle">Administrador de Llaves Rotativas</p>

        <div class="provider-switch">
            <button id="btnGemini" class="switch-btn active" onclick="setProvider('gemini')">Gemini</button>
            <button id="btnOpenRouter" class="switch-btn" onclick="setProvider('openrouter')">OpenRouter</button>
            <button id="btnNvidia" class="switch-btn" onclick="setProvider('nvidia')">Nvidia</button>
        </div>

        <form id="addKeyForm">
            <div class="form-group">
                <label for="labelName">Nombre de la Llave (<span id="labelHint">Ej: gemini-pro-1</span>)</label>
                <input type="text" id="labelName" required placeholder="Ingresa un nombre" autocomplete="off">
            </div>
            <div class="form-group">
                <label for="apiKeyValue">API Key</label>
                <input type="password" id="apiKeyValue" required placeholder="API Key..." autocomplete="off">
            </div>

            <button type="submit" class="action-btn">Añadir Key e Inicializar en Caliente</button>
        </form>

        <div style="margin-top: 2.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                <h2 class="section-title" style="border-bottom: none; margin-bottom: 0; padding-bottom: 0;">Llaves Activas (<span id="keyCount">0</span>)</h2>
                <div style="font-size: 0.85rem; color: var(--text-muted); align-items: center; gap: 0.5rem; display: none;" id="providerModelContainer">
                    <span>Modelo global: <b id="currentGlobalModel" style="color: var(--text-main);">...</b></span>
                    <button class="action-btn" style="padding: 0.2rem 0.5rem; width: auto;" onclick="editProviderModel()">✏️</button>
                </div>
            </div>
            <div class="keys-list" id="keysList"></div>
        </div>
    </div>

    <div id="toast" class="toast">¡Activo!</div>

    <script>
        const form = document.getElementById('addKeyForm');
        const keysList = document.getElementById('keysList');
        const toast = document.getElementById('toast');
        const keyCount = document.getElementById('keyCount');
        
        let currentProvider = "gemini";

        const showToast = (msg, isError=false) => {
            toast.textContent = msg;
            toast.className = `toast show ${isError ? 'error' : ''}`;
            setTimeout(() => toast.className = 'toast', 3000);
        };

        const updateUIState = () => {
            document.getElementById('btnGemini').classList.toggle('active', currentProvider === 'gemini');
            document.getElementById('btnOpenRouter').classList.toggle('active', currentProvider === 'openrouter');
            document.getElementById('btnNvidia').classList.toggle('active', currentProvider === 'nvidia');
            
            let title = '✨ Gemini Proxy';
            if (currentProvider === 'openrouter') title = '✨ OpenRouter Proxy';
            else if (currentProvider === 'nvidia') title = '✨ Nvidia Proxy';
            document.getElementById('mainTitle').innerHTML = title;
            
            let hint = 'Ej: gemini-1';
            if (currentProvider === 'openrouter') hint = 'Ej: or-tesis';
            else if (currentProvider === 'nvidia') hint = 'Ej: nvidia-llama';
            document.getElementById('labelHint').textContent = hint;
            
            document.getElementById('providerModelContainer').style.display = (currentProvider === 'openrouter' || currentProvider === 'nvidia') ? 'flex' : 'none';
        };

        const fetchCurrentProvider = async () => {
            try {
                const res = await fetch('/api/provider');
                const data = await res.json();
                if(data.provider) {
                    currentProvider = data.provider;
                    updateUIState();
                }
            } catch(e) {}
        };

        const setProvider = async (prov) => {
            if(prov === currentProvider) return;
            try {
                const res = await fetch('/api/provider', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ provider: prov })
                });
                if(res.ok) {
                    currentProvider = prov;
                    updateUIState();
                    loadKeys();
                    let provName = 'Gemini';
                    if (prov === 'openrouter') provName = 'OpenRouter';
                    else if (prov === 'nvidia') provName = 'Nvidia';
                    showToast(`¡Cambiado a ${provName}!`);
                }
            } catch(e) {
                showToast('Error al cambiar proveedor', true);
            }
        };

        const loadKeys = async () => {
            try {
                const res = await fetch('/api/keys');
                const data = await res.json();
                
                // Actualizar estado devuelto por si se desincronio
                if(data.provider && data.provider !== currentProvider) {
                    currentProvider = data.provider;
                    updateUIState();
                }

                if (data.globalModel) {
                    document.getElementById('currentGlobalModel').textContent = data.globalModel;
                }
                keyCount.textContent = data.keys.length;
                keysList.innerHTML = '';
                data.keys.forEach(k => {
                    const masked = k.apiKey.substring(0, 6) + '••••••••' + k.apiKey.substring(k.apiKey.length - 4);
                    const dateAdded = new Date(k.addedAt).toLocaleDateString();
                    const el = document.createElement('div');
                    el.className = 'key-item';
                    
                    let modelHtml = '';
                    
                    el.innerHTML = `
                        <div>
                            <div class="key-label">${k.label}</div>
                            <div class="key-val" title="Agregada el ${dateAdded}">${masked}</div>
                            ${modelHtml}
                        </div>

                    `;
                    keysList.appendChild(el);
                });
            } catch (err) {
                keysList.innerHTML = '<div style="color: var(--danger)">Error cargando llaves.</div>';
            }
        };

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const label = document.getElementById('labelName').value.trim();
            const apiKey = document.getElementById('apiKeyValue').value.trim();
            
            if(!label || !apiKey) return;

            const btn = form.querySelector('button');
            const ogText = btn.textContent;
            btn.textContent = 'Guardando y Recargando...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/keys', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ label, apiKey })
                });

                if(res.ok) {
                    showToast('¡Configuración actualizada y recargada!');
                    form.reset();
                    loadKeys();
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Error al guardar.', true);
                }
            } catch (err) {
                showToast('Error de conexión.', true);
            } finally {
                btn.textContent = ogText;
                btn.disabled = false;
            }
        });

        const editProviderModel = async () => {
            const currentModel = document.getElementById('currentGlobalModel').textContent;
            const newModel = prompt(`Editar modelo global para ${currentProvider}:`, currentModel === '...' ? '' : currentModel);
            if (newModel !== null) {
                try {
                    const res = await fetch('/api/provider/model', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ model: newModel })
                    });
                    if(res.ok) {
                        showToast('Modelo global actualizado');
                        loadKeys();
                    } else {
                        const err = await res.json();
                        showToast(err.error || 'Error al actualizar', true);
                    }
                } catch (err) {
                    showToast('Error de conexión', true);
                }
            }
        };

        // Initialize
        fetchCurrentProvider().then(loadKeys);
    </script>
</body>
</html>"""

def get_keys_file(provider):
    if provider == "gemini": return KEYS_FILE_GEMINI
    if provider == "openrouter": return KEYS_FILE_OR
    return KEYS_FILE_NVIDIA

def get_default_model_for_provider(provider):
    if provider == "openrouter": return "nvidia/nemotron-3-super-120b-a12b:free"
    elif provider == "nvidia": return "meta/llama3-70b-instruct"
    return "gemini-2.5-flash"

def load_keys(provider):
    path = get_keys_file(provider)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    global_model = data.get("default_model", get_default_model_for_provider(provider))
    keys = [k for k in data.get("keys", []) if k.get("provider") == provider and k.get("apiKey")]
    
    for k in keys:
        k["model"] = global_model
        
    return keys

def save_new_key(provider, label, api_key):
    path = get_keys_file(provider)
    # Lee existente
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"keys": []}
    
    # Comprueba dup
    for k in data.get("keys", []):
        if k.get("apiKey") == api_key:
            return False, "Esa API Key ya esta registrada."
            
    new_entry = {
        "id": str(uuid.uuid4()),
        "label": label,
        "provider": provider,
        "apiKey": api_key,
        "apiBase": None,
        "tokensUsed": 0,
        "addedAt": datetime.datetime.now().isoformat()
    }
    data["keys"].append(new_entry)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True, new_entry

def edit_provider_model(provider, model):
    path = get_keys_file(provider)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"keys": []}
    
    data["default_model"] = model
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True, "Ok"

def load_active_provider():
    """Load the persisted active provider from disk, defaulting to 'gemini'."""
    try:
        if os.path.exists(PROXY_CONFIG_FILE):
            with open(PROXY_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("active_provider", "gemini")
    except Exception:
        pass
    return "gemini"

def save_active_provider(provider):
    """Persist the active provider to disk."""
    try:
        with open(PROXY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_provider": provider}, f)
    except Exception:
        pass

class KeyRotator:
    def __init__(self, provider):
        self._provider = provider
        self._keys_file = get_keys_file(provider)
        self._keys = load_keys(provider)
        self._index = 0
        self._lock = threading.Lock()
        
        self.usage_stats = {}
        for k in self._keys:
            self.usage_stats[k.get("apiKey")] = k.get("tokensUsed", 0)
        self._stats_lock = threading.Lock()
        
        self._stop_event = threading.Event()
        self._save_thread = threading.Thread(target=self._save_loop, daemon=True)
        self._save_thread.start()

    def _save_loop(self):
        while not self._stop_event.is_set():
            time.sleep(15)
            # Token persistence disabled
            # self.persist_stats()
            
    def persist_stats(self):
        if not os.path.exists(self._keys_file): return
        with self._stats_lock:
            snap = dict(self.usage_stats)
        try:
            with open(self._keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cambios = False
            for k in data.get("keys", []):
                ak = k.get("apiKey")
                if ak in snap and k.get("tokensUsed", 0) != snap[ak]:
                    k["tokensUsed"] = snap[ak]
                    cambios = True
            if cambios:
                with open(self._keys_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_tokens(self, api_key, tokens):
        with self._stats_lock:
            if api_key in self.usage_stats:
                self.usage_stats[api_key] += tokens
            else:
                self.usage_stats[api_key] = tokens

    def reload(self, new_keys):
        with self._lock:
            self._keys = new_keys
            self._index = 0
            with self._stats_lock:
                for k in new_keys:
                    if k.get("apiKey") not in self.usage_stats:
                        self.usage_stats[k.get("apiKey")] = k.get("tokensUsed", 0)

    def stop(self):
        self._stop_event.set()

    def get_next(self):
        with self._lock:
            if not self._keys:
                return 0, None
            idx = self._index
            self._index = (self._index + 1) % len(self._keys)
            return idx, self._keys[idx]

    def peek(self, idx):
        if not self._keys: return None
        return self._keys[idx % len(self._keys)]

    @property
    def count(self):
        return len(self._keys)

_rotators = {}
_active_provider = "gemini"

def inject_api_key(path, api_key):
    if path.startswith("/v1/chat/completions") or path.startswith("/chat/completions"):
        path = "/v1beta/openai/chat/completions"
    elif path.startswith("/v1/models") or path.startswith("/models"):
        path = "/v1beta/openai/models"

    if "?" in path:
        base, qs = path.split("?", 1)
        params = urllib.parse.parse_qs(qs, keep_blank_values=True)
        params["key"] = [api_key]
        return base + "?" + urllib.parse.urlencode(params, doseq=True)
    return path + "?key=" + urllib.parse.quote(api_key, safe="")

def forward_request(path, method, headers, body, key_entry):
    api_key = key_entry["apiKey"]
    provider = key_entry.get("provider", "gemini")
    
    if provider == "gemini":
        url = GEMINI_BASE + inject_api_key(path, api_key)
        # Manejar el prefijo del modelo introducido por LiteLLM (gemini/gemini-...)
        if body and method.upper() in ("POST", "PUT"):
            try:
                payload = json.loads(body.decode("utf-8"))
                if "model" in payload and isinstance(payload["model"], str):
                    if payload["model"].startswith("gemini/"):
                        payload["model"] = payload["model"].split("gemini/", 1)[1]
                        body = json.dumps(payload).encode("utf-8")
            except Exception:
                pass
    elif provider == "openrouter" or provider == "nvidia":
        # OpenRouter / Nvidia
        # path suele ser /v1/chat/completions (LiteLLM compatible)
        # removemos query params si los hubiera que sean propios de gemini
        clean_path = path.split("?")[0] if "?" in path else path
        if clean_path == "/chat/completions":
            clean_path = "/v1/chat/completions"
        elif clean_path == "/models":
            clean_path = "/v1/models"
            
        base_url = OPENROUTER_BASE if provider == "openrouter" else NVIDIA_BASE
        url = base_url + clean_path
        original_model = None
        if body and method.upper() in ("POST", "PUT"):
            try:
                payload = json.loads(body.decode("utf-8"))
                original_model = payload.get("model")  # save for response normalization
                # Override model with the one defined in key_entry, if present
                override_model = key_entry.get("model")
                if override_model:
                    payload["model"] = override_model
                body = json.dumps(payload).encode("utf-8")
            except Exception:
                pass

    skip_hdrs = {"host", "content-length", "transfer-encoding",
                 "connection", "x-api-key", "authorization", "accept-encoding"}
    fwd = {k: v for k, v in headers.items() if k.lower() not in skip_hdrs}
    
    if provider == "gemini":
        fwd["x-goog-api-key"] = api_key
    fwd["Authorization"] = f"Bearer {api_key}"
    
    if body:
        fwd["Content-Length"] = str(len(body))
    
    req = urllib.request.Request(url, data=body or None, headers=fwd, method=method)
    sys.stdout.write("[DEBUG] forward_request: %s %s (provider=%s)\n" % (method, url[:120], provider))
    sys.stdout.flush()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_body = resp.read()
            resp_hdrs = dict(resp.headers)
            # OpenRouter returns whitespace before JSON — strip it
            if provider != "gemini":
                resp_body = resp_body.lstrip()
                # Normalize model field in response to match what client sent
                if original_model:
                    try:
                        resp_json = json.loads(resp_body)
                        if isinstance(resp_json, dict) and "model" in resp_json:
                            resp_json["model"] = original_model
                            resp_body = json.dumps(resp_json).encode("utf-8")
                    except Exception:
                        pass
            sys.stdout.write("[DEBUG] response: %d, body[:200]=%s\n" % (resp.status, resp_body[:200]))
            sys.stdout.flush()
            return resp.status, resp_body, {"Content-Type": "application/json"}
    except urllib.error.HTTPError as e:
        err_body = e.read()
        if provider != "gemini":
            err_body = err_body.lstrip()
        sys.stdout.write("[DEBUG] HTTPError: %d, body[:200]=%s\n" % (e.code, err_body[:200]))
        sys.stdout.flush()
        return e.code, err_body, {"Content-Type": "application/json"}
    except urllib.error.URLError as e:
        sys.stdout.write("[DEBUG] URLError: %s\n" % str(e.reason))
        sys.stdout.flush()
        err = json.dumps({"error": {"message": str(e.reason), "type": "connection_error"}}).encode("utf-8")
        return 503, err, {"Content-Type": "application/json"}

class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "GeminiKeyProxy/2.0"
    _lock = threading.Lock()

    def log_message(self, fmt, *args):
        with ProxyHandler._lock:
            msg = "[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args)
            sys.stdout.write(msg)
            sys.stdout.flush()

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n > 0 else b""

    def _respond(self, status, body, hdrs):
        self.send_response(status)
        skip = {"transfer-encoding", "connection", "content-encoding", "content-length"}
        for k, v in hdrs.items():
            if k.lower() not in skip:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ui(self):
        global _active_provider
        
        # Admin UI: Servir HTML
        if self.path == "/" and self.command == "GET":
            self._respond(200, HTML_TEMPLATE.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"})
            return True
            
        # Admin UI: Get o Set provider
        if self.path == "/api/provider" and self.command == "GET":
            self._respond(200, json.dumps({"provider": _active_provider}).encode("utf-8"), {"Content-Type": "application/json"})
            return True
            
        if self.path == "/api/provider" and self.command == "POST":
            body = self._body()
            try:
                data = json.loads(body.decode("utf-8"))
                new_prov = data.get("provider")
                if new_prov in ["gemini", "openrouter", "nvidia"]:
                    _active_provider = new_prov
                    save_active_provider(new_prov)  # persist to disk
                    self.log_message("UI: Proveedor cambiado a [%s]", _active_provider)
                    self._respond(200, b'{"status": "ok"}', {"Content-Type": "application/json"})
                else:
                    self._respond(400, b'{"error": "Proveedor invalido"}', {"Content-Type": "application/json"})
            except Exception as e:
                self._respond(500, json.dumps({"error": str(e)}).encode("utf-8"), {"Content-Type": "application/json"})
            return True

        # Admin UI: Listar llaves
        if self.path == "/api/keys" and self.command == "GET":
            # list current provider's keys
            keys = load_keys(_active_provider)
            
            # Find the global model
            global_model = "Desconocido"
            path = get_keys_file(_active_provider)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    global_model = data.get("default_model", get_default_model_for_provider(_active_provider))
            else:
                global_model = get_default_model_for_provider(_active_provider)

            cur_rotator = _rotators.get(_active_provider)
            if cur_rotator:
                with cur_rotator._stats_lock:
                    for k in keys:
                        k["tokensUsed"] = cur_rotator.usage_stats.get(k["apiKey"], k.get("tokensUsed", 0))
            for k in keys:
                k["apiKey"] = k["apiKey"] # enviamos en claro, la UI censura
                
            resp = {"keys": keys, "provider": _active_provider, "globalModel": global_model}
            self._respond(200, json.dumps(resp).encode("utf-8"), {"Content-Type": "application/json"})
            return True
            
        # Admin UI: Añadir llave
        if self.path == "/api/keys" and self.command == "POST":
            body = self._body()
            try:
                data = json.loads(body.decode("utf-8"))
                label = data.get("label", "").strip()
                api_key = data.get("apiKey", "").strip()
                if not label or not api_key:
                    self._respond(400, b'{"error": "Faltan campos."}', {"Content-Type": "application/json"})
                    return True
                
                success, result = save_new_key(_active_provider, label, api_key)
                if not success:
                    self._respond(400, json.dumps({"error": result}).encode("utf-8"), {"Content-Type": "application/json"})
                    return True
                
                # HOT RELOAD
                if _active_provider in _rotators:
                    _rotators[_active_provider].reload(load_keys(_active_provider))
                self.log_message("UI: Añadida llava [%s] a %s y recargada memoria", label, _active_provider)
                
                self._respond(200, b'{"status": "ok"}', {"Content-Type": "application/json"})
            except Exception as e:
                self._respond(500, json.dumps({"error": str(e)}).encode("utf-8"), {"Content-Type": "application/json"})
            return True

        # Admin UI: Editar modelo global del proveedor
        if self.path == "/api/provider/model" and self.command == "POST":
            body = self._body()
            try:
                data = json.loads(body.decode("utf-8"))
                model = data.get("model", "").strip()
                
                success, result = edit_provider_model(_active_provider, model)
                if not success:
                    self._respond(400, json.dumps({"error": result}).encode("utf-8"), {"Content-Type": "application/json"})
                    return True
                
                # HOT RELOAD
                if _active_provider in _rotators:
                    _rotators[_active_provider].reload(load_keys(_active_provider))
                self.log_message("UI: Editado modelo global en %s", _active_provider)
                
                self._respond(200, b'{"status": "ok"}', {"Content-Type": "application/json"})
            except Exception as e:
                self._respond(500, json.dumps({"error": str(e)}).encode("utf-8"), {"Content-Type": "application/json"})
            return True

        return False

    def _handle(self):
        if self._handle_ui():
            return
            
        if self.path == "/health":
            self._respond(200, b'{"status":"ok"}', {"Content-Type": "application/json"})
            return

        rotator = _rotators.get(_active_provider)
        if not rotator or rotator.count == 0:
            self._respond(503, b'{"error": "No hay keys disponibles"}', {"Content-Type": "application/json"})
            return

        body = self._body()
        headers = dict(self.headers)
        start_idx, key_entry = rotator.get_next()
        attempt = 0
        status, resp_body, resp_headers = 0, b"", {}

        while attempt <= rotator.count:
            label = key_entry["label"]
            api_key = key_entry["apiKey"]
            self.log_message("PROXY [%s] %s %s", label, self.command, self.path[:50])
            status, resp_body, resp_headers = forward_request(
                self.path, self.command, headers, body, key_entry
            )
            if status == 429 and attempt < rotator.count - 1:
                attempt += 1
                key_entry = rotator.peek(start_idx + attempt)
                self.log_message("429 [%s] > rota a [%s] (intento %d)", label, key_entry["label"], attempt)
                time.sleep(0.3)
            else:
                # Token counting disabled
                self.log_message("RES   [%s] %d", label, status)
                break

        self._respond(status, resp_body, resp_headers)

    def do_GET(self):    self._handle()
    def do_POST(self):   self._handle()
    def do_PUT(self):    self._handle()
    def do_DELETE(self): self._handle()
    def do_PATCH(self):  self._handle()


def main():
    global _rotators, _active_provider
    print("=" * 55, flush=True)
    print("  Unified Key Rotation Proxy  |  UI: http://localhost:%d" % PROXY_PORT, flush=True)
    print("=" * 55, flush=True)
    
    _rotators["gemini"] = KeyRotator("gemini")
    _rotators["openrouter"] = KeyRotator("openrouter")
    _rotators["nvidia"] = KeyRotator("nvidia")
    
    # Load persisted provider (defaults to gemini)
    _active_provider = load_active_provider()
    print("[INFO] %d keys de Gemini cargadas." % _rotators["gemini"].count, flush=True)
    print("[INFO] %d keys de OpenRouter cargadas." % _rotators["openrouter"].count, flush=True)
    print("[INFO] %d keys de Nvidia cargadas." % _rotators["nvidia"].count, flush=True)
    print("[INFO] Proveedor activo: %s" % _active_provider, flush=True)
        
    server = ThreadingHTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Proxy detenido.", flush=True)
        for r in _rotators.values():
            r.stop()
        server.server_close()

if __name__ == "__main__":
    main()
