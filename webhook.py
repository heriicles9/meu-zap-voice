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

# --- CONEXÃO BANCO ---
try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') # Força um teste rápido no banco!
    print("✅ Banco de Dados OK!")
except Exception as e:
    client = None
    print(f"❌ Erro no Banco: {e}")

# 🌐 ROTA DE TESTE (Para você abrir no navegador e ver se está online!)
@app.route('/', methods=['GET'])
def home():
    return "<h1>🧠 O Cérebro do ZapFluxo está Online e Operante! ⚡</h1>"

# 1️⃣ FUNÇÃO DE ENVIAR TEXTO (Agora com limite de espera!)
def enviar_mensagem(instancia, numero, texto):
    headers = {"apikey": EVO_KEY}
    
    url_presenca = f"{EVO_URL}/chat/sendPresence/{instancia}"
    payload_presenca = {"number": numero, "options": {"delay": 2000, "presence": "composing"}}
    try:
        # Tenta acionar o digitando. Se o motor demorar mais de 10 segs, ignora para não travar!
        requests.post(url_presenca, json=payload_presenca, headers=headers, timeout=10)
    except: pass 
    
    time.sleep(2)
    
    url = f"{EVO_URL}/message/sendText/{instancia}"
    data = {"number": numero, "textMessage": {"text": texto}}
    print(f"📤 Disparando a mensagem: {texto}")
    try:
        res = requests.post(url, json=data, headers=headers, timeout=30)
        print(f"📠 Confirmação da API: {res.status_code} - {res.text}")
    except Exception as e:
        print("💥 Motor demorou para responder! Evitando congelamento do cérebro.")

# 2️⃣ FUNÇÃO DE ENVIAR ÁUDIO 
def enviar_audio(instancia, numero, b64_audio):
    headers = {"apikey": EVO_KEY}
    
    url_presenca = f"{EVO_URL}/chat/sendPresence/{instancia}"
    payload_presenca = {"number": numero, "options": {"delay": 3000, "presence": "recording"}}
    try:
        requests.post(url_presenca, json=payload_presenca, headers=headers, timeout=10)
    except: pass
    
    time.sleep(3)
    
    url = f"{EVO_URL}/message/sendWhatsAppAudio/{instancia}"
    data = {"number": numero, "options": {"encoding": True}, "audioMessage": {"audio": b64_audio}}
    print(f"🎤 Disparando ÁUDIO para: {numero}")
    try:
        res = requests.post(url, json=data, headers=headers, timeout=30)
        print(f"📠 Confirmação da API (Áudio): {res.status_code} - {res.text}")
    except Exception as e:
        print("💥 Motor demorou para responder o Áudio! Evitando congelamento.")

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
            if "conversation" in msg_data:
                texto_recebido = msg_data["conversation"]
            elif "extendedTextMessage" in msg_data:
                texto_recebido = msg_data["extendedTextMessage"]["text"]
                
            if not texto_recebido: return jsonify({"status": "sem texto"}), 200
                
            db = client["zapvoice_db"]
            numero_db = numero_exato.split('@')[0]
            
            if texto_recebido.strip().lower() == "reset":
                db["sessoes"].delete_one({"numero": numero_db, "instancia": instancia})
                enviar_mensagem(instancia, numero_exato, "🔄 Memória apagada! Mande um 'Oi'.")
                return jsonify({"status": "resetado"}), 200
                
            fluxo_doc = db["fluxos"].find_one({"_id": instancia})
            if not fluxo_doc or not fluxo_doc.get("blocos"): return jsonify({"status": "fluxo vazio"}), 200
                
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
                    if bloco_atual["tipo"] == "Menu":
                        opcoes = bloco_atual.get("opcoes", "").split("\n")
                        for op in opcoes:
                            if ">" in op:
                                botao, destino = op.split(">")
                                if texto_recebido.strip().lower() == botao.strip().lower():
                                    proximo_id = destino.strip()
                                    break
                    elif bloco_atual["tipo"] in ["Texto", "Áudio"]:
                        proximo_id = bloco_atual.get("opcoes", "").strip()
                        
                    if proximo_id:
                        novo_bloco = next((b for b in blocos if b["id"] == proximo_id), None)
                        if novo_bloco:
                            bloco_atual = novo_bloco
                            db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})
            
            if bloco_atual:
                if bloco_atual["tipo"] == "Áudio":
                    b64 = bloco_atual.get("arquivo_b64", "")
                    if b64: enviar_audio(instancia, numero_exato, b64)
                    else: enviar_mensagem(instancia, numero_exato, "🎧 [Áudio corrompido ou vazio]")
                else:
                    enviar_mensagem(instancia, numero_exato, bloco_atual["msg"])
                
    except Exception as e:
        print(f"💥 ERRO GRAVE NO PYTHON: {e}")
        traceback.print_exc()
        
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
