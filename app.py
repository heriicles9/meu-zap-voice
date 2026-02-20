import streamlit as st
import time
import pymongo
import os
import graphviz
import requests
import base64

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="ZapVoice SaaS", layout="wide", page_icon="🤖")

# --- CONEXÃO BANCO (Movida para cima para o Login funcionar) ---
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

# --- SISTEMA DE LOGIN MULTI-USUÁRIO (SaaS) ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""

if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    
    with col_centro:
        st.title("☁️ ZapVoice Plataforma")
        st.write("Acesse ou crie a conta da sua empresa.")
        
        if not client:
            st.error("🚨 Banco de dados desconectado. Verifique a variável MONGO_URI.")
            st.stop()
            
        db = client["zapvoice_db"]
        colecao_users = db["usuarios"]
        
        tab_login, tab_registro = st.tabs(["🔑 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            with st.container(border=True):
                user_login = st.text_input("Usuário da Empresa", key="ulogin").lower().strip()
                pass_login = st.text_input("Senha", type="password", key="plogin")
                if st.button("Entrar no Painel", type="primary", use_container_width=True):
                    if user_login and pass_login:
                        user_data = colecao_users.find_one({"_id": user_login, "senha": pass_login})
                        if user_data:
                            st.session_state["logado"] = True
                            st.session_state["usuario"] = user_login
                            st.rerun()
                        else:
                            st.error("❌ Usuário ou senha incorretos!")
                            
        with tab_registro:
            with st.container(border=True):
                st.write("Crie um nome curto, sem espaços (Ex: *lojadojoao*)")
                user_reg = st.text_input("Novo Usuário", key="ureg").lower().strip()
                pass_reg = st.text_input("Criar Senha", type="password", key="preg")
                if st.button("Criar e Entrar", type="primary", use_container_width=True):
                    if user_reg and pass_reg:
                        # Verifica se o nome já existe ou tem espaço
                        if " " in user_reg:
                            st.error("❌ O nome de usuário não pode ter espaços!")
                        elif colecao_users.find_one({"_id": user_reg}):
                            st.error("❌ Esse usuário já existe! Escolha outro nome.")
                        else:
                            # Salva o novo cliente no banco
                            colecao_users.insert_one({"_id": user_reg, "senha": pass_reg})
                            st.session_state["logado"] = True
                            st.session_state["usuario"] = user_reg
                            st.success("✅ Conta criada com sucesso! Entrando...")
                            time.sleep(1)
                            st.rerun()
                            
    st.stop() # Bloqueia todo o resto do código para quem não está logado!
# --- FIM DO SISTEMA DE LOGIN ---

# --- CREDENCIAIS DA EVOLUTION API ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"

# 🚨 TRAVA DE SEGURANÇA: O projeto_id agora é o nome do usuário logado!
projeto_id = st.session_state["usuario"]

# --- FUNÇÕES DB ---
def carregar_fluxo_db(proj_id):
    if not client: return []
    db = client["zapvoice_db"]
    doc = db["fluxos"].find_one({"_id": proj_id})
    return doc.get("blocos", []) if doc else []

def salvar_fluxo_db(proj_id, lista_blocos):
    if not client: return False
    db = client["zapvoice_db"]
    db["fluxos"].update_one(
        {"_id": proj_id}, 
        {"$set": {"blocos": lista_blocos, "updated_at": time.time()}}, 
        upsert=True
    )
    return True

# --- FUNÇÕES DO WHATSAPP (EVOLUTION API) ---
def obter_qr_code(proj_id):
    headers = {"apikey": EVO_KEY}
    instancia = proj_id.replace(" ", "").replace("-", "")
    
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

def ativar_webhook(proj_id):
    headers = {"apikey": EVO_KEY}
    instancia = proj_id.replace(" ", "").replace("-", "")
    data = {
        "enabled": True,
        "url": WEBHOOK_URL,
        "webhookByEvents": False,
        "events": ["MESSAGES_UPSERT"]
    }
    try:
        res = requests.post(f"{EVO_URL}/webhook/set/{instancia}", json=data, headers=headers)
        return res.status_code in [200, 201]
    except:
        return False

# --- SIDEBAR (O NOVO MENU DO CLIENTE) ---
with st.sidebar:
    st.header("👤 Meu Perfil")
    st.write(f"Empresa conectada: **{projeto_id}**")
    
    if st.button("🔄 Sincronizar Dados", use_container_width=True):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.rerun()
        
    st.divider()
    
    # Botão de Sair
    if st.button("🚪 Sair do Painel", use_container_width=True):
        st.session_state["logado"] = False
        st.session_state["usuario"] = ""
        st.rerun()

# --- ESTADO E MEMÓRIA ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id)
if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None
if 'num_opcoes' not in st.session_state:
    st.session_state.num_opcoes = 2 

# --- HEADER COM O QR CODE E WEBHOOK ---
c1, c2, c3 = st.columns([2.5, 1, 1.5])

with c1:
    st.title("ZapVoice Builder 🤖☁️")
    st.caption(f"Trabalhando no cérebro de: **{projeto_id}**")
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
                if ativar_webhook(projeto_id):
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
            
            col_titulo, col_add, col_rem = st.columns([2, 1, 1])
            with col_titulo:
                st.write("🔘 **Botões de Resposta**")
            with col_add:
                if st.button("➕ Mais", use_container_width=True):
                    st.session_state.num_opcoes += 1
                    st.rerun()
            with col_rem:
                if st.button("➖ Menos", use_container_width=True) and st.session_state.num_opcoes > 1:
                    st.session_state.num_opcoes -= 1
                    st.rerun()

            linhas = val_opcoes.split("\n") if val_opcoes else []
            b_vals, d_vals = [], []
            for linha in linhas:
                if ">" in linha:
                    b_vals.append(linha.split(">")[0].strip())
                    d_vals.append(linha.split(">")[1].strip())

            while len(b_vals) < st.session_state.num_opcoes:
                b_vals.append("")
                d_vals.append("")

            col_btn, col_dest = st.columns(2)
            lista_opcoes = []
            
            for idx in range(st.session_state.num_opcoes):
                with col_btn:
                    btn_val = st.text_input(f"Opção {idx+1}", value=b_vals[idx], key=f"input_btn_{idx}")
                with col_dest:
                    dest_val = st.text_input(f"Destino {idx+1}", value=d_vals[idx], key=f"input_dest_{idx}")
                
                if btn_val and dest_val:
                    lista_opcoes.append(f"{btn_val.strip()} > {dest_val.strip()}")
            
            routing = "\n".join(lista_opcoes)
            
        else: # Tipo TEXTO
            content = st.text_area("Mensagem de Texto", value=val_msg)
            routing = st.text_input("Próximo ID Automático", value=val_opcoes)

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            if bid and content:
                novo = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
                if st.session_state.indice_edicao is not None:
                    st.session_state.fluxo[st.session_state.indice_edicao] = novo
                    st.session_state.indice_edicao = None
                else:
                    st.session_state.fluxo.append(novo)
                
                salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                st.session_state.num_opcoes = 2 
                st.rerun()

with col_visual:
    tab1, tab2 = st.tabs(["📋 Lista", "🕸️ Mapa Visual"])
    with tab1:
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(b['msg'])
                c_e, c_d = st.columns(2)
                if c_e.button("Editar", key=f"btn_edit_{i}"):
                    st.session_state.indice_edicao = i
                    if b['tipo'] == 'Menu':
                        qtd = len([l for l in b.get('opcoes', '').split('\n') if '>' in l])
                        st.session_state.num_opcoes = max(1, qtd)
                    st.rerun()
                if c_d.button("Excluir", key=f"btn_del_{i}"):
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
