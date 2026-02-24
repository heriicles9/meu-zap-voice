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
    return "ZapFluxo v2.5 Online 🚀"

# --- FUNÇÃO DA IA COM ESCUDO ---
def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    texto_historico = "\n".join(historico_lista)
    regra_fuga = ""
    if condicao_saida:
        regra_fuga = f"\n\nORDEM SECRETA: Se o cliente {condicao_saida}, você DEVE adicionar EXATAMENTE a palavra [MUDAR_BLOCO] no final da sua resposta."
    
    prompt = f"Você é um assistente de WhatsApp. Siga estas regras:\n{treinamento}{regra_fuga}\n\nHistórico:\n{texto_historico}\n\nSua resposta:"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        
        # TENTATIVA 2 SE DER ERRO 429 (LIMITE DE VELOCIDADE)
        if res.status_code == 429:
            time.sleep(3)
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            
        if res.status_code == 200:
            texto = res.json()['candidates'][0]['content']['parts'][0]['text']
            return texto.replace("João:", "").replace("Assistente:", "").strip()
        else:
            return "😅 [Opa, recebi muitas mensagens ao mesmo tempo. Pode repetir em 1 minutinho?]"
    except:
        return "🤖 [Falha na conexão com a inteligência central]"

def enviar_mensagem(instancia, numero, texto, tipo="text", b64="", legenda=""):
    headers = {"apikey": EVO_KEY}
    
    # Simula digitando...
    requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json={"number": numero, "delay": 2000, "presence": "composing"}, headers=headers)
    time.sleep(2)
    
    if tipo == "text":
        url = f"{EVO_URL}/message/sendText/{instancia}"
        payload = {"number": numero, "textMessage": {"text": texto}, "options": {"delay": 0, "presence": "composing"}}
    elif tipo == "audio":
        url = f"{EVO_URL}/message/sendWhatsAppAudio/{instancia}"
        payload = {"number": numero, "audioMessage": {"audio": b64}}
    elif tipo == "media":
        url = f"{EVO_URL}/message/sendMedia/{instancia}"
        payload = {"number": numero, "mediaMessage": {"mediatype": "image", "caption": legenda, "media": b64}}
    
    requests.post(url, json=payload, headers=headers)

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
        
        if not texto_cliente:
            return jsonify({"status": "no_text"}), 200

        # RESETAR CONVERSA
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
                        if texto_cliente.strip() == btn.strip():
                            proximo_id = dst.strip()
            elif bloco_atual["tipo"] != "Robô IA":
                proximo_id = bloco_atual.get("opcoes")
            
            if proximo_id:
                bloco_atual = next((b for b in fluxo_doc["blocos"] if b["id"] == proximo_id), bloco_atual)
                db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})

        # PROCESSAR RESPOSTA
        if bloco_atual["tipo"] == "Robô IA":
            historico = sessao.get("historico", [])
            historico.append(f"Cliente: {texto_cliente}")
            historico = historico[-10:] # Mantém apenas as últimas 10
            
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
