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
    st.header("🔐 Acesso Multi-Sessão")
    projeto_id = st.text_input("ID do Projeto / Cliente", value="demo-teste")
    if st.button("🔄 Sincronizar Dados"):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.rerun()

# --- ESTADO ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id)
if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- HEADER COM QR CODE ---
c1, c2, c3 = st.columns([4, 1, 1])
with c1:
    st.title("ZapVoice Builder 🤖☁️")
    st.caption(f"Projeto: **{projeto_id}**")
with c2:
    if client: st.success("🟢 DB ONLINE")
    else: st.error("🔴 DB OFFLINE")
with c3:
    with st.popover("📲 Conectar", use_container_width=True):
        st.markdown("### Escaneie o QR")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=ZapVoice_{projeto_id}"
        st.image(qr_url, use_column_width=True)

st.divider()

# --- EDITOR E VISUALIZAÇÃO ---
col_editor, col_visual = st.columns([1, 1.5])

# Carregar dados para edição
val_id, val_msg, val_opcoes, val_tipo_index = "", "", "", 0
if st.session_state.indice_edicao is not None:
    b = st.session_state.fluxo[st.session_state.indice_edicao]
    val_id, val_msg, val_opcoes = b['id'], b['msg'], b.get('opcoes', '')
    tipos = ["Texto", "Menu", "Áudio"]
    val_tipo_index = tipos.index(b['tipo']) if b['tipo'] in tipos else 0

with col_editor:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        
        bid = st.text_input("ID Único do Bloco", value=val_id, placeholder="ex: boas_vindas")
        btype = st.selectbox("Tipo de Resposta", ["Texto", "Menu", "Áudio"], index=val_tipo_index)
        
        content, routing = "", ""
        
        if btype == "Áudio":
            st.info("Sobe o arquivo de voz")
            upl = st.file_uploader("Arquivo .mp3 ou .ogg", type=['mp3','ogg'])
            content = f"[Audio] {upl.name}" if upl else val_msg
        
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg, placeholder="Olá! Escolha uma opção:")
            st.markdown("---")
            st.markdown("**🎯 Lógica Se/Então (Botões)**")
            st.caption("Se o usuário clicar no botão... Então ele vai para o ID...")
            routing = st.text_area("Formato: Botão > ID_Destino", value=val_opcoes, 
                                   placeholder="Vendas > bloco_vendas\nSuporte > bloco_suporte", height=100)
        
        else: # Texto
            content = st.text_area("Mensagem de Texto", value=val_msg)
            st.markdown("---")
            st.markdown("**➡️ Próximo Passo Automático**")
            routing = st.text_input("Se responder qualquer coisa, vá para o ID:", value=val_opcoes, placeholder="ex: menu_principal")

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
    tab1, tab2 = st.tabs(["📋 Lista de Blocos", "🕸️ Fluxograma Visual"])
    
    with tab1:
        if st.button("Limpar Tudo"):
            st.session_state.fluxo = []
            salvar_fluxo_db(projeto_id, [])
            st.rerun()
            
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(b['msg'])
                if b.get('opcoes'):
                    st.info(f"**Caminhos:**\n{b['opcoes']}")
                c_e, c_d = st.columns(2)
                if c_e.button("Editar", key=f"e{i}"):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if c_d.button("Excluir", key=f"d{i}"):
                    st.session_state.fluxo.pop(i)
                    salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                    st.rerun()

    with tab2:
        if not st.session_state.fluxo:
            st.info("Crie conexões para ver o mapa.")
        else:
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR', bgcolor='transparent')
            for b in st.session_state.fluxo:
                color = "#E1F5FE" if b['tipo'] == "Texto" else "#FFF9C4"
                if b['tipo'] == "Áudio": color = "#F1F8E9"
                dot.node(b['id'], f"{b['id']}\n({b['tipo']})", shape="rect", style="filled", fillcolor=color)
                
                if b.get('opcoes'):
                    for l in b['opcoes'].split('\n'):
                        if ">" in l:
                            try:
                                btn, dest = l.split(">")[0].strip(), l.split(">")[1].strip()
                                dot.edge(b['id'], dest, label=btn)
                            except: pass
                        elif l.strip():
                            dot.edge(b['id'], l.strip())
            st.graphviz_chart(dot)
