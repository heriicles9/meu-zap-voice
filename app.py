import streamlit as st
import time
import pymongo
import os
import graphviz
import requests
import base64
import datetime

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="ZapFluxo SaaS", layout="wide", page_icon="⚡")

# --- CONEXÃO BANCO ---
@st.cache_resource
def init_connection():
    try:
        uri = os.environ.get("MONGO_URI") 
        if not uri and "MONGO_URI" in st.secrets: uri = st.secrets["MONGO_URI"]
        if uri:
            return pymongo.MongoClient(uri)
        return None
    except:
        return None

client = init_connection()

# --- SISTEMA DE LOGIN E SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.update({
        "logado": False,
        "usuario": "",
        "vencimento_teste": None,
        "plano_ativo": False
    })

if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    with col_centro:
        # LOGO CENTRALIZADA (HTML para remover botão de ampliar)
        try:
            with open("logo.png", "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(
                f"""
                <div style="display: flex; justify-content: center; margin-bottom: 20px;">
                    <img src="data:image/png;base64,{encoded_string}" width="380" style="border-radius: 15px;">
                </div>
                """,
                unsafe_allow_html=True
            )
        except:
            pass 
        
        if not client:
            st.error("🚨 Banco de dados desconectado. Verifique o MONGO_URI.")
            st.stop()
        
        db = client["zapvoice_db"]
        tab_login, tab_registro, tab_senha = st.tabs(["🔑 Entrar", "📝 Criar Conta", "🔄 Trocar Senha"])
        
        with tab_login:
            st.write("")
            user_login = st.text_input("Usuário", key="ulogin").lower().strip()
            pass_login = st.text_input("Senha", type="password", key="plogin")
            if st.button("Acessar Painel", type="primary", use_container_width=True):
                user_db = db["usuarios"].find_one({"_id": user_login, "senha": pass_login})
                if user_db:
                    st.session_state.update({
                        "logado": True,
                        "usuario": user_login,
                        "vencimento_teste": user_db.get("vencimento_teste"),
                        "plano_ativo": user_db.get("plano_ativo", False)
                    })
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")
                            
        with tab_registro:
            st.write("")
            user_reg = st.text_input("Novo Usuário", key="ureg").lower().strip()
            email_reg = st.text_input("Seu E-mail (Obrigatório)", key="ereg").lower().strip()
            pass_reg = st.text_input("Nova Senha", type="password", key="preg")
            if st.button("Criar Minha Conta", type="primary", use_container_width=True):
                if user_reg and email_reg and pass_reg and not db["usuarios"].find_one({"_id": user_reg}):
                    venc = datetime.datetime.now() + datetime.timedelta(days=7)
                    db["usuarios"].insert_one({
                        "_id": user_reg, 
                        "email": email_reg,
                        "senha": pass_reg,
                        "vencimento_teste": venc,
                        "plano_ativo": False
                    })
                    st.session_state.update({
                        "logado": True, "usuario": user_reg, 
                        "vencimento_teste": venc, "plano_ativo": False
                    })
                    st.success("✅ Conta criada com 7 dias de teste!")
                    time.sleep(1.5); st.rerun()
                else:
                    st.error("❌ Preencha todos os campos ou o usuário já existe.")
                    
        with tab_senha:
            st.write("")
            u_t = st.text_input("Usuário", key="ut").lower().strip()
            p_a = st.text_input("Senha Atual", type="password", key="pa")
            p_n = st.text_input("Nova Senha", type="password", key="pn")
            if st.button("Atualizar Senha", use_container_width=True):
                if db["usuarios"].find_one({"_id": u_t, "senha": p_a}):
                    db["usuarios"].update_one({"_id": u_t}, {"$set": {"senha": p_n}})
                    st.success("✅ Senha alterada!")
                else: st.error("❌ Dados atuais incorretos.")
    st.stop()

# --- VARIÁVEIS DE PROJETO ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook" # Ajuste se necessário
projeto_id = st.session_state["usuario"]
instancia_limpa = projeto_id.replace(" ", "").replace("-", "")
link_asaas = "https://www.asaas.com/c/kai0orwy6nsfr37s"
db = client["zapvoice_db"]

# --- CONTROLE DE PLANO E PAYWALL ---
agora = datetime.datetime.now()
venc_teste = st.session_state["vencimento_teste"]
# Converte string para datetime caso necessário (segurança para usuários antigos)
if isinstance(venc_teste, str): 
    venc_teste = datetime.datetime.fromisoformat(venc_teste.replace("Z", ""))

dias_restantes = (venc_teste - agora).days

if not st.session_state["plano_ativo"]:
    if dias_restantes < 0:
        # TELA DE BLOQUEIO (TRAVA)
        col_bloq1, col_bloq2, col_bloq3 = st.columns([1, 2, 1])
        with col_bloq2:
            st.error("⏳ Período de teste expirado!")
            st.markdown(f"""
                <div style="text-align: center; background-color: #1e1e1e; padding: 25px; border-radius: 15px; border: 1px solid #ff4b4b;">
                    <h2 style="color: white;">Opa! Seu acesso expirou.</h2>
                    <p style="color: #cccccc;">Para continuar automatizando seu WhatsApp com IA, assine o Plano Pro.</p>
                    <a href="{link_asaas}" target="_blank" style="text-decoration: none;">
                        <button style="width: 100%; background-color: #ff4b4b; color: white; border: none; padding: 15px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 18px;">
                            💳 ASSINAR AGORA (R$ 147,00/mês)
                        </button>
                    </a>
                    <p style="font-size: 12px; color: #888; margin-top: 10px;">Liberação imediata após o PIX via e-mail.</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("🚪 Sair da Conta", use_container_width=True):
                st.session_state.logado = False; st.rerun()
        st.stop()
    else:
        # BANNER DE AVISO COM BOTÃO DE ASSINATURA IMEDIATA
        c_aviso, c_link = st.columns([3, 1])
        with c_aviso:
            st.warning(f"💎 Você está no Teste Grátis. Restam **{dias_restantes} dias**. Quer liberar o acesso ilimitado?")
        with c_link:
            st.markdown(f'<a href="{link_asaas}" target="_blank" style="text-decoration:none;"><button style="width:100%;background-color:#28a745;color:white;border:none;padding:8px;border-radius:5px;cursor:pointer;font-weight:bold;">🚀 ASSINAR JÁ</button></a>', unsafe_allow_html=True)

# --- FUNÇÕES CORE ---
def carregar_fluxo():
    doc = db["fluxos"].find_one({"_id": projeto_id})
    return doc.get("blocos", []) if doc else []

def salvar_fluxo(lista):
    db["fluxos"].update_one({"_id": projeto_id}, {"$set": {"blocos": lista}}, upsert=True)

def ativar_webhook():
    try:
        res = requests.post(f"{EVO_URL}/webhook/set/{instancia_limpa}", 
            json={"enabled": True, "url": WEBHOOK_URL, "webhookByEvents": False, "events": ["MESSAGES_UPSERT"]}, 
            headers={"apikey": EVO_KEY})
        return res.status_code in [200, 201]
    except: return False

# --- INTERFACE PRINCIPAL ---
if 'fluxo' not in st.session_state: st.session_state.fluxo = carregar_fluxo()
if 'indice_edicao' not in st.session_state: st.session_state.indice_edicao = None
if 'num_opcoes' not in st.session_state: st.session_state.num_opcoes = 2

with st.sidebar:
    try: st.image("logo.png", use_container_width=True)
    except: pass
    st.header(f"👤 {projeto_id}")
    
    if not st.session_state["plano_ativo"]:
        st.markdown(f'<a href="{link_asaas}" target="_blank" style="text-decoration:none;"><button style="width:100%;background-color:#28a745;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;margin-bottom:10px;">💎 Seja Plano Pro</button></a>', unsafe_allow_html=True)
        st.divider()

    if st.button("🔄 Sincronizar", use_container_width=True):
        st.session_state.fluxo = carregar_fluxo(); st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False; st.rerun()

# --- TOPO ---
c1, c2, c3 = st.columns([2.5, 1, 1.5])
with c1: st.title("ZapFluxo Builder ⚡")
with c2: st.success("🟢 DB Ativo") if client else st.error("🔴 DB Offline")
with c3:
    with st.popover("📲 Conectar Zap", use_container_width=True):
        if st.button("🧹 Limpar Conexão", use_container_width=True):
            requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
            st.success("Limpando... Aguarde."); time.sleep(2); st.rerun()
        
        st.divider()
        st.markdown("**Opção 1: QR Code**")
        if st.button("Gerar QR Code", use_container_width=True):
            headers = {"apikey": EVO_KEY}
            res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}", headers=headers)
            if res.status_code == 200 and "base64" in res.json():
                st.image(base64.b64decode(res.json()["base64"].split(",")[1]))
            else:
                requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": True}, headers=headers)
                st.info("Instância criada. Clique em Gerar QR Code novamente.")
        
        st.divider()
        st.markdown("**Opção 2: Código**")
        n_zap = st.text_input("Número (Com 55)", placeholder="5511999999999", key="nzap", label_visibility="collapsed")
        if st.button("Gerar Código", use_container_width=True):
            if n_zap:
                res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={n_zap}", headers={"apikey": EVO_KEY})
                if "pairingCode" in res.json():
                    st.success(f"Código: **{res.json()['pairingCode']}**")
                else: st.error("Erro. Use o botão Limpar e tente novamente.")
            else: st.warning("Digite o número.")

        st.divider()
        if st.button("🚀 Ativar Robô", type="primary", use_container_width=True):
            if ativar_webhook(): st.success("Robô Ativo!")
            else: st.error("Falha ao ativar.")

st.divider()

# --- BUILDER ---
col_ed, col_vis = st.columns([1, 1.5])
tipos = ["Texto", "Menu", "Áudio", "Imagem", "Robô IA"]
val_id, val_msg, val_opc, v_idx = "", "", "", 0

if st.session_state.indice_edicao is not None:
    b = st.session_state.fluxo[st.session_state.indice_edicao]
    val_id, val_msg, val_opc = b['id'], b.get('msg',''), b.get('opcoes','')
    if b['tipo'] in tipos: v_idx = tipos.index(b['tipo'])

with col_ed:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        bid = st.text_input("ID do Bloco", value=val_id)
        btype = st.selectbox("Tipo", tipos, index=v_idx)
        
        content, routing, upl = "", "", None
        if btype == "Robô IA":
            content = st.text_area("Treinamento IA", value=val_msg, height=150)
            v_c = val_opc.split("|")[0] if "|" in val_opc else ""
            v_d = val_opc.split("|")[1] if "|" in val_opc else ""
            cf1, cf2 = st.columns(2)
            c_saida = cf1.text_input("Gatilho (ex: pix)", value=v_c)
            d_saida = cf2.text_input("ID Destino", value=v_d)
            routing = f"{c_saida}|{d_saida}" if c_saida else ""
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg)
            routing = st.text_area("Opções (Formato: Opção > ID)", value=val_opc, help="Ex: 1 > vendas\n2 > suporte")
        else:
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("ID do próximo bloco", value=val_opc)
            if btype in ["Áudio", "Imagem"]:
                upl = st.file_uploader("Arquivo", type=['mp3','ogg','png','jpg'])

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            novo = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
            if upl: novo["arquivo_b64"] = base64.b64encode(upl.read()).decode('utf-8')
            elif st.session_state.indice_edicao is not None:
                novo["arquivo_b64"] = st.session_state.fluxo[st.session_state.indice_edicao].get("arquivo_b64", "")
            
            if st.session_state.indice_edicao is not None:
                st.session_state.fluxo[st.session_state.indice_edicao] = novo
            else: st.session_state.fluxo.append(novo)
            salvar_fluxo(st.session_state.fluxo)
            st.session_state.indice_edicao = None; st.rerun()

with col_vis:
    tab_list, tab_graph, tab_crm = st.tabs(["📋 Lista de Blocos", "🕸️ Mapa de Fluxo", "👁️ Live CRM"])
    with tab_list:
        for i, blk in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {blk['id']} ({blk['tipo']})"):
                st.write(blk['msg'][:100] + "...")
                ced1, ced2 = st.columns(2)
                if ced1.button("Editar", key=f"e_{i}"):
                    st.session_state.indice_edicao = i; st.rerun()
                if ced2.button("Excluir", key=f"d_{i}"):
                    st.session_state.fluxo.pop(i); salvar_fluxo(st.session_state.fluxo); st.rerun()
    with tab_graph:
        if st.session_state.fluxo:
            dot = graphviz.Digraph()
            for b in st.session_state.fluxo:
                dot.node(b['id'], f"{b['id']}\n({b['tipo']})")
                if b.get('opcoes') and b['tipo'] != "Robô IA":
                    for l in b['opcoes'].split('\n'):
                        if ">" in l: dot.edge(b['id'], l.split(">")[1].strip())
            st.graphviz_chart(dot)
    with tab_crm:
        if st.button("🔄 Atualizar Chats"): st.rerun()
        chats = list(db["sessoes"].find({"instancia": instancia_limpa}))
        for s in chats:
            with st.expander(f"📱 {s.get('nome_personalizado', s.get('numero'))} (Bloco: {s.get('bloco_id')})"):
                for m in s.get("historico", []): st.write(m)
                if st.button("🗑️ Resetar Conversa", key=f"res_{s['_id']}"):
                    db["sessoes"].delete_one({"_id": s["_id"]}); st.rerun()
