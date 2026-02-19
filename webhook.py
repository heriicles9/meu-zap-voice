import os
import requests
from flask import Flask, request, jsonify
import pymongo

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")

# --- CONEXÃO BANCO ---
try:
    client = pymongo.MongoClient(MONGO_URI)
    print("✅ Conectado ao MongoDB no Cérebro!")
except Exception as e:
    client = None
    print("❌ Erro no MongoDB:", e)

def enviar_mensagem(instancia, numero, texto):
    url = f"{EVO_URL}/message/sendText/{instancia}"
    headers = {"apikey": EVO_KEY}
    
    data = {
        "number": numero, 
        "textMessage": {
            "text": texto
        }
    }
    
    print(f"📤 Tentando enviar mensagem para {numero}: {texto}")
    res = requests.post(url, json=data, headers=headers)
    print(f"📠 Resposta da API ao enviar: {res.status_code} - {res.text}")

@app.route('/webhook', methods=['POST'])
def webhook():
    if not client: return jsonify({"erro": "Sem banco"}), 500
    
    dados = request.json
    print("\n=========================================")
    print("🚨 RAIO-X MÁXIMO ATIVADO! PACOTE COMPLETO:")
    print(dados) # ISSO AQUI VAI MOSTRAR TODOS OS DADOS ESCONDIDOS
    print("=========================================\n")
    
    evento = dados.get('event', '')
    
    if evento.lower() == 'messages.upsert':
        instancia = dados.get('instance')
        msg_data = dados.get('data', {}).get('message', {})
        key = dados.get('data', {}).get('key', {})
        
        if key.get('fromMe'):
            return jsonify({"status": "ignorado"}), 200
            
        numero = key.get('remoteJid')
        
        texto_recebido = ""
        if "conversation" in msg_data:
            texto_recebido = msg_data["conversation"]
        elif "extendedTextMessage" in msg_data:
            texto_recebido = msg_data["extendedTextMessage"]["text"]
            
        if not texto_recebido:
            return jsonify({"status": "sem texto"}), 200
            
        db = client["zapvoice_db"]
        fluxo_doc = db["fluxos"].find_one({"_id": instancia})
        
        if not fluxo_doc or not fluxo_doc.get("blocos"):
            return jsonify({"status": "fluxo vazio"}), 200
            
        blocos = fluxo_doc["blocos"]
        sessao = db["sessoes"].find_one({"numero": numero, "instancia": instancia})
        bloco_atual = None
        
        if not sessao:
            bloco_atual = blocos[0]
            db["sessoes"].insert_one({"numero": numero, "instancia": instancia, "bloco_id": bloco_atual["id"]})
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
                elif bloco_atual["tipo"] == "Texto":
                    proximo_id = bloco_atual.get("opcoes", "").strip()
                    
                if proximo_id:
                    novo_bloco = next((b for b in blocos if b["id"] == proximo_id), None)
                    if novo_bloco:
                        bloco_atual = novo_bloco
                        db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})
        
        if bloco_atual:
            enviar_mensagem(instancia, numero, bloco_atual["msg"])
            
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
