import streamlit as st
import time
import pymongo
import os
import graphviz # Biblioteca visual

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

# --- FUNÇÕES ---
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
    
    if st.button("🔄 Carregar/Atualizar"):
        st.session_state.fluxo = carregar_fluxo_db(projeto_id)
        st.success("Sincronizado!")
        time.sleep(0.5)
        st.rerun()

    st.divider()
    st.info("Para testar o gráfico, crie blocos que apontem uns para os outros.")

# --- ESTADO ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id)

if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- VARIÁVEIS FORMULÁRIO ---
val_id, val_msg, val_opcoes = "", "", ""
val_tipo_index = 0
titulo_form = "➕ Novo Bloco"
texto_botao = "Salvar Bloco"

if st.session_state.indice_edicao is not None:
    try:
        idx = st.session_state.indice_edicao
        bloco = st.session_state.fluxo[idx]
        val_id = bloco['id']
        val_msg = bloco['msg']
        val_opcoes = bloco.get('opcoes', '') # Recupera as opções de roteamento
        
        tipos = ["Texto", "Menu", "Áudio"]
        if bloco['tipo'] in tipos:
            val_tipo_index = tipos.index(bloco['tipo'])
            
        titulo_form = f"✏️ Editando: {val_id}"
        texto_botao = "Atualizar"
    except:
        st.session_state.indice_edicao = None

# --- HEADER ---
c1, c2 = st.columns([5,1])
c1.title("ZapVoice Builder ☁️")
c1.caption(f"Projeto: **{projeto_id}**")
c2.markdown(f"Status DB: **{'🟢 ON' if client else '🔴 OFF'}**")

st.divider()

# --- LÓGICA PRINCIPAL ---
col_editor, col_visual = st.columns([1, 1.5])

with col_editor:
    with st.container(border=True):
        st.subheader(titulo_form)
        if st.session_state.indice_edicao is not None:
            if st.button("Cancelar Edição"):
                st.session_state.indice_edicao = None
                st.rerun()

        # Inputs
        bid = st.text_input("ID do Bloco", value=val_id, placeholder="Ex: menu_inicial")
        btype = st.selectbox("Tipo", ["Texto", "Menu", "Áudio"], index=val_tipo_index)
        
        content = None
        opcoes_routing = ""

        if btype == "Áudio":
            st.info("Upload de Áudio")
            if val_msg: st.caption(f"Atual: {val_msg}")
            upl = st.file_uploader("Arquivo", type=['mp3','ogg'])
            if upl: content = f"[Audio] {upl.name}"
            elif val_msg: content = val_msg
            
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg, height=100)
            st.markdown("---")
            st.write("🔘 **Botões e Destinos**")
            st.caption("Formato: `Nome do Botão > id_do_destino` (Um por linha)")
            opcoes_routing = st.text_area("Configuração dos Botões", value=val_opcoes, placeholder="Vendas > bloco_vendas\nSuporte > bloco_suporte", height=100)
            
        else: # Texto
            content = st.text_area("Mensagem", value=val_msg, height=150)
            st.caption("Opcional: Para onde vai depois dessa mensagem?")
            opcoes_routing = st.text_input("Próximo ID (Auto-redirect)", value=val_opcoes, placeholder="Ex: menu_principal")

        # Salvar
        if st.button(texto_botao, type="primary", use_container_width=True):
            if bid and content:
                novo_bloco = {
                    "id": bid, 
                    "tipo": btype, 
                    "msg": content,
                    "opcoes": opcoes_routing # Salva o roteamento
                }
                
                if st.session_state.indice_edicao is not None:
                    st.session_state.fluxo[st.session_state.indice_edicao] = novo_bloco
                    st.session_state.indice_edicao = None
                else:
                    st.session_state.fluxo.append(novo_bloco)
                
                if client: salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                st.rerun()
            else:
                st.error("Preencha ID e Mensagem.")

with col_visual:
    # ABAS: Lista vs Gráfico
    tab1, tab2 = st.tabs(["📋 Lista", "🕸️ Fluxograma (Visual)"])
    
    with tab1:
        if st.button("Limpar Tudo", key="limpar"):
            st.session_state.fluxo = []
            salvar_fluxo_db(projeto_id, [])
            st.rerun()
            
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"{b['id']} ({b['tipo']})"):
                st.write(b['msg'])
                if b.get('opcoes'):
                    st.code(b['opcoes'], language="text")
                if st.button("Editar", key=f"e{i}"):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if st.button("Excluir", key=f"d{i}"):
                    st.session_state.fluxo.pop(i)
                    salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                    st.rerun()

    with tab2:
        st.subheader("Mapa da Conversa")
        if not st.session_state.fluxo:
            st.info("Crie blocos conectando IDs para ver o gráfico.")
        else:
            # GERADOR DE GRÁFICO (GRAPHVIZ)
            graph = graphviz.Digraph()
            graph.attr(rankdir='LR') # Desenha da Esquerda pra Direita
            
            # 1. Cria os Nós (Blocos)
            for b in st.session_state.fluxo:
                label = f"{b['id']}\n({b['tipo']})"
                shape = "box" if b['tipo'] == "Texto" else "component"
                if b['tipo'] == "Menu": shape = "folder"
                
                graph.node(b['id'], label, shape=shape, style="filled", fillcolor="#e1f5fe")
                
                # 2. Cria as Conexões (Setas)
                if b.get('opcoes'):
                    linhas = b['opcoes'].split('\n')
                    for l in linhas:
                        if ">" in l:
                            try:
                                gatilho, destino = l.split(">")
                                gatilho = gatilho.strip()
                                destino = destino.strip()
                                # Cria a seta
                                graph.edge(b['id'], destino, label=gatilho)
                            except: pass
                        elif l.strip():
                             # Caso seja redirect simples (apenas o ID)
                             graph.edge(b['id'], l.strip())

            st.graphviz_chart(graph)
