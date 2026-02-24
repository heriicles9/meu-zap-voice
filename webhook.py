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

# 🚨 CHAVE SEGURA NO RENDER
GEMINI_KEY = os.environ.get("GEMINI_KEY")

try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') 
    print("✅ Banco OK!")
except Exception as e:
    client = None

@app.route('/', methods=['GET'])
def home(): return "<h1>🧠 Cérebro do ZapFluxo v2.0 (Com Variáveis e Roteamento) ⚡</h1>"

# --- FUNÇÃO DA IA ---
def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    
    texto_historico = "\n".join(historico_lista)
    
    # Se existir uma condição de saída, damos uma ordem extra secreta para a IA
    regra_fuga = f"\n\nORDEM SECRETA: Se o cliente {condicao_saida}, você DEVE adicionar EXATAMENTE a palavra [MUDAR_BLOCO] no final da sua resposta." if condicao_saida else ""
    
    prompt = f"Você é um assistente de WhatsApp. Siga ESTRITAMENTE estas regras:\n{treinamento}{regra_fuga}\n\nVeja o histórico da conversa abaixo e responda de forma natural.\n\nHISTÓRICO:\n{texto_historico}\n\nSua resposta:"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].replace("João:", "").replace("Assistente:", "").strip()
        return f"🤖 [Erro do Google! Código: {res.status_code}]"
    except Exception as e:
        return f"🤖 [Falha neural: {e}]"

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

# --- ROTEADOR ---
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
            
            # 🚨 MÁGICA 1: PEGANDO O NOME DO CLIENTE!
            nome_cliente = dados.get('data', {}).get('pushName', 'Cliente')
                
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
                db["sessoes"].insert_one({"numero": numero_db, "instancia": instancia, "bloco_id": bloco_atual["id"], "historico": []})
                sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
            else:
                bloco_id_atual = sessao["bloco_id"]
                bloco_atual = next((b for b in blocos if b["id"] == bloco_id_atual), None)
                
                if bloco_atual:
                    proximo_id = None
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
            
            if bloco_atual:
                if bloco_atual["tipo"] == "Robô IA":
                    historico = sessao.get("historico", [])
                    historico.append(f"Cliente: {texto_recebido}")
                    historico = historico[-10:]
                    
                    # 🚨 MÁGICA 2: FUGA DO LOOP
                    opcoes_ia = bloco_atual.get("opcoes", "")
                    condicao = opcoes_ia.split("|")[0] if "|" in opcoes_ia else ""
                    destino = opcoes_ia.split("|")[1] if "|" in opcoes_ia else ""
                    
                    resposta_inteligente = consultar_gemini(bloco_atual["msg"], historico, condicao)
                    
                    deve_mudar = False
                    if "[MUDAR_BLOCO]" in resposta_inteligente:
                        resposta_inteligente = resposta_inteligente.replace("[MUDAR_BLOCO]", "").strip()
                        deve_mudar = True
                    
                    # 🚨 Troca a tag {nome} pelo nome real antes de enviar
                    resposta_inteligente = resposta_inteligente.replace("{nome}", nome_cliente)
                    historico.append(f"IA: {resposta_inteligente}")
                    
                    db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"historico": historico}})
                    enviar_mensagem(instancia, numero_exato, resposta_inteligente)
                    
                    if deve_mudar and destino:
                        # Muda o bloco silenciosamente para a próxima interação ou manda o bloco seguinte logo
                        db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": destino}})
                        
                elif bloco_atual["tipo"] == "Áudio":
                    b64 = bloco_atual.get("arquivo_b64", "")
                    if b64: enviar_audio(instancia, numero_exato, b64)
                elif bloco_atual["tipo"] == "Imagem":
                    b64 = bloco_atual.get("arquivo_b64", "")
                    # Troca a tag {nome} na legenda da foto
                    legenda = bloco_atual.get("msg", "").replace("{nome}", nome_cliente)
                    if b64: enviar_imagem(instancia, numero_exato, b64, legenda)
                else:
                    # Troca a tag {nome} no texto e menu normais
                    texto_formatado = bloco_atual["msg"].replace("{nome}", nome_cliente)
                    enviar_mensagem(instancia, numero_exato, texto_formatado)
                
    except Exception as e:
        traceback.print_exc()
        
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=porta)
