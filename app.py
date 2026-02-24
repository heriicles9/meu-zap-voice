import streamlit as st
import time
import pymongo
import os
import graphviz
import requests
import base64

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="ZapFluxo SaaS", layout="wide", page_icon="⚡")

# --- CONEXÃO BANCO ---
@st.cache_resource
def init_connection():
    try:
        uri = os.environ.get("MONGO_URI") 
        if not uri and "MONGO_URI" in st.secrets: uri = st.secrets["MONGO_URI"]
        if not uri: return None
        return pymongo.MongoClient(uri)
    except: return None

client = init_connection()

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""

if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    with col_centro:
        st.title("☁️ Plataforma ZapFluxo")
        st.write("Acesse ou crie a conta da sua empresa.")
        
        if not client:
            st.error("🚨 Banco de dados desconectado.")
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
                        if colecao_users.find_one({"_id": user_login, "senha": pass_login}):
                            st.session_state["logado"] = True
                            st.session_state["usuario"] = user_login
                            st.rerun()
                        else: st.error("❌ Usuário ou senha incorretos!")
                            
        with tab_registro:
            with st.container(border=True):
                user_reg = st.text_input("Novo Usuário", key="ureg").lower().strip()
                pass_reg = st.text_input("Criar Senha", type="password", key="preg")
                if st.button("Criar e Entrar", type="primary", use_container_width=True):
                    if user_reg and pass_reg:
                        if " " in user_reg: st.error("❌ O nome não pode ter espaços!")
                        elif colecao_users.find_one({"_id": user_reg}): st.error("❌ Esse usuário já existe!")
                        else:
                            colecao_users.insert_one({"_id": user_reg, "senha": pass_reg})
                            st.session_state["logado"] = True
                            st.session_state["usuario"] = user_reg
                            st.rerun()
    st.stop()

# --- CREDENCIAIS ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"
projeto_id = st.session_state["usuario"]

# --- FUNÇÕES DB ---
def carregar_fluxo_db(proj_id):
    if not client: return []
    doc = client["zapvoice_db"]["fluxos"].find_one({"_id": proj_id})
    return doc.get("blocos", []) if doc else []

def salvar_fluxo_db(proj_id, lista_blocos):
    if not client: return False
    client["zapvoice_db"]["fluxos"].update_one({"_id": proj_id}, {"$set": {"blocos": lista_blocos, "updated_at": time.time()}}, upsert=True)
    return True

# --- FUNÇÕES API ---
def obter_qr_code(proj_id):
    headers = {"apikey": EVO_KEY}
    instancia = proj_id.replace(" ", "").replace("-", "")
    try:
        res_create = requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia, "qrcode": True, "token": instancia}, headers=headers)
        if res_create.status_code in [200, 201]:
            dados = res_create.json()
            if "qrcode" in dados and "base64" in dados["qrcode"]: return dados["qrcode"]["base64"]
        time.sleep(1)
        res_conn = requests.get(f"{EVO_URL}/instance/connect/{instancia}", headers=headers)
        if res_conn.status_code == 200 and "base64" in res_conn.json(): return res_conn.json()["base64"]
        return f"ERRO API"
    except: return None

def ativar_webhook(proj_id):
    headers = {"apikey": EVO_KEY}
    instancia = proj_id.replace(" ", "").replace("-", "")
    try: return requests.post(f"{EVO_URL}/webhook/set/{instancia}", json={"enabled": True, "url": WEBHOOK_URL, "webhookByEvents": False, "events": ["MESSAGES_UPSERT"]}, headers=headers).status_code in [200, 201]
    except: return False

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Meu Perfil")
    st.write(f"Empresa conectada: **{projeto_id}**")
    if st.button("🔄 Sincronizar Dados", use_container_width=True):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.rerun()
    st.divider()
    if st.button("🚪 Sair do Painel", use_container_width=True):
        st.session_state["logado"] = False
        st.session_state["usuario"] = ""
        st.rerun()

if 'fluxo' not in st.session_state: st.session_state.fluxo = carregar_fluxo_db(projeto_id)
if 'indice_edicao' not in st.session_state: st.session_state.indice_edicao = None
if 'num_opcoes' not in st.session_state: st.session_state.num_opcoes = 2 

c1, c2, c3 = st.columns([2.5, 1, 1.5])
with c1: 
    st.title("ZapFluxo Builder ⚡☁️")
    
with c2: 
    if client:
        st.success("🟢 ON")
    else 
        st.error("🔴 OFF")
        
with c3:
    with st.popover("📲 Conectar WhatsApp", use_container_width=True):
        if st.button("1. Gerar QR Code Real", use_container_width=True):
            qr = obter_qr_code(projeto_id)
            if qr and not qr.startswith("ERRO"): st.image(base64.b64decode(qr.split(",")[1] if "," in qr else qr), caption="Escaneie!")
        if st.button("2. 🎧 Ativar Robô", use_container_width=True, type="primary"):
            st.success("Robô ativado!") if ativar_webhook(projeto_id) else st.error("Erro")
st.divider()

col_editor, col_visual = st.columns([1, 1.5])
val_id, val_msg, val_opcoes, val_tipo_index = "", "", "", 0

# 🚨 ADICIONAMOS A OPÇÃO DE "ROBÔ IA" AQUI!
tipos = ["Texto", "Menu", "Áudio", "Imagem", "Robô IA"]

if st.session_state.indice_edicao is not None:
    try:
        b = st.session_state.fluxo[st.session_state.indice_edicao]
        val_id, val_msg, val_opcoes = b['id'], b.get('msg', ''), b.get('opcoes', '')
        val_tipo_index = tipos.index(b['tipo']) if b['tipo'] in tipos else 0
    except: st.session_state.indice_edicao = None

with col_editor:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        bid = st.text_input("ID do Bloco", value=val_id)
        btype = st.selectbox("Tipo", tipos, index=val_tipo_index)
        
        content, routing = "", ""
        upl = None
        
        if btype == "Robô IA":
            st.info("🧠 A IA assumirá a conversa neste bloco.")
            content = st.text_area("Comportamento da IA (Ex: Você é o atendente da Pizzaria, venda a pizza X...)", value=val_msg, height=150)
            routing = "" # A IA não tem próximo bloco, ela conversa em loop até o cliente resetar
            
        elif btype == "Áudio":
            upl = st.file_uploader("Arquivo", type=['mp3','ogg'])
            content = f"🎵 Novo Áudio" if upl else val_msg
            routing = st.text_input("Próximo ID", value=val_opcoes)
            
        elif btype == "Imagem":
            upl = st.file_uploader("Foto", type=['png', 'jpg', 'jpeg'])
            content = st.text_area("Legenda", value=val_msg if not val_msg.startswith("📸") else "")
            if not content and not upl and val_msg: content = val_msg
            routing = st.text_input("Próximo ID", value=val_opcoes)
            
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg)
            if st.button("➕"): st.session_state.num_opcoes += 1
            linhas = val_opcoes.split("\n") if val_opcoes else []
            b_vals, d_vals = [l.split(">")[0].strip() for l in linhas if ">" in l], [l.split(">")[1].strip() for l in linhas if ">" in l]
            while len(b_vals) < st.session_state.num_opcoes: b_vals.append(""); d_vals.append("")
            
            opcoes_temp = []
            for i in range(st.session_state.num_opcoes):
                c_btn, c_dst = st.columns(2)
                v1, v2 = c_btn.text_input(f"Opção {i+1}", value=b_vals[i], key=f"b_{i}"), c_dst.text_input(f"Destino {i+1}", value=d_vals[i], key=f"d_{i}")
                if v1 and v2: opcoes_temp.append(f"{v1} > {v2}")
            routing = "\n".join(opcoes_temp)
            
        else: # Texto
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("Próximo ID", value=val_opcoes)

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            if bid:
                novo = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
                if btype in ["Áudio", "Imagem"]:
                    if upl: novo["arquivo_b64"] = base64.b64encode(upl.read()).decode('utf-8')
                    elif st.session_state.indice_edicao is not None: novo["arquivo_b64"] = st.session_state.fluxo[st.session_state.indice_edicao].get("arquivo_b64", "")
                    if btype == "Imagem" and not content: novo["msg"] = "📸 [Sem legenda]"
                
                if st.session_state.indice_edicao is not None: st.session_state.fluxo[st.session_state.indice_edicao] = novo
                else: st.session_state.fluxo.append(novo)
                
                salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                st.session_state.indice_edicao = None
                st.rerun()

with col_visual:
    t1, t2 = st.tabs(["📋 Lista", "🕸️ Mapa"])
    with t1:
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(b['msg'])
                ce, cd = st.columns(2)
                if ce.button("Editar", key=f"e_{i}"): st.session_state.indice_edicao = i; st.rerun()
                if cd.button("Excluir", key=f"d_{i}"): st.session_state.fluxo.pop(i); salvar_fluxo_db(projeto_id, st.session_state.fluxo); st.rerun()
    with t2:
        if st.session_state.fluxo:
            dot = graphviz.Digraph(engine='dot')
            dot.attr(rankdir='LR')
            for b in st.session_state.fluxo:
                dot.node(b['id'], f"{b['id']}\n({b['tipo']})", shape="rect")
                if b.get('opcoes'):
                    for l in b['opcoes'].split('\n'):
                        if ">" in l: dot.edge(b['id'], l.split(">")[1].strip(), label=l.split(">")[0].strip())
                        elif l.strip(): dot.edge(b['id'], l.strip())
            st.graphviz_chart(dot)
