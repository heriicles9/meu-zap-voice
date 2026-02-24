import os, requests, pymongo, time, traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGS ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client["zapvoice_db"]
except: client = None

@app.route('/')
def home(): return "ZapFluxo v2.5 Online 🚀"

def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    regra_fuga = f"\n\nORDEM: Se o cliente {condicao_saida}, adicione [MUDAR_BLOCO] ao final." if condicao_saida else ""
    prompt = f"Regras:\n{treinamento}{regra_fuga}\n\nHistórico:\n" + "\n".join(historico_lista)
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 429: time.sleep(3); res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return "😅 [Opa, muita gente falando! Tenta de novo em 1 min?]"
    except: return "🤖 [Falha na conexão neural]"

def enviar(inst, num, txt, tipo="text", b64="", leg=""):
    headers = {"apikey": EVO_KEY}
    requests.post(f"{EVO_URL}/chat/sendPresence/{inst}", json={"number": num, "options": {"delay": 2000, "presence": "composing"}}, headers=headers)
    time.sleep(2)
    if tipo == "text": requests.post(f"{EVO_URL}/message/sendText/{inst}", json={"number": num, "textMessage": {"text": txt}}, headers=headers)
    elif tipo == "audio": requests.post(f"{EVO_URL}/message/sendWhatsAppAudio/{inst}", json={"number": num, "audioMessage": {"audio": b64}}, headers=headers)
    elif tipo == "media": requests.post(f"{EVO_URL}/message/sendMedia/{inst}", json={"number": num, "mediaMessage": {"mediatype": "image", "caption": leg, "media": b64}}, headers=headers)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.json
        if dados.get('event') != 'messages.upsert': return jsonify({"ok":True})
        
        instancia = dados.get('instance')
        key = dados.get('data', {}).get('key', {})
        if key.get('fromMe'): return jsonify({"ok":True})
        
        numero = key.get('remoteJid', '')
        num_db = numero.split('@')[0]
        nome = dados.get('data', {}).get('pushName', 'Cliente')
        msg_wrap = dados.get('data', {}).get('message', {})
        texto = msg_wrap.get('conversation') or msg_wrap.get('extendedTextMessage', {}).get('text') or ""
        
        if not texto: return jsonify({"ok":True})
        if texto.lower() == "reset": 
            db["sessoes"].delete_one({"numero": num_db, "instancia": instancia})
            enviar(instancia, numero, "🔄 Resetado!")
            return jsonify({"ok":True})

        fluxo = db["fluxos"].find_one({"_id": instancia})
        if not fluxo: return jsonify({"ok":True})
        
        sessao = db["sessoes"].find_one({"numero": num_db, "instancia": instancia})
        if not sessao:
            bloco = fluxo["blocos"][0]
            db["sessoes"].insert_one({"numero": num_db, "instancia": instancia, "bloco_id": bloco["id"], "historico": []})
            sessao = db["sessoes"].find_one({"numero": num_db, "instancia": instancia})
        else:
            bloco = next((b for b in fluxo["blocos"] if b["id"] == sessao["bloco_id"]), fluxo["blocos"][0])
            prox = None
            if bloco["tipo"] == "Menu":
                for o in bloco["opcoes"].split("\n"):
                    if ">" in o and texto.strip() == o.split(">")[0].strip(): prox = o.split(">")[1].strip()
            elif bloco["tipo"] != "Robô IA": prox = bloco.get("opcoes")
            
            if prox:
                bloco = next((b for b in fluxo["blocos"] if b["id"] == prox), bloco)
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco["id"]}})

        if bloco["tipo"] == "Robô IA":
            hist = sessao.get("historico", []) + [f"Cliente: {texto}"]
            hist = hist[-10:]
            cond, dest = (bloco["opcoes"].split("|")[0], bloco["opcoes"].split("|")[1]) if "|" in bloco["opcoes"] else ("","")
            resp = consultar_gemini(bloco["msg"], hist, cond)
            mudar = "[MUDAR_BLOCO]" in resp
            resp = resp.replace("[MUDAR_BLOCO]", "").replace("{nome}", nome).strip()
            hist.append(f"João: {resp}")
            db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"historico": hist}})
            enviar(instancia, numero, resp)
            if mudar and dest: db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": dest}})
        elif bloco["tipo"] == "Áudio": enviar(instancia, numero, "", "audio", bloco.get("arquivo_b64"))
        elif bloco["tipo"] == "Imagem": enviar(instancia, numero, "", "media", bloco.get("arquivo_b64"), bloco["msg"].replace("{nome}", nome))
        else: enviar(instancia, numero, bloco["msg"].replace("{nome}", nome))

    except: traceback.print_exc()
    return jsonify({"ok":True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
