import os
import requests
from flask import Flask, request, jsonify
import pymongo
import traceback

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")

# --- CONEXÃO BANCO ---
try:
    client = pymongo.MongoClient(MONGO_URI)
    print("✅ Banco de Dados OK!")
except Exception as e:
    client = None
    print(f"❌ Erro no Banco: {e}")

def enviar_mensagem(instancia, numero, texto):
    url = f"{EVO_URL}/message/sendText/{instancia}"
    headers = {"apikey": EVO_KEY}
    
    data = {
        "number": numero, 
        "textMessage": {
            "text": texto
        }
    }
    print(f"📤 Tentando enviar para: {numero} | Texto: {texto}")
    res = requests.post(url, json=data, headers=headers)
    print(f"📠 Resposta da API: {res.status_code} - {res.text}")

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
            
            if key.get('fromMe'):
                return jsonify({"status": "ignorado"}), 200
                
            # 🚨 BUSCANDO O NÚMERO COM SEGURANÇA MÁXIMA
            numero_bruto = dados.get('data', {}).get('sender', '')
            if not numero_bruto:
                numero_bruto = key.get('remoteJid', '')
                
            # Limpa tudo que vier depois do @ para pegar só o telefone
            numero_real = numero_bruto.split('@')[0] if '@' in numero_bruto else numero_bruto
            
            print(f"🕵️‍♂️ NÚMERO EXTRAÍDO: {numero_real} (Original que chegou: {numero_bruto})")
            
            texto_recebido = ""
            if "conversation" in msg_data:
                texto_recebido = msg_data["conversation"]
            elif "extendedTextMessage" in msg_data:
                texto_recebido = msg_data["extendedTextMessage"]["text"]
                
            print(f"💬 Mensagem recebida: '{texto_recebido}'")
                
            if not texto_recebido:
                return jsonify({"status": "sem texto"}), 200
                
            db = client["zapvoice_db"]
            fluxo_doc = db["fluxos"].find_one({"_id": instancia})
            
            if not fluxo_doc or not fluxo_doc.get("blocos"):
                print("❌ Gaveta de blocos vazia ou projeto não encontrado no DB.")
                return jsonify({"status": "fluxo vazio"}), 200
                
            blocos = fluxo_doc["blocos"]
            sessao = db["sessoes"].find_one({"numero": numero_real, "instancia": instancia})
            bloco_atual = None
            
            if not sessao:
                print("🆕 Cliente novo detectado!")
                bloco_atual = blocos[0]
                db["sessoes"].insert_one({"numero": numero_real, "instancia": instancia, "bloco_id": bloco_atual["id"]})
            else:
                bloco_id_atual = sessao["bloco_id"]
                print(f"🔄 Cliente voltando. Ele estava no bloco '{bloco_id_atual}'")
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
                enviar_mensagem(instancia, numero_real, bloco_atual["msg"])
                
    except Exception as e:
        print(f"💥 ERRO GRAVE NO PYTHON: {e}")
        traceback.print_exc() # Isso vai mostrar a linha exata do erro!
        
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
