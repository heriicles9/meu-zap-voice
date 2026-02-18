import streamlit as st
import time
import pymongo
import os
import graphviz

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="ZapVoice Builder", layout="wide", page_icon="🤖")

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

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acesso")
    projeto_id = st.text_input("ID do Projeto / Cliente", value="demo-teste")
    if st.button("🔄 Sincronizar Dados"):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.rerun()

# --- ESTADO ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id)
if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- HEADER COM QR CODE AJUSTADO ---
c1, c2, c3 = st.columns([4, 1, 1.2]) # Ajuste de proporção para o botão não ficar espremido

with c1:
    st.title("ZapVoice Builder 🤖☁️")
    st.caption(f"Projeto Ativo: **{projeto_id}**")
with c2:
    if client: st.success("🟢 DB ON")
    else: st.error("🔴 DB OFF")
with c3:
    # Popover com tamanho controlado
    with st.popover("📲 Conectar WhatsApp", use_container_width=True):
        st.write("### Conectar Sessão")
        st.warning("⚠️ Este QR Code é uma DEMONSTRAÇÃO VISUAL.")
        st.caption("Para conexão real, é necessária integração com API.")
        
        # QR Code menor (width=180) e centralizado
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=ZapVoice_{projeto_id}"
        st.image(qr_url, width=180) # Definindo largura fixa para não ficar gigante
        st.caption(f"ID: {projeto_id}")

st.divider()

# --- EDITOR E VISUALIZAÇÃO ---
col_editor, col_visual = st.columns([1, 1.5])

# Lógica de edição
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
        elif btype == "Menu":
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_area("Se (Botão) > Então (ID)", value=val_opcoes, placeholder="Vendas > vendas_bloco")
        else:
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("Próximo ID", value=val_opcoes)

        if st.button("💾 Salvar", type="primary", use_container_width=True):
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
