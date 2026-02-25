import os
import requests
import pymongo
import time
import traceback
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURAÇÕES DE AMBIENTE ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
MONGO_URI = os.environ.get("MONGO_URI")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# Conexão Global com o Banco de Dados
try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client["zapvoice_db"]
except Exception as e:
    print(f"Erro ao conectar ao MongoDB: {e}")
    client = None

@app.route('/')
def home():
    return "ZapFluxo v5.0 - Motor de Webhook e Pagamentos Online 🚀"

# 💰 --- WEBHOOK DO ASAAS (Pagamentos Automáticos) ---
@app.route('/asaas', methods=['POST'])
def webhook_asaas():
    try:
        dados = request.json
        evento = dados.get("event")
        
        # Filtra apenas quando o dinheiro é confirmado ou recebido
        if evento in ["PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"]:
            payment_obj = dados.get("payment", {})
            
            # O Asaas pode mandar o email direto no payment ou dentro de customer
            email_cliente = payment_obj.get("email")
            if not email_cliente:
                email_cliente = payment_obj.get("customer", {}).get("email")
                
            if email_cliente:
                email_cliente = email_cliente.lower().strip()
                
                # Dá 400 dias de acesso (Plano Anual + Margem)
                data_liberada = datetime.datetime.now() + datetime.timedelta(days=400)
                
                # Atualiza no Banco de Dados
                resultado = db["usuarios"].update_one(
                    {"email": email_cliente},
                    {
                        "$set": {
                            "plano_ativo": True, 
                            "vencimento_teste": data_liberada
                        }
                    }
                )
                
                if resultado.modified_count > 0:
                    print(f"💰 SUCESSO: Plano Pro ativado para o email: {email_cliente}")
                else:
                    print(f"⚠️ AVISO: Pagamento de {email_cliente} recebido, mas usuário não achado no BD.")
                    
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Erro no webhook do Asaas: {e}")
        return jsonify({"status": "error"}), 500


# --- FUNÇÕES DE APOIO (WhatsApp e IA) ---

def simular_acao_ia(instancia, numero):
    url = f"{EVO_URL}/chat/sendPresence/{instancia}"
    headers = {"apikey": EVO_KEY}
    payload = {
        "number": numero, 
        "delay": 15000, 
        "presence": "composing"
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=2)
    except:
        pass # Ignora erros de timeout aqui para não travar o fluxo

def consultar_gemini(treinamento, historico_lista, condicao_saida=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    texto_historico = "\n".join(historico_lista)
    
    regra_fuga = ""
    if condicao_saida:
        regra_fuga = f"\n\nORDEM SECRETA: Se o cliente {condicao_saida}, você DEVE adicionar EXATAMENTE a palavra [MUDAR_BLOCO] no final da sua resposta."
        
    prompt = f"Você é um assistente de WhatsApp. Siga estas regras:\n{treinamento}{regra_fuga}\n\nHistórico da conversa:\n{texto_historico}\n\nSua resposta:"
    
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    
    for tentativa in range(3):
        try:
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            if res.status_code == 200:
                texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                # Limpa marcações que a IA pode inventar
                texto_limpo = texto.replace("João:", "").replace("Assistente:", "").replace("Bot:", "").strip()
                return texto_limpo
            elif res.status_code == 429:
                time.sleep(4) # Espera se der limite de requisições do Google
        except Exception as e:
            print(f"Erro ao consultar Gemini (Tentativa {tentativa+1}): {e}")
            time.sleep(2)
            
    return "😅 [Opa, o sistema deu uma congestionada aqui. Pode repetir?]"

def obter_base64_da_mensagem(instancia, data_obj):
    url = f"{EVO_URL}/chat/getBase64FromMediaMessage/{instancia}"
    headers = {"apikey": EVO_KEY}
    payload = {"message": data_obj}
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            b64 = res.json().get("base64", "")
            if "," in b64:
                return b64.split(",")[1]
            return b64
    except Exception as e:
        print(f"Erro ao baixar mídia da Evolution: {e}")
        
    return None

def transcrever_audio(audio_b64):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": "Transcreva exatamente o que o cliente disse neste áudio, ignorando ruídos. Responda APENAS com a transcrição em texto."},
                {"inline_data": {"mimeType": "audio/ogg", "data": audio_b64}}
            ]
        }]
    }
    
    try:
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Erro na transcrição de áudio: {e}")
        
    return "[Falha na transcrição do áudio]"

def enviar_mensagem(instancia, numero, texto, tipo="text", b64="", legenda=""):
    headers = {"apikey": EVO_KEY}
    
    # Se não for uma resposta de IA (que já simulou o digitando), simula um digitando rápido
    if tipo != "ia_digitou":
        payload_presence = {"number": numero, "delay": 2000, "presence": "composing"}
        requests.post(f"{EVO_URL}/chat/sendPresence/{instancia}", json=payload_presence, headers=headers)
        time.sleep(2)
    
    # Executa o envio real de acordo com o tipo
    if tipo == "text" or tipo == "ia_digitou":
        payload = {"number": numero, "textMessage": {"text": texto}}
        requests.post(f"{EVO_URL}/message/sendText/{instancia}", json=payload, headers=headers)
        
    elif tipo == "audio":
        payload = {"number": numero, "audioMessage": {"audio": b64}}
        requests.post(f"{EVO_URL}/message/sendWhatsAppAudio/{instancia}", json=payload, headers=headers)
        
    elif tipo == "media":
        payload = {
            "number": numero, 
            "mediaMessage": {
                "mediatype": "image", 
                "caption": legenda, 
                "media": b64
            }
        }
        requests.post(f"{EVO_URL}/message/sendMedia/{instancia}", json=payload, headers=headers)


# 📲 --- WEBHOOK PRINCIPAL (Recepção do WhatsApp) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.json
        
        # Ignora tudo que não for mensagem nova
        if dados.get('event') != 'messages.upsert': 
            return jsonify({"status": "ignored_event"}), 200
        
        instancia = dados.get('instance')
        data = dados.get('data', {})
        key = data.get('key', {})
        
        # Ignora mensagens enviadas por você mesmo
        if key.get('fromMe'): 
            return jsonify({"status": "from_me_ignored"}), 200
            
        numero_jid = key.get('remoteJid', '')
        numero_db = numero_jid.split('@')[0]
        nome_cliente = data.get('pushName', 'Cliente')
        msg_obj = data.get('message', {})
        
        # Captura texto simples ou texto de resposta (quote)
        texto_cliente = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""
        
        # LOG VISUAL NO RENDER PARA FÁCIL DEBUG
        print(f"--------------------------------------------------")
        print(f"📩 INSTÂNCIA: {instancia}")
        print(f"👤 CLIENTE: {numero_db} ({nome_cliente})")
        print(f"💬 TEXTO: {texto_cliente}")
        print(f"--------------------------------------------------")

        # Verifica se é áudio e faz a transcrição
        if "audioMessage" in str(msg_obj):
            print("🎙️ Áudio detectado. Baixando e transcrevendo...")
            b64_audio = obter_base64_da_mensagem(instancia, data)
            if b64_audio:
                texto_cliente = transcrever_audio(b64_audio)
                print(f"📝 Transcrição final: {texto_cliente}")
            else:
                texto_cliente = "[O cliente enviou um áudio, mas falhou ao baixar]"

        # Comando secreto de Reset
        if texto_cliente.lower() == "reset":
            db["sessoes"].delete_one({"numero": numero_db, "instancia": instancia})
            enviar_mensagem(instancia, numero_jid, "🔄 Sua conversa foi resetada com sucesso!")
            return jsonify({"status": "reset"}), 200

        # 🚨 BUSCA INTELIGENTE DO FLUXO (Tratamento de Case Sensitive e Nomes compostos)
        fluxo_doc = db["fluxos"].find_one({
            "$or": [
                {"_id": instancia},
                {"_id": instancia.lower()},
                {"nome_projeto": instancia},
                {"_id": {"$regex": f"_{instancia}$", "$options": "i"}}
            ]
        })

        if not fluxo_doc:
            print(f"❌ ERRO CRÍTICO: Nenhum fluxo foi encontrado no Banco para a Instância '{instancia}'")
            return jsonify({"status": "no_flow_found"}), 200
            
        blocos = fluxo_doc.get("blocos", [])
        if not blocos:
            print(f"⚠️ AVISO: Fluxo encontrado, mas a pasta está vazia (sem blocos salvos).")
            return jsonify({"status": "empty_flow"}), 200
        
        # GERENCIAMENTO DE SESSÃO DO CLIENTE
        sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
        
        # Se for o primeiro contato do cliente
        if not sessao:
            bloco_atual = blocos[0]
            db["sessoes"].insert_one({
                "numero": numero_db, 
                "instancia": instancia, 
                "bloco_id": bloco_atual["id"], 
                "historico": [],
                "nome_personalizado": nome_cliente
            })
            sessao = db["sessoes"].find_one({"numero": numero_db, "instancia": instancia})
            
        # Se ele já está conversando
        else:
            # Encontra onde ele estava parado
            bloco_atual = None
            for b in blocos:
                if b["id"] == sessao["bloco_id"]:
                    bloco_atual = b
                    break
            
            # Prevenção de erro se o bloco que ele estava foi deletado do painel
            if not bloco_atual:
                bloco_atual = blocos[0]
                
            proximo_id = None
            
            # Lógica para descobrir para onde ele vai agora
            if bloco_atual["tipo"] == "Menu":
                opcoes_menu = bloco_atual.get("opcoes", "")
                for linha in opcoes_menu.split("\n"):
                    if ">" in linha:
                        partes = linha.split(">")
                        texto_botao = partes[0].strip().lower()
                        destino_id = partes[1].strip()
                        
                        if texto_cliente.strip().lower() == texto_botao:
                            proximo_id = destino_id
                            break
                            
            elif bloco_atual["tipo"] != "Robô IA":
                # Se for Texto, Audio ou Imagem, ele segue o fluxo reto
                proximo_id = bloco_atual.get("opcoes")
            
            # Atualiza a sessão para o próximo bloco, se houver caminho
            if proximo_id:
                for b in blocos:
                    if b["id"] == proximo_id:
                        bloco_atual = b
                        db["sessoes"].update_one(
                            {"_id": sessao["_id"]}, 
                            {"$set": {"bloco_id": bloco_atual["id"]}}
                        )
                        break

        # APLICA NOME PERSONALIZADO SE HOUVER NO CRM
        nome_cliente_crm = sessao.get("nome_personalizado", nome_cliente)

        # PROCESSAMENTO DE ENVIO CONFORME O TIPO DO BLOCO ATUAL
        tipo = bloco_atual.get("tipo")
        
        if tipo == "Robô IA":
            # 1. Avisa o cliente que está digitando (longo)
            simular_acao_ia(instancia, numero_jid)
            
            # 2. Prepara a memória
            historico = sessao.get("historico", [])
            historico.append(f"Cliente: {texto_cliente}")
            historico = historico[-10:] # Guarda só as últimas 10 para não estourar limite
            
            # 3. Analisa Gatilho de Fuga
            opcoes_ia = bloco_atual.get("opcoes", "")
            condicao_fuga = ""
            destino_fuga = ""
            
            if "|" in opcoes_ia:
                partes_ia = opcoes_ia.split("|")
                condicao_fuga = partes_ia[0].strip()
                if len(partes_ia) > 1:
                    destino_fuga = partes_ia[1].strip()
            
            # 4. Consulta a IA
            resposta_ia = consultar_gemini(bloco_atual["msg"], historico, condicao_fuga)
            
            # 5. Verifica se a IA acionou a fuga
            mudar_de_bloco = False
            if "[MUDAR_BLOCO]" in resposta_ia:
                mudar_de_bloco = True
                
            # 6. Limpa a resposta final
            resposta_ia = resposta_ia.replace("[MUDAR_BLOCO]", "").replace("{nome}", nome_cliente_crm).strip()
            
            # 7. Salva a resposta da IA no histórico
            historico.append(f"Bot: {resposta_ia}")
            db["sessoes"].update_one(
                {"_id": sessao["_id"]}, 
                {"$set": {"historico": historico}}
            )
            
            # 8. Envia a mensagem no WhatsApp
            enviar_mensagem(instancia, numero_jid, resposta_ia, tipo="ia_digitou")
            
            # 9. Executa a mudança de bloco se necessário
            if mudar_de_bloco and destino_fuga:
                db["sessoes"].update_one(
                    {"_id": sessao["_id"]}, 
                    {"$set": {"bloco_id": destino_fuga}}
                )

        elif tipo == "Áudio":
            arquivo_base64 = bloco_atual.get("arquivo_b64", "")
            enviar_mensagem(instancia, numero_jid, "", "audio", arquivo_base64)
            
        elif tipo == "Imagem":
            arquivo_base64 = bloco_atual.get("arquivo_b64", "")
            legenda_formatada = bloco_atual.get("msg", "").replace("{nome}", nome_cliente_crm)
            enviar_mensagem(instancia, numero_jid, "", "media", arquivo_base64, legenda_formatada)
            
        else:
            # Tipo "Texto" padrão
            texto_formatado = bloco_atual.get("msg", "").replace("{nome}", nome_cliente_crm)
            enviar_mensagem(instancia, numero_jid, texto_formatado)

    except Exception as e:
        print("❌ ERRO FATAL NO WEBHOOK:")
        traceback.print_exc()
        
    return jsonify({"status": "success"}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
