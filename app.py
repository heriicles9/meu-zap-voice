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

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.update({
        "logado": False, "usuario": "", "vencimento_teste": None, "plano_ativo": False, "projeto_ativo": "Padrao"
    })

if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    with col_centro:
        try:
            with open("logo.png", "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(f'<div style="display:flex;justify-content:center;margin-bottom:20px;"><img src="data:image/png;base64,{encoded_string}" width="380" style="border-radius:15px;"></div>', unsafe_allow_html=True)
        except: pass 
        
        if not client:
            st.error("🚨 Banco de dados desconectado.")
            st.stop()
        
        db = client["zapvoice_db"]
        tab_login, tab_registro, tab_senha = st.tabs(["🔑 Entrar", "📝 Criar Conta", "🔄 Trocar Senha"])
        
        with tab_login:
            st.write("")
            u_l = st.text_input("Usuário", key="ulogin").lower().strip()
            p_l = st.text_input("Senha", type="password", key="plogin")
            if st.button("Acessar Painel", type="primary", use_container_width=True):
                user_db = db["usuarios"].find_one({"_id": u_l, "senha": p_l})
                if user_db:
                    st.session_state.update({
                        "logado": True, "usuario": u_l, 
                        "vencimento_teste": user_db.get("vencimento_teste"),
                        "plano_ativo": user_db.get("plano_ativo", False)
                    })
                    st.rerun()
                else: st.error("❌ Dados incorretos.")
                            
        with tab_registro:
            st.write("")
            u_r = st.text_input("Novo Usuário", key="ureg").lower().strip()
            e_r = st.text_input("Seu E-mail", key="ereg").lower().strip()
            p_r = st.text_input("Nova Senha", type="password", key="preg")
            if st.button("Criar Conta", type="primary", use_container_width=True):
                if u_r and e_r and p_r and not db["usuarios"].find_one({"_id": u_r}):
                    venc = datetime.datetime.now() + datetime.timedelta(days=7)
                    db["usuarios"].insert_one({"_id": u_r, "email": e_r, "senha": p_r, "vencimento_teste": venc, "plano_ativo": False})
                    st.session_state.update({"logado": True, "usuario": u_r, "vencimento_teste": venc, "plano_ativo": False})
                    st.success("✅ Conta criada!"); time.sleep(1); st.rerun()
                else: st.error("❌ Erro no cadastro.")
    st.stop()

# --- VARIÁVEIS DE AMBIENTE ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"
link_asaas = "https://www.asaas.com/c/kai0orwy6nsfr37s"
db = client["zapvoice_db"]

# --- FUNÇÕES DE PROJETO ---
def listar_projetos():
    projs = db["fluxos"].find({"dono": st.session_state["usuario"]})
    lista = [p["nome_projeto"] for p in projs]
    return lista if lista else ["Padrao"]

def carregar_fluxo(p_nome):
    doc = db["fluxos"].find_one({"dono": st.session_state["usuario"], "nome_projeto": p_nome})
    return doc.get("blocos", []) if doc else []

def salvar_fluxo(lista, p_nome):
    db["fluxos"].update_one(
        {"_id": f"{st.session_state['usuario']}_{p_nome}"},
        {"$set": {"dono": st.session_state["usuario"], "nome_projeto": p_nome, "blocos": lista}},
        upsert=True
    )

# --- SIDEBAR (O NOVO GERENCIADOR) ---
with st.sidebar:
    try: st.image("logo.png", use_container_width=True)
    except: pass
    
    st.divider()
    st.subheader("📁 Meus Projetos (Pastas)")
    
    lista_p = listar_projetos()
    proj_selecionado = st.selectbox("Abrir Pasta:", lista_p, index=lista_p.index(st.session_state["projeto_ativo"]) if st.session_state["projeto_ativo"] in lista_p else 0)
    
    if proj_selecionado != st.session_state["projeto_ativo"]:
        st.session_state["projeto_ativo"] = proj_selecionado
        st.session_state["fluxo"] = carregar_fluxo(proj_selecionado)
        st.rerun()

    with st.expander("➕ Nova Pasta"):
        novo_n = st.text_input("Nome da Pasta", key="n_proj_input").strip()
        if st.button("Criar Pasta"):
            if novo_n:
                salvar_fluxo([], novo_n)
                st.session_state["projeto_ativo"] = novo_n
                st.rerun()

    # MIGRAR DADOS ANTIGOS
    antigo = db["fluxos"].find_one({"_id": st.session_state["usuario"]})
    if antigo and not carregar_fluxo("Padrao"):
        if st.button("⚠️ Importar Blocos Antigos"):
            salvar_fluxo(antigo.get("blocos", []), "Padrao")
            db["fluxos"].delete_one({"_id": st.session_state["usuario"]})
            st.success("Dados migrados para a pasta Padrao!"); time.sleep(1); st.rerun()

    st.divider()
    st.header(f"👤 {st.session_state['usuario']}")
    if not st.session_state["plano_ativo"]:
        st.markdown(f'<a href="{link_asaas}" target="_blank" style="text-decoration:none;"><button style="width:100%;background-color:#28a745;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;">💎 Seja Plano Pro</button></a>', unsafe_allow_html=True)
    
    if st.button("🔄 Sincronizar"): st.rerun()
    if st.button("🚪 Sair"): st.session_state.logado = False; st.rerun()

# --- LÓGICA DE INSTÂNCIA POR PROJETO ---
# Ex: usuario_projeto -> demoteste_vendas
projeto_id_unico = f"{st.session_state['usuario']}_{st.session_state['projeto_ativo']}"
instancia_limpa = projeto_id_unico.replace(" ", "").replace("-", "").lower()

# --- TRAVA DE MONETIZAÇÃO ---
agora = datetime.datetime.now()
v_t = st.session_state["vencimento_teste"]
if isinstance(v_t, str): v_t = datetime.datetime.fromisoformat(v_t.replace("Z", ""))
dias_r = (v_t - agora).days

if not st.session_state["plano_ativo"] and dias_r < 0:
    st.error("⏳ Teste Expirado!"); st.stop()

# --- INTERFACE PRINCIPAL ---
if 'fluxo' not in st.session_state: st.session_state.fluxo = carregar_fluxo(st.session_state["projeto_ativo"])
if 'indice_edicao' not in st.session_state: st.session_state.indice_edicao = None

c1, c2, c3 = st.columns([2.5, 1, 1.5])
with c1: st.title(f"ZapFluxo: {st.session_state['projeto_ativo']} ⚡")
with c2:
    if client: st.success("🟢 DB Ativo")
    else: st.error("🔴 DB Offline")
with c3:
    with st.popover("📲 Conectar Zap", use_container_width=True):
        st.info(f"Instância: {instancia_limpa}")
        if st.button("🧹 Limpar Conexão"):
            requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
            st.rerun()
        st.divider()
        if st.button("Gerar QR Code"):
            res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}", headers={"apikey": EVO_KEY})
            if res.status_code == 200 and "base64" in res.json():
                st.image(base64.b64decode(res.json()["base64"].split(",")[1]))
            else:
                requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": True}, headers={"apikey": EVO_KEY})
                st.info("Criando... Clique novamente.")
        st.divider()
        n_zap = st.text_input("Número (Com 55)", key="nzap")
        if st.button("Gerar Código"):
            res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={n_zap}", headers={"apikey": EVO_KEY})
            if "pairingCode" in res.json(): st.success(f"Código: **{res.json()['pairingCode']}**")
        st.divider()
        if st.button("🚀 Ativar Robô", type="primary"):
            requests.post(f"{EVO_URL}/webhook/set/{instancia_limpa}", json={"enabled": True, "url": WEBHOOK_URL, "webhookByEvents": False, "events": ["MESSAGES_UPSERT"]}, headers={"apikey": EVO_KEY})
            st.success("Ativado!")

st.divider()

# --- BUILDER (Mesma lógica de antes, mas salvando no projeto_ativo) ---
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
            cf1, cf2 = st.columns(2); c_s = cf1.text_input("Gatilho", value=v_c); d_s = cf2.text_input("Destino", value=v_d)
            routing = f"{c_s}|{d_s}" if c_s else ""
        elif btype == "Menu":
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_area("Opções (Botão > ID)", value=val_opc)
        else:
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("ID Próximo", value=val_opc)
            if btype in ["Áudio", "Imagem"]: upl = st.file_uploader("Arquivo", type=['mp3','ogg','png','jpg'])

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            novo = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
            if upl: novo["arquivo_b64"] = base64.b64encode(upl.read()).decode('utf-8')
            elif st.session_state.indice_edicao is not None:
                novo["arquivo_b64"] = st.session_state.fluxo[st.session_state.indice_edicao].get("arquivo_b64", "")
            
            if st.session_state.indice_edicao is not None: st.session_state.fluxo[st.session_state.indice_edicao] = novo
            else: st.session_state.fluxo.append(novo)
            salvar_fluxo(st.session_state.fluxo, st.session_state["projeto_ativo"])
            st.session_state.indice_edicao = None; st.rerun()

with col_vis:
    tab_l, tab_m, tab_c = st.tabs(["📋 Blocos", "🕸️ Mapa", "👁️ CRM"])
    with tab_l:
        for i, blk in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {blk['id']}"):
                st.write(blk['msg'][:50])
                if st.button("Editar", key=f"ed_{i}"): st.session_state.indice_edicao = i; st.rerun()
                if st.button("Excluir", key=f"del_{i}"):
                    st.session_state.fluxo.pop(i); salvar_fluxo(st.session_state.fluxo, st.session_state["projeto_ativo"]); st.rerun()
    with tab_m:
        if st.session_state.fluxo:
            dot = graphviz.Digraph(); [dot.node(b['id'], b['id']) for b in st.session_state.fluxo]
            for b in st.session_state.fluxo:
                if b.get('opcoes') and b['tipo'] != "Robô IA":
                    for l in b['opcoes'].split('\n'):
                        if ">" in l: dot.edge(b['id'], l.split(">")[1].strip())
            st.graphviz_chart(dot)
    with tab_c:
        chats = list(db["sessoes"].find({"instancia": instancia_limpa}))
        for s in chats:
            with st.expander(f"📱 {s.get('numero')}"):
                for m in s.get("historico", []): st.write(m)
