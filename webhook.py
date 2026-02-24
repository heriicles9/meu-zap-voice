import os, requests, pymongo, time, traceback
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client["zapvoice_db"]
except:
    client = None

@app.route('/')
def home():
    return "ZapFluxo v3.2 (Escudo Máximo + Gemini 2.5) Online 🚀🎧"

# --- FUNÇÃO 1: IA PARA CONVERSAR ---
def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
    # 🚨 ATUALIZADO PARA O GEMINI 2.5 FLASH!
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    texto_historico = "\n".join(historico_lista)
    regra_fuga = ""
    if condicao_saida:
        regra_fuga = f"\n\nORDEM SECRETA: Se o cliente {condicao_saida}, você DEVE adicionar EXATAMENTE a palavra [MUDAR_BLOCO] no final da sua resposta."
    
    prompt = f"Você é um assistente de WhatsApp. Siga estas regras:\n{treinamento}{regra_fuga}\n\nHistórico:\n{texto_historico}\n\nSua resposta:"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for tentativa in range(3):
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            if res.status_code == 200:
                texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                return texto.replace("João:", "").replace("Assistente:", "").strip()
            elif res.status_code == 429:
                time.sleep(4)
            else:
                return f"🤖 [Erro do Google! Código: {res.status_code}]"
        except:
            time.sleep(2)
            
    return "😅 [Opa, o sistema deu uma congestionada aqui. Pode repetir?]"

# --- FUNÇÃO 2: BAIXAR ÁUDIO DO WHATSAPP ---
def obter_base64_da_mensagem(instancia, data_completo):
    url = f"{EVO_URL}/chat/getBase64FromMediaMessage/{instancia}"
    headers = {"apikey": EVO_KEY}
    try:
        # A API precisa do objeto 'data' inteiro para ler a Key e baixar a mídia
        res = requests.post(url, json={"message": data_completo}, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            b64 = res.json().get("base64", "")
            return b64.split(",")[1] if "," in b64 else b64
    except:
        pass
    return None

# --- FUNÇÃO 3: IA PARA TRANSCREVER ÁUDIO ---
def transcrever_audio(audio_b64):
    # 🚨 ATUALIZADO PARA O GEMINI 2.5 FLASH!
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": "Transcreva exatamente o que o cliente disse neste áudio, ignorando ruídos. Responda APENAS com a transcrição em texto."},
                {"inline_data": {"mimeType": "audio/ogg", "data": audio_b64}}
            ]
        }]
    }
    
    for tentativa in range(3):
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            elif res.status_code == 429:
                time.sleep(4)
            else:
                break
        except:
            time.sleep(2)
            
    return "[Áudio incompreensível ou falha na rede]"

def enviar_mensagem(instancia, numero, texto, tipo="text", b64="", legenda=""):
    headers = {"apikey": EVO_KEY}
    requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "delay": 2000, "presence": "composing"}, headers=headers)
    time.sleep(2)
    
    if tipo == "text":
        requests.post(f"{EVO_URL}/message/sendText/{instancia}", json={"number": numero, "textMessage": {"text": texto}, "options": {"delay": 0, "presence": "composing"}}, headers=headers)
    elif tipo == "audio":
        requests.post(f"{EVO_URL}/message/sendWhatsAppAudio/{instancia}", json={"number": numero, "audioMessage": {"audio": b64}}, headers=headers)
    elif tipo == "media":
        requests.post(f"{EVO_URL}/message/sendMedia/{instancia}", json={"number": numero, "mediaMessage": {"mediatype": "image", "caption": legenda, "media": b64}}, headers=headers)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.json
        if dados.get('event') != 'messages.upsert':
            return jsonify({"status": "ignored"}), 200
        
        instancia = dados.get('instance')
        data = dados.get('data', {})
        key = data.get('key', {})
        
        if key.get('fromMe'):
            return jsonify({"status": "from_me"}), 200
            
        numero_jid = key.get('remoteJid', '')
        numero_db = numero_jid.split('@')[0]
        nome_cliente = data.get('pushName', 'Cliente')
        
        msg_obj = data.get('message', {})
        texto_cliente = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""
        
        # 🚨 DETECTOR DE ÁUDIO BLINDADO
        # Converte a mensagem toda em texto para achar o áudio não importa onde o WhatsApp esconda
        is_audio = "audioMessage" in str(msg_obj)
        
        if not texto_cliente and not is_audio:
            return jsonify({"status": "no_text_or_audio"}), 200
            
        if is_audio:
            # Passamos a variável 'data' inteira para a API conseguir baixar
            b64_audio = obter_base64_da_mensagem(instancia, data)
            if b64_audio:
                texto_cliente = transcrever_audio(b64_audio)
            else:
                texto_cliente = "[O cliente enviou um áudio, mas o sistema falhou ao baixar o arquivo]"

        if texto_cliente.lower() == "reset":
            db["sessoes"].delete_one({"numero": numero_db, "instancia": instancia})
            enviar_mensagem(instancia, numero_jid, "🔄 Conversa resetada!")
            return jsonify({"status": "reset"}), 200

        fluxo_doc = db["fluxos"].find_one({"_id": instancia})
        if not fluxo_doc or not fluxo_doc.get("blocos"):
            return jsonify({"status": "no_flow"}), 200
        
        sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
        
        if not sessao:
            bloco_atual = fluxo_doc["blocos"][0]
            db["sessoes"].insert_one({
                "numero": numero_db, 
                "instancia": instancia, 
                "bloco_id": bloco_atual["id"], 
                "historico": []
            })
            sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
        else:
            bloco_atual = next((b for b in fluxo_doc["blocos"] if b["id"] == sessao["bloco_id"]), fluxo_doc["blocos"][0])
            
            proximo_id = None
            if bloco_atual["tipo"] == "Menu":
                for linha in bloco_atual["opcoes"].split("\n"):
                    if ">" in linha:
                        btn, dst = linha.split(">")
                        if texto_cliente.strip().lower() == btn.strip().lower():
                            proximo_id = dst.strip()
            elif bloco_atual["tipo"] != "Robô IA":
                proximo_id = bloco_atual.get("opcoes")
            
            if proximo_id:
                bloco_atual = next((b for b in fluxo_doc["blocos"] if b["id"] == proximo_id), bloco_atual)
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})

        if sessao.get("nome_personalizado"):
            nome_cliente = sessao.get("nome_personalizado")

        if bloco_atual["tipo"] == "Robô IA":
            historico = sessao.get("historico", [])
            historico.append(f"Cliente: {texto_cliente}")
            historico = historico[-10:] 
            
            condicao, destino = ("", "")
            if "|" in bloco_atual["opcoes"]:
                condicao, destino = bloco_atual["opcoes"].split("|")
            
            resposta_ia = consultar_gemini(bloco_atual["msg"], historico, condicao)
            
            mudar_bloco = "[MUDAR_BLOCO]" in resposta_ia
            resposta_ia = resposta_ia.replace("[MUDAR_BLOCO]", "").replace("{nome}", nome_cliente).strip()
            
            historico.append(f"João: {resposta_ia}")
            db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"historico": historico}})
            
            enviar_mensagem(instancia, numero_jid, resposta_ia)
            
            if mudar_bloco and destino:
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": destino.strip()}})
                
        elif bloco_atual["tipo"] == "Áudio":
            enviar_mensagem(instancia, numero_jid, "", "audio", bloco_atual.get("arquivo_b64"))
        elif bloco_atual["tipo"] == "Imagem":
            msg_legenda = bloco_atual["msg"].replace("{nome}", nome_cliente)
            enviar_mensagem(instancia, numero_jid, "", "media", bloco_atual.get("arquivo_b64"), msg_legenda)
        else:
            msg_final = bloco_atual["msg"].replace("{nome}", nome_cliente)
            enviar_mensagem(instancia, numero_jid, msg_final)

    except:
        traceback.print_exc()
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # 🚨 Puxa exatamente a porta que o Render exige!
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
