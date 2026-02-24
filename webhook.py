import os, requests, pymongo, time, traceback, datetime
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
    return "ZapFluxo v3.4 (SaaS + Asaas Auto-Pay) Online 🚀💰"

# 💰 --- ROTA NOVA: WEBHOOK DO ASAAS ---
@app.route('/asaas', methods=['POST'])
def webhook_asaas():
    try:
        dados = request.json
        evento = dados.get("event")
        
        # Filtra apenas pagamentos confirmados ou recebidos
        if evento in ["PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"]:
            payment_obj = dados.get("payment", {})
            # Tenta pegar o e-mail do cliente (onde o Asaas guarda)
            email_cliente = payment_obj.get("email") or payment_obj.get("customer", {}).get("email")
            
            if email_cliente:
                email_cliente = email_cliente.lower().strip()
                # Define uma data de expiração bem longa (ex: 400 dias) para quem pagou
                data_liberada = datetime.datetime.now() + datetime.timedelta(days=400)
                
                # Procura o usuário pelo e-mail e ativa o plano
                resultado = db["usuarios"].update_one(
                    {"email": email_cliente},
                    {"$set": {"plano_ativo": True, "vencimento_teste": data_liberada}}
                )
                
                if resultado.modified_count > 0:
                    print(f"💰 SUCESSO: Plano ativado para {email_cliente}")
                    return jsonify({"status": "ativado"}), 200
                else:
                    print(f"⚠️ AVISO: Pagamento recebido de {email_cliente}, mas e-mail não achado no banco.")
                    return jsonify({"status": "usuario_nao_encontrado"}), 200
                    
        return jsonify({"status": "evento_ignorado"}), 200
    except:
        traceback.print_exc()
        return jsonify({"status": "erro_interno"}), 500

# --- FUNÇÕES DE IA E WHATSAPP ---

def simular_acao_ia(instancia, numero, tempo_ms=15000):
    url = f"{EVO_URL}/chat/sendPresence/{instancia}"
    headers = {"apikey": EVO_KEY}
    payload = {"number": numero, "delay": tempo_ms, "presence": "composing"}
    try:
        requests.post(url, json=payload, headers=headers, timeout=2)
    except:
        pass

def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
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
        except:
            time.sleep(2)
    return "😅 [Opa, o sistema deu uma congestionada aqui. Pode repetir?]"

def obter_base64_da_mensagem(instancia, mensagem_obj):
    url = f"{EVO_URL}/chat/getBase64FromMediaMessage/{instancia}"
    headers = {"apikey": EVO_KEY}
    try:
        res = requests.post(url, json={"message": mensagem_obj}, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            b64 = res.json().get("base64", "")
            return b64.split(",")[1] if "," in b64 else b64
    except:
        pass
    return None

def transcrever_audio(audio_b64):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": "Transcreva este áudio. Responda APENAS o texto."}, {"inline_data": {"mimeType": "audio/ogg", "data": audio_b64}}]}]}
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        return "[Falha na transcrição]"

def enviar_mensagem(instancia, numero, texto, tipo="text", b64="", legenda=""):
    headers = {"apikey": EVO_KEY}
    if tipo != "ia_ja_digitou":
        requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "delay": 2000, "presence": "composing"}, headers=headers)
        time.sleep(2)
    
    if tipo in ["text", "ia_ja_digitou"]:
        requests.post(f"{EVO_URL}/message/sendText/{instancia}", json={"number": numero, "textMessage": {"text": texto}}, headers=headers)
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
        if key.get('fromMe'): return jsonify({"status": "from_me"}), 200
            
        numero_jid = key.get('remoteJid', '')
        numero_db = numero_jid.split('@')[0]
        nome_cliente = data.get('pushName', 'Cliente')
        msg_obj = data.get('message', {})
        texto_cliente = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""
        
        if not texto_cliente and "audioMessage" in str(msg_obj):
            b64_audio = obter_base64_da_mensagem(instancia, data)
            texto_cliente = transcrever_audio(b64_audio) if b64_audio else "[Áudio não baixado]"

        if texto_cliente.lower() == "reset":
            db["sessoes"].delete_one({"numero": numero_db, "instancia": instancia})
            enviar_mensagem(instancia, numero_jid, "🔄 Conversa resetada!")
            return jsonify({"status": "reset"}), 200

        fluxo_doc = db["fluxos"].find_one({"_id": instancia})
        if not fluxo_doc: return jsonify({"status": "no_flow"}), 200
        
        sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
        if not sessao:
            bloco_atual = fluxo_doc["blocos"][0]
            db["sessoes"].insert_one({"numero": numero_db, "instancia": instancia, "bloco_id": bloco_atual["id"], "historico": []})
            sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
        else:
            bloco_atual = next((b for b in fluxo_doc["blocos"] if b["id"] == sessao["bloco_id"]), fluxo_doc["blocos"][0])
            proximo_id = None
            if bloco_atual["tipo"] == "Menu":
                for linha in bloco_atual["opcoes"].split("\n"):
                    if ">" in linha:
                        btn, dst = linha.split(">")
                        if texto_cliente.strip().lower() == btn.strip().lower(): proximo_id = dst.strip()
            elif bloco_atual["tipo"] != "Robô IA":
                proximo_id = bloco_atual.get("opcoes")
            
            if proximo_id:
                bloco_atual = next((b for b in fluxo_doc["blocos"] if b["id"] == proximo_id), bloco_atual)
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})

        if sessao.get("nome_personalizado"): nome_cliente = sessao.get("nome_personalizado")

        if bloco_atual["tipo"] == "Robô IA":
            simular_acao_ia(instancia, numero_jid)
            historico = sessao.get("historico", [])
            historico.append(f"Cliente: {texto_cliente}")
            historico = historico[-10:]
            
            condicao, destino = ("", "")
            if "|" in bloco_atual["opcoes"]: condicao, destino = bloco_atual["opcoes"].split("|")
            
            resposta_ia = consultar_gemini(bloco_atual["msg"], historico, condicao)
            mudar_bloco = "[MUDAR_BLOCO]" in resposta_ia
            resposta_ia = resposta_ia.replace("[MUDAR_BLOCO]", "").replace("{nome}", nome_cliente).strip()
            
            historico.append(f"João: {resposta_ia}")
            db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"historico": historico}})
            enviar_mensagem(instancia, numero_jid, resposta_ia, tipo="ia_ja_digitou")
            
            if mudar_bloco and destino:
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": destino.strip()}})
        elif bloco_atual["tipo"] == "Áudio":
            enviar_mensagem(instancia, numero_jid, "", "audio", bloco_atual.get("arquivo_b64"))
        elif bloco_atual["tipo"] == "Imagem":
            enviar_mensagem(instancia, numero_jid, "", "media", bloco_atual.get("arquivo_b64"), bloco_atual["msg"].replace("{nome}", nome_cliente))
        else:
            enviar_mensagem(instancia, numero_jid, bloco_atual["msg"].replace("{nome}", nome_cliente))

    except:
        traceback.print_exc()
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
