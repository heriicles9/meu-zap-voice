import os
import requests
from flask import Flask, request, jsonify
import pymongo

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI") # Ele vai pegar a mesma senha do Render

# --- CONEXÃO BANCO ---
try:
    client = pymongo.MongoClient(MONGO_URI)
except:
    client = None

def enviar_mensagem(instancia, numero, texto):
    url = f"{EVO_URL}/message/sendText/{instancia}"
    headers = {"apikey": EVO_KEY}
    data = {"number": numero, "text": texto}
    requests.post(url, json=data, headers=headers)

@app.route('/webhook', methods=['POST'])
def webhook():
    if not client: return jsonify({"erro": "Sem banco de dados"}), 500
    
    dados = request.json
    
    # 1. Verifica se é uma mensagem nova chegando
    if dados.get('event') == 'messages.upsert':
        instancia = dados.get('instance')
        msg_data = dados.get('data', {}).get('message', {})
        key = dados.get('data', {}).get('key', {})
        
        # Ignora mensagens enviadas por você mesmo (para não dar loop)
        if key.get('fromMe'):
            return jsonify({"status": "ignorado"}), 200
            
        numero = key.get('remoteJid')
        
        # Extrai o texto que o cliente digitou
        texto_recebido = ""
        if "conversation" in msg_data:
            texto_recebido = msg_data["conversation"]
        elif "extendedTextMessage" in msg_data:
            texto_recebido = msg_data["extendedTextMessage"]["text"]
            
        if not texto_recebido:
            return jsonify({"status": "sem texto"}), 200
            
        # --- LÓGICA DE CONVERSA (O CÉREBRO) ---
        db = client["zapvoice_db"]
        fluxo_doc = db["fluxos"].find_one({"_id": instancia})
        
        if not fluxo_doc or not fluxo_doc.get("blocos"):
            return jsonify({"status": "fluxo vazio"}), 200
            
        blocos = fluxo_doc["blocos"]
        
        # Busca em qual passo (bloco) este cliente específico está
        sessao = db["sessoes"].find_one({"numero": numero, "instancia": instancia})
        bloco_atual = None
        
        if not sessao:
            # Cliente novo! Pega o PRIMEIRO bloco da sua lista
            bloco_atual = blocos[0]
            db["sessoes"].insert_one({"numero": numero, "instancia": instancia, "bloco_id": bloco_atual["id"]})
        else:
            # Cliente já está conversando. Vamos ver o que ele respondeu!
            bloco_id_atual = sessao["bloco_id"]
            bloco_atual = next((b for b in blocos if b["id"] == bloco_id_atual), None)
            
            if bloco_atual:
                proximo_id = None
                
                # Se ele estava num MENU, verifica se ele digitou o nome do botão
                if bloco_atual["tipo"] == "Menu":
                    opcoes = bloco_atual.get("opcoes", "").split("\n")
                    for op in opcoes:
                        if ">" in op:
                            botao, destino = op.split(">")
                            # Ex: Se ele digitou "Vendas" ou "1" e bater com o botão
                            if texto_recebido.strip().lower() == botao.strip().lower():
                                proximo_id = destino.strip()
                                break
                                
                # Se ele estava num TEXTO comum, vai direto pro próximo bloco
                elif bloco_atual["tipo"] == "Texto":
                    proximo_id = bloco_atual.get("opcoes", "").strip()
                    
                # Se achou o próximo destino, avança o cliente de casa!
                if proximo_id:
                    novo_bloco = next((b for b in blocos if b["id"] == proximo_id), None)
                    if novo_bloco:
                        bloco_atual = novo_bloco
                        # Salva no banco que ele andou pra frente
                        db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"bloco_id": bloco_atual["id"]}})
        
        # Envia a mensagem do bloco atual para o WhatsApp dele!
        if bloco_atual:
            enviar_mensagem(instancia, numero, bloco_atual["msg"])
            
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
