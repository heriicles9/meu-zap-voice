import os
import requests
from flask import Flask, request, jsonify
import pymongo
import traceback
import time

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")

# 🚨 A SUA CHAVE DA INTELIGÊNCIA ARTIFICIAL:
GEMINI_KEY = "AIzaSyACYdQJKNDohhoCJFrZjCZuIWt_tKberDs"

# --- CONEXÃO BANCO ---
try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') 
    print("✅ Banco OK!")
except Exception as e:
    client = None

@app.route('/', methods=['GET'])
def home(): return "<h1>🧠 O Cérebro do ZapFluxo + IA está Online! ⚡</h1>"

# --- FUNÇÃO DA IA (GEMINI) 🧠 ---
def consultar_gemini(treinamento, mensagem_cliente):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = f"Você é um assistente de WhatsApp. Siga ESTRITAMENTE estas regras e comportamento:\n{treinamento}\n\nResponda de forma curta e natural a seguinte mensagem do cliente:\nCliente: {mensagem_cliente}"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # 🚨 AGORA O ROBÔ VAI DEDURAR O ERRO EXATO DO GOOGLE!
            print(f"💥 ERRO GEMINI: {res.text}")
            return f"🤖 [Erro do Google! Código: {res.status_code}]"
    except Exception as e:
        return f"🤖 [Falha de conexão com a central neural: {e}]"

# --- FUNÇÕES DE ENVIO ---
def enviar_mensagem(instancia, numero, texto):
    headers = {"apikey": EVO_KEY}
    try: requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "options": {"delay": 2000, "presence": "composing"}}, headers=headers, timeout=5)
    except: pass 
    time.sleep(2)
    try: requests.post(f"{EVO_URL}/message/sendText/{instancia}", json={"number": numero, "textMessage": {"text": texto}}, headers=headers, timeout=20)
    except: pass

def enviar_audio(instancia, numero, b64_audio):
    headers = {"apikey": EVO_KEY}
    try: requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "options": {"delay": 3000, "presence": "recording"}}, headers=headers, timeout=5)
    except: pass
    time.sleep(3)
    try: requests.post(f"{EVO_URL}/message/sendWhatsAppAudio/{instancia}", json={"number": numero, "options": {"encoding": True}, "audioMessage": {"audio": b64_audio}}, headers=headers, timeout=20)
    except: pass

def enviar_imagem(instancia, numero, b64_img, legenda):
    headers = {"apikey": EVO_KEY}
    try: requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "options": {"delay": 2000, "presence": "composing"}}, headers=headers, timeout=5)
    except: pass
    time.sleep(2)
    if legenda.startswith("📸"): legenda = "" 
    try: requests.post(f"{EVO_URL}/message/sendMedia/{instancia}", json={"number": numero, "options": {"delay": 0}, "mediaMessage": {"mediatype": "image", "caption": legenda, "media": b64_img}}, headers=headers, timeout=20)
    except: pass

# --- ROTEADOR (O Cérebro do Robô) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if not client: return jsonify({"erro": "Sem banco"}), 500
    try:
        dados = request.json
        evento = dados.get('event', '')
        
        if evento.lower() == 'messages.upsert':
            instancia = dados.get('instance')
            msg_data = dados.get('data', {}).get('message', {})
            key = dados.get('data', {}).get('key', {})
            if key.get('fromMe'): return jsonify({"status": "ignorado"}), 200
                
            numero_exato = key.get('remoteJid', '')
            if "@lid" in numero_exato: numero_exato = "557583479259"
                
            texto_recebido = ""
            if "conversation" in msg_data: texto_recebido = msg_data["conversation"]
            elif "extendedTextMessage" in msg_data: texto_recebido = msg_data["extendedTextMessage"]["text"]
            if not texto_recebido: return jsonify({"status": "sem texto"}), 200
                
            db = client["zapvoice_db"]
            numero_db = numero_exato.split('@')[0]
            
            if texto_recebido.strip().lower() == "reset":
                db["sessoes"].delete_one({"numero": numero_db, "instancia": instancia})
                enviar_mensagem(instancia, numero_exato, "🔄 Memória apagada! Mande um 'Oi'.")
                return jsonify({"status": "resetado"}), 200
                
            fluxo_doc = db["fluxos"].find_one({"_id": instancia})
            if not fluxo_doc or not fluxo_doc.get("blocos"): return jsonify({"status": "vazio"}), 200
                
            blocos = fluxo_doc["blocos"]
            sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
            bloco_atual = None
            
            if not sessao:
                bloco_atual = blocos[0]
                db["sessoes"].insert_one({"numero": numero_db, "instancia": instancia, "bloco_id": bloco_atual["id"]})
            else:
                bloco_id_atual = sessao["bloco_id"]
                bloco_atual = next((b for b in blocos if b["id"] == bloco_id_atual), None)
                
                if bloco_atual:
                    proximo_id = None
                    # 🚨 Na IA, o robô NÃO avança de bloco.
                    if bloco_atual["tipo"] == "Robô IA":
                        proximo_id = None 
                    elif bloco_atual["tipo"] == "Menu":
                        for op in bloco_atual.get("opcoes", "").split("\n"):
                            if ">" in op and texto_recebido.strip().lower() == op.split(">")[0].strip().lower():
                                proximo_id = op.split(">")[1].strip()
                                break
                    elif bloco_atual["tipo"] in ["Texto", "Áudio", "Imagem"]:
                        proximo_id = bloco_atual.get("opcoes", "").strip()
                        
                    if proximo_id:
                        novo_bloco = next((b for b in blocos if b["id"] == proximo_id), None)
                        if novo_bloco:
                            bloco_atual = novo_bloco
                            db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})
            
            # 🚨 DECISÃO: O QUE ENVIAR PARA O CLIENTE?
            if bloco_atual:
                if bloco_atual["tipo"] == "Robô IA":
                    resposta_inteligente = consultar_gemini(bloco_atual["msg"], texto_recebido)
                    enviar_mensagem(instancia, numero_exato, resposta_inteligente)
                elif bloco_atual["tipo"] == "Áudio":
                    b64 = bloco_atual.get("arquivo_b64", "")
                    if b64: enviar_audio(instancia, numero_exato, b64)
                elif bloco_atual["tipo"] == "Imagem":
                    b64 = bloco_atual.get("arquivo_b64", "")
                    if b64: enviar_imagem(instancia, numero_exato, b64, bloco_atual.get("msg", ""))
                else:
                    enviar_mensagem(instancia, numero_exato, bloco_atual["msg"])
                
    except Exception as e:
        traceback.print_exc()
        
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
