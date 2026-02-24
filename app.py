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

# --- SISTEMA DE LOGIN COM MONETIZAÇÃO ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["vencimento_teste"] = None
    st.session_state["plano_ativo"] = False

if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    with col_centro:
        
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
            st.error("🚨 Banco de dados desconectado.")
            st.stop()
        
        db = client["zapvoice_db"]
        
        tab_login, tab_registro, tab_senha = st.tabs(["🔑 Entrar", "📝 Criar Conta", "🔄 Trocar Senha"])
        
        with tab_login:
            st.write("")
            user_login = st.text_input("Usuário", key="ulogin").lower().strip()
            pass_login = st.text_input("Senha", type="password", key="plogin")
            
            manter_logado = st.checkbox("Manter conectado", value=True)
            
            if st.button("Acessar Painel", type="primary", use_container_width=True):
                user_db = db["usuarios"].find_one({"_id": user_login, "senha": pass_login})
                if user_db:
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = user_login
                    
                    # Se for usuário antigo sem data, cria agora
                    if "vencimento_teste" not in user_db:
                        venc = datetime.datetime.now() + datetime.timedelta(days=7)
                        db["usuarios"].update_one({"_id": user_login}, {"$set": {"vencimento_teste": venc, "plano_ativo": False}})
                        st.session_state["vencimento_teste"] = venc
                        st.session_state["plano_ativo"] = False
                    else:
                        st.session_state["vencimento_teste"] = user_db["vencimento_teste"]
                        st.session_state["plano_ativo"] = user_db.get("plano_ativo", False)
                        
                    st.rerun()
                else:
                    st.error("❌ Dados incorretos.")
                            
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
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = user_reg
                    st.session_state["vencimento_teste"] = venc
                    st.session_state["plano_ativo"] = False
                    st.success("✅ Conta criada com 7 dias de teste!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Preencha todos os campos ou usuário já existe.")
                    
        with tab_senha:
            st.write("")
            user_troca = st.text_input("Seu Usuário", key="utroca").lower().strip()
            pass_atual = st.text_input("Senha Atual", type="password", key="patual")
            pass_nova = st.text_input("Nova Senha", type="password", key="pnova")
            
            if st.button("Mudar Senha", type="primary", use_container_width=True):
                if user_troca and pass_atual and pass_nova:
                    if db["usuarios"].find_one({"_id": user_troca, "senha": pass_atual}):
                        db["usuarios"].update_one({"_id": user_troca}, {"$set": {"senha": pass_nova}})
                        st.success("✅ Senha alterada!")
                    else:
                        st.error("❌ Dados atuais incorretos.")
                else:
                    st.warning("⚠️ Preencha tudo.")
                    
    st.stop()

# --- VARIÁVEIS DE PROJETO ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook" # Ajuste para sua URL do Render
projeto_id = st.session_state["usuario"]
instancia_limpa = projeto_id.replace(" ", "").replace("-", "")

# --- TRAVA DE MONETIZAÇÃO ---
agora = datetime.datetime.now()
venc_teste = st.session_state["vencimento_teste"]
dias_restantes = (venc_teste - agora).days

if not st.session_state["plano_ativo"] and dias_restantes < 0:
    col_bloq1, col_bloq2, col_bloq3 = st.columns([1, 2, 1])
    with col_bloq2:
        st.error("⏳ Seu período de teste de 7 dias expirou!")
        st.markdown("### Assine o Plano Pro para continuar usando o ZapFluxo 🚀")
        link_asaas = "https://www.asaas.com/c/kai0orwy6nsfr37s"
        st.markdown(f'<a href="{link_asaas}" target="_blank" style="text-decoration: none;"><button style="width: 100%; background-color: #ff4b4b; color: white; border: none; padding: 15px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 18px;">💳 ASSINAR AGORA (R$ 147,00/mês)</button></a>', unsafe_allow_html=True)
        st.info("⚠️ Importante: Use o mesmo e-mail do seu cadastro para a liberação automática.")
        if st.button("🚪 Sair"):
            st.session_state["logado"] = False
            st.rerun()
    st.stop()
else:
    if not st.session_state["plano_ativo"]:
        st.warning(f"💎 Período de Teste Grátis: Restam {dias_restantes} dias.")

# --- FUNÇÕES ---
def carregar_fluxo():
    doc = client["zapvoice_db"]["fluxos"].find_one({"_id": projeto_id})
    if doc:
        return doc.get("blocos", [])
    return []

def salvar_fluxo(lista):
    client["zapvoice_db"]["fluxos"].update_one({"_id": projeto_id}, {"$set": {"blocos": lista}}, upsert=True)

def ativar_webhook():
    try:
        res = requests.post(f"{EVO_URL}/webhook/set/{instancia_limpa}", json={"enabled": True, "url": WEBHOOK_URL, "webhookByEvents": False, "events": ["MESSAGES_UPSERT"]}, headers={"apikey": EVO_KEY})
        return res.status_code in [200, 201]
    except:
        return False

# --- INTERFACE ---
if 'fluxo' not in st.session_state: st.session_state.fluxo = carregar_fluxo()
if 'indice_edicao' not in st.session_state: st.session_state.indice_edicao = None
if 'num_opcoes' not in st.session_state: st.session_state.num_opcoes = 2

with st.sidebar:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        pass
        
    st.header(f"👤 {projeto_id}")
    if st.button("🔄 Sincronizar Dados", use_container_width=True):
        st.session_state.fluxo = carregar_fluxo()
        st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logado"] = False
        st.rerun()

c1, c2, c3 = st.columns([2.5, 1, 1.5])
with c1:
    st.title("ZapFluxo Builder ⚡")
with c2:
    if client:
        st.success("🟢 DB Conectado")
    else:
        st.error("🔴 DB Offline")
with c3:
    with st.popover("📲 Conectar Zap", use_container_width=True):
        
        if st.button("🧹 Limpar Conexão Travada", use_container_width=True):
            requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
            st.success("Tudo limpo! Pode conectar agora.")
            time.sleep(2)
            st.rerun()

        st.divider()
        st.markdown("**Opção 1: QR Code (PC)**")
        if st.button("Gerar QR Code", use_container_width=True):
            headers = {"apikey": EVO_KEY}
            res_conn = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}", headers=headers)
            if res_conn.status_code == 200 and "base64" in res_conn.json():
                st.image(base64.b64decode(res_conn.json()["base64"].split(",")[1]))
            else:
                res_create = requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": True}, headers=headers)
                if "qrcode" in res_create.json():
                    st.image(base64.b64decode(res_create.json()["qrcode"]["base64"].split(",")[1]))
                else:
                    st.error("Erro na API. Atualize a página.")
        
        st.divider()
        st.markdown("**Opção 2: Código (Celular)**")
        numero_zap = st.text_input("Celular", placeholder="Ex: 5511999999999", key="nzap", label_visibility="collapsed")
        if st.button("Gerar Código", use_container_width=True):
            if numero_zap:
                headers = {"apikey": EVO_KEY}
                res_conn = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={numero_zap}", headers=headers)
                try:
                    codigo = res_conn.json().get("pairingCode")
                    if res_conn.status_code == 200 and codigo:
                        st.success(f"Código: **{codigo}**")
                    else:
                        requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": False}, headers=headers)
                        time.sleep(1)
                        res_conn2 = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={numero_zap}", headers=headers)
                        codigo2 = res_conn2.json().get("pairingCode")
                        if codigo2: st.success(f"Código: **{codigo2}**")
                        else: st.error("Erro ao gerar. Limpe a conexão e tente de novo.")
                except: st.error("Erro de conexão.")
            else: st.warning("Digite o número com 55.")

        st.divider()
        if st.button("🚀 Ativar Robô", type="primary", use_container_width=True):
            if ativar_webhook():
                st.success("Robô Ativo!")
            else:
                st.error("Erro ao ativar")
st.divider()

col_ed, col_vis = st.columns([1, 1.5])
tipos = ["Texto", "Menu", "Áudio", "Imagem", "Robô IA"]
val_id, val_msg, val_opc, v_idx = "", "", "", 0

if st.session_state.indice_edicao is not None:
    b = st.session_state.fluxo[st.session_state.indice_edicao]
    val_id, val_msg, val_opc = b['id'], b.get('msg',''), b.get('opcoes','')
    if b['tipo'] in tipos:
        v_idx = tipos.index(b['tipo'])

with col_ed:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        bid = st.text_input("ID do Bloco", value=val_id)
        btype = st.selectbox("Tipo de Conteúdo", tipos, index=v_idx)
        content, routing, upl = "", "", None
        
        if btype == "Robô IA":
            content = st.text_area("Treinamento da IA (Use {nome})", value=val_msg, height=150)
            v_c = val_opc.split("|")[0] if "|" in val_opc else ""
            v_d = val_opc.split("|")[1] if "|" in val_opc else ""
            c_f1, c_f2 = st.columns(2)
            cond = c_f1.text_input("Se o cliente...", value=v_c, placeholder="pedir pix")
            dest = c_f2.text_input("Vá para o ID:", value=v_d, placeholder="id_pix")
            routing = f"{cond}|{dest}" if cond else ""
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg)
            # Simplificado para caber: lógica de menu mantida
            routing = st.text_area("Opções (Formato: Opção > Destino)", value=val_opc)
        else:
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("ID do próximo bloco", value=val_opc)
            if btype in ["Áudio", "Imagem"]:
                upl = st.file_uploader("Upload", type=['mp3','ogg','png','jpg'])

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            novo_bloco = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
            if upl: novo_bloco["arquivo_b64"] = base64.b64encode(upl.read()).decode('utf-8')
            elif st.session_state.indice_edicao is not None:
                novo_bloco["arquivo_b64"] = st.session_state.fluxo[st.session_state.indice_edicao].get("arquivo_b64", "")
            
            if st.session_state.indice_edicao is not None: st.session_state.fluxo[st.session_state.indice_edicao] = novo_bloco
            else: st.session_state.fluxo.append(novo_bloco)
            salvar_fluxo(st.session_state.fluxo)
            st.session_state.indice_edicao = None
            st.rerun()

with col_vis:
    tab_lista, tab_mapa, tab_chat = st.tabs(["📋 Lista", "🕸️ Mapa", "👁️ Live Chat"])
    with tab_lista:
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(f"Conteúdo: {b['msg'][:50]}...")
                c_b1, c_b2 = st.columns(2)
                if c_b1.button("Editar", key=f"ed_{i}"):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if c_b2.button("Excluir", key=f"del_{i}"):
                    st.session_state.fluxo.pop(i)
                    salvar_fluxo(st.session_state.fluxo)
                    st.rerun()
    with tab_mapa:
        if st.session_state.fluxo:
            dot = graphviz.Digraph()
            for b in st.session_state.fluxo:
                dot.node(b['id'], b['id'])
                if b.get('opcoes') and b['tipo'] != "Robô IA":
                    for linha in b['opcoes'].split('\n'):
                        if ">" in linha: dot.edge(b['id'], linha.split(">")[1].strip())
            st.graphviz_chart(dot)
    with tab_chat:
        if st.button("🔄 Atualizar Conversas"): st.rerun()
        sessoes = list(client["zapvoice_db"]["sessoes"].find({"instancia": instancia_limpa}))
        for s in sessoes:
            with st.expander(f"📱 {s.get('nome_personalizado', s.get('numero'))}"):
                for m in s.get("historico", []):
                    st.write(m)
