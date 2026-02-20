import streamlit as st
import time
import pymongo
import os
import graphviz
import requests
import base64

# --- SISTEMA DE LOGIN (CADEADO) ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🔒 Acesso Restrito")
    st.write("Painel de Controle do Robô")
    
    senha = st.text_input("Digite a senha de administrador:", type="password")
    if st.button("Entrar"):
        if senha == "mestra123":  # 🔑 Você pode mudar a sua senha aqui!
            st.session_state["logado"] = True
            st.rerun()
        else:
            st.error("❌ Senha incorreta!")
    st.stop() # Isso faz uma barreira mágica: nada do código abaixo roda sem a senha!
# --- FIM DO LOGIN ---

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="ZapVoice Builder", layout="wide", page_icon="🤖")

# --- CREDENCIAIS DA EVOLUTION API ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"

# --- URL DO SEU WEBHOOK (CÉREBRO) ---
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"

# --- CONEXÃO BANCO ---
@st.cache_resource
def init_connection():
    try:
        uri = os.environ.get("MONGO_URI") 
        if not uri and "MONGO_URI" in st.secrets:
            uri = st.secrets["MONGO_URI"]
        if not uri: return None
        return pymongo.MongoClient(uri)
    except: return None

client = init_connection()

# --- FUNÇÕES DB ---
def carregar_fluxo_db(projeto_id):
    if not client: return []
    db = client["zapvoice_db"]
    doc = db["fluxos"].find_one({"_id": projeto_id})
    return doc.get("blocos", []) if doc else []

def salvar_fluxo_db(projeto_id, lista_blocos):
    if not client: return False
    db = client["zapvoice_db"]
    db["fluxos"].update_one(
        {"_id": projeto_id}, 
        {"$set": {"blocos": lista_blocos, "updated_at": time.time()}}, 
        upsert=True
    )
    return True

# --- FUNÇÕES DO WHATSAPP (EVOLUTION API) ---
def obter_qr_code(projeto_id):
    headers = {"apikey": EVO_KEY}
    instancia = projeto_id.replace(" ", "").replace("-", "")
    
    try:
        data = {"instanceName": instancia, "qrcode": True, "token": instancia}
        res_create = requests.post(f"{EVO_URL}/instance/create", json=data, headers=headers)
        
        if res_create.status_code in [200, 201]:
            dados = res_create.json()
            if "qrcode" in dados and "base64" in dados["qrcode"]:
                return dados["qrcode"]["base64"]
        
        time.sleep(1)
        res_conn = requests.get(f"{EVO_URL}/instance/connect/{instancia}", headers=headers)
        
        if res_conn.status_code == 200:
            dados_conn = res_conn.json()
            if "base64" in dados_conn:
                return dados_conn["base64"]
                
        return f"ERRO API: {res_create.status_code} | {res_conn.text}"
            
    except Exception as e:
        return f"ERRO SISTEMA: {e}"
        
    return None

def ativar_webhook(projeto_id):
    headers = {"apikey": EVO_KEY}
    instancia = projeto_id.replace(" ", "").replace("-", "")
    
    data = {
        "enabled": True,
        "url": WEBHOOK_URL,
        "webhookByEvents": False,
        "events": ["MESSAGES_UPSERT"]
    }
    
    try:
        res = requests.post(f"{EVO_URL}/webhook/set/{instancia}", json=data, headers=headers)
        if res.status_code in [200, 201]:
            return True
        return False
    except:
        return False

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acesso")
    projeto_id = st.text_input("ID do Projeto / Cliente", value="demoteste")
    if st.button("🔄 Sincronizar Dados"):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.rerun()

# --- ESTADO ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id)
if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- HEADER COM O QR CODE E WEBHOOK ---
c1, c2, c3 = st.columns([2.5, 1, 1.5])

with c1:
    st.title("ZapVoice Builder 🤖☁️")
    st.caption(f"Projeto Ativo: **{projeto_id}**")
with c2:
    if client: st.success("🟢 DB ON")
    else: st.error("🔴 DB OFF")
with c3:
    with st.popover("📲 Conectar WhatsApp", use_container_width=True):
        st.write("### Conectar Sessão")
        
        if st.button("1. Gerar QR Code Real", use_container_width=True):
            with st.spinner("Ligando o motor..."):
                qr_b64 = obter_qr_code(projeto_id)
                
                if qr_b64 and not qr_b64.startswith("ERRO"):
                    if "," in qr_b64:
                        qr_b64 = qr_b64.split(",")[1]
                    st.image(base64.b64decode(qr_b64), caption="Escaneie agora!", use_container_width=True)
                    st.success("Motor conectado! Tudo pronto.")
                else:
                    st.error("Falha ao buscar QR Code.")
                    if qr_b64: st.code(qr_b64)
                    
        st.divider()
        
        if st.button("2. 🎧 Ativar Robô (Webhook)", use_container_width=True, type="primary"):
            with st.spinner("Conectando Cérebro ao Motor..."):
                sucesso = ativar_webhook(projeto_id)
                if sucesso:
                    st.success("Robô ativado! Ele já está ouvindo as mensagens.")
                else:
                    st.error("Erro ao ativar. Verifique se o celular já leu o QR Code.")

st.divider()

# --- EDITOR E VISUALIZAÇÃO ---
col_editor, col_visual = st.columns([1, 1.5])

val_id, val_msg, val_opcoes, val_tipo_index = "", "", "", 0
if st.session_state.indice_edicao is not None:
    try:
        b = st.session_state.fluxo[st.session_state.indice_edicao]
        val_id, val_msg, val_opcoes = b['id'], b['msg'], b.get('opcoes', '')
        tipos = ["Texto", "Menu", "Áudio"]
        val_tipo_index = tipos.index(b['tipo']) if b['tipo'] in tipos else 0
    except: st.session_state.indice_edicao = None

with col_editor:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        bid = st.text_input("ID do Bloco", value=val_id)
        btype = st.selectbox("Tipo", ["Texto", "Menu", "Áudio"], index=val_tipo_index)
        
        content, routing = "", ""
        if btype == "Áudio":
            upl = st.file_uploader("Arquivo", type=['mp3','ogg'])
            content = f"[Audio] {upl.name}" if upl else val_msg
            routing = st.text_input("Próximo ID Automático", value=val_opcoes)
            
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg)
            st.write("---")
            st.write("🔘 **Configurar Botões de Resposta**")
            
            # Mágica para preencher as caixinhas quando for "Editar" um bloco existente
            linhas = val_opcoes.split("\n") if val_opcoes else []
            b_vals, d_vals = ["", "", ""], ["", "", ""]
            for idx, linha in enumerate(linhas):
                if idx < 3 and ">" in linha:
                    b_vals[idx] = linha.split(">")[0].strip()
                    d_vals[idx] = linha.split(">")[1].strip()

            # Desenha as colunas
            col1, col2 = st.columns(2)
            with col1:
                st.write("**O que o cliente digita:**")
                btn1 = st.text_input("Opção 1 (Ex: 1)", value=b_vals[0], key="b1")
                btn2 = st.text_input("Opção 2 (Ex: 2)", value=b_vals[1], key="b2")
                btn3 = st.text_input("Opção 3 (Ex: 3)", value=b_vals[2], key="b3")
                
            with col2:
                st.write("**Para qual bloco ele vai:**")
                dest1 = st.text_input("Destino 1 (Ex: vendas)", value=d_vals[0], key="d1")
                dest2 = st.text_input("Destino 2 (Ex: suporte)", value=d_vals[1], key="d2")
                dest3 = st.text_input("Destino 3 (Ex: atendente)", value=d_vals[2], key="d3")

            # Junta tudo para salvar no banco do jeito que o cérebro entende
            lista_opcoes = []
            if btn1 and dest1: lista_opcoes.append(f"{btn1.strip()} > {dest1.strip()}")
            if btn2 and dest2: lista_opcoes.append(f"{btn2.strip()} > {dest2.strip()}")
            if btn3 and dest3: lista_opcoes.append(f"{btn3.strip()} > {dest3.strip()}")
            
            routing = "\n".join(lista_opcoes)
            
        else: # Tipo TEXTO
            content = st.text_area("Mensagem de Texto", value=val_msg)
            routing = st.text_input("Próximo ID", value=val_opcoes)

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            if bid and content:
                novo = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
                if st.session_state.indice_edicao is not None:
                    st.session_state.fluxo[st.session_state.indice_edicao] = novo
                    st.session_state.indice_edicao = None
                else:
                    st.session_state.fluxo.append(novo)
                salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                st.rerun()

with col_visual:
    tab1, tab2 = st.tabs(["📋 Lista", "🕸️ Mapa Visual"])
    with tab1:
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(b['msg'])
                c_e, c_d = st.columns(2)
                if c_e.button("Editar", key=f"e{i}"):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if c_d.button("Excluir", key=f"d{i}"):
                    st.session_state.fluxo.pop(i)
                    salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                    st.rerun()
    with tab2:
        if st.session_state.fluxo:
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR')
            for b in st.session_state.fluxo:
                dot.node(b['id'], f"{b['id']}\n({b['tipo']})", shape="rect")
                if b.get('opcoes'):
                    for l in b['opcoes'].split('\n'):
                        if ">" in l:
                            orig, dest = l.split(">")[0].strip(), l.split(">")[1].strip()
                            dot.edge(b['id'], dest, label=orig)
                        elif l.strip():
                            dot.edge(b['id'], l.strip())
            st.graphviz_chart(dot)
