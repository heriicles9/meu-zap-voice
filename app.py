import streamlit as st
import time
import pymongo
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="ZapVoice Builder", layout="wide", page_icon="🤖")

# --- CONEXÃO COM MONGODB (CACHEADA) ---
# O @st.cache_resource é VITAL para 100 usuários. 
# Ele mantém a conexão aberta e reutiliza, em vez de conectar do zero a cada clique.
@st.cache_resource
def init_connection():
    # Tenta pegar a senha dos segredos do Streamlit ou Variável de Ambiente (Render)
    try:
        # Se estiver rodando localmente, procure no .streamlit/secrets.toml
        # Se estiver no Render, vai buscar nas Environment Variables
        uri = os.environ.get("MONGO_URI") 
        if not uri and "MONGO_URI" in st.secrets:
            uri = st.secrets["MONGO_URI"]
            
        if not uri:
            return None
            
        client = pymongo.MongoClient(uri)
        return client
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        return None

client = init_connection()

# --- FUNÇÕES DE BANCO DE DADOS ---

def carregar_fluxo_db(projeto_id):
    if not client: return []
    db = client["zapvoice_db"] # Nome do Banco
    collection = db["fluxos"]  # Nome da Coleção (Tabela)
    
    # Busca o documento pelo ID do projeto
    dados = collection.find_one({"_id": projeto_id})
    if dados:
        return dados.get("blocos", [])
    return []

def salvar_fluxo_db(projeto_id, lista_blocos):
    if not client: return False
    db = client["zapvoice_db"]
    collection = db["fluxos"]
    
    # Upsert=True: Se existir, atualiza. Se não existir, cria.
    collection.update_one(
        {"_id": projeto_id}, 
        {"$set": {"blocos": lista_blocos, "updated_at": time.time()}}, 
        upsert=True
    )
    return True

# --- ESTILOS ---
st.markdown("""
<style>
    .status-badge { background-color: #ff4b4b; color: white; padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 12px; }
    .success-badge { background-color: #0df06c; color: black; padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR (IDENTIFICAÇÃO DO USUÁRIO) ---
with st.sidebar:
    st.header("🔐 Acesso")
    # Cada usuário define sua chave única para não misturar dados
    projeto_id = st.text_input("Nome do Projeto / Chave", value="demo-teste")
    st.info("Use uma chave única para salvar seus dados separadamente dos outros.")
    
    if st.button("🔄 Carregar Dados da Nuvem"):
        dados_nuvem = carregar_fluxo_db(projeto_id)
        st.session_state.fluxo = dados_nuvem
        st.success("Dados carregados!")
        time.sleep(1)
        st.rerun()

# --- ESTADO LOCAL ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = carregar_fluxo_db(projeto_id) # Tenta carregar ao iniciar

if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- VARIÁVEIS DE CONTROLE DO FORMULÁRIO ---
val_id = ""
val_msg = ""
val_tipo_index = 0
titulo_form = "➕ Criar Novo Bloco"
texto_botao = "Salvar Bloco"

# Se estiver editando, popula os campos
if st.session_state.indice_edicao is not None:
    try:
        idx = st.session_state.indice_edicao
        bloco_atual = st.session_state.fluxo[idx]
        val_id = bloco_atual['id']
        val_msg = bloco_atual['msg']
        lista_tipos = ["Apenas Texto", "Menu (Botões)", "Áudio"]
        if bloco_atual['tipo'] in lista_tipos:
            val_tipo_index = lista_tipos.index(bloco_atual['tipo'])
        titulo_form = f"✏️ Editando: {val_id}"
        texto_botao = "Atualizar Bloco"
    except:
        st.session_state.indice_edicao = None # Reset se der erro

# --- CABEÇALHO ---
col_head_info, col_head_actions = st.columns([6, 1])
with col_head_info:
    st.title("ZapVoice Builder ☁️")
    st.caption(f"Projeto Ativo: **{projeto_id}**")

with col_head_actions:
    if client:
        st.markdown('<span class="success-badge">DB ONLINE</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge">DB OFFLINE</span>', unsafe_allow_html=True)
        
    with st.popover("📲 Conectar", use_container_width=True):
        st.info("Abra o WhatsApp > Aparelhos Conectados")
        # Gera QR Code baseado no ID do projeto para ser único
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=ZapVoice_{projeto_id}"
        st.image(qr_url, caption=f"Conectando ao projeto: {projeto_id}", use_column_width=True)

st.divider()

# --- CORPO PRINCIPAL ---
col_form, col_view = st.columns([1, 1.3])

# --- FORMULÁRIO ---
with col_form:
    with st.container(border=True):
        st.subheader(titulo_form)
        
        if st.session_state.indice_edicao is not None:
            if st.button("❌ Cancelar", key="cancel_edit"):
                st.session_state.indice_edicao = None
                st.rerun()

        block_id = st.text_input("NOME DO BLOCO (ID)", value=val_id, placeholder="Ex: inicio")
        resp_type = st.selectbox("TIPO DE RESPOSTA", ["Apenas Texto", "Menu (Botões)", "Áudio"], index=val_tipo_index)
        
        final_content = None
        if resp_type == "Áudio":
            st.info("📂 Áudio (Link ou Nome)")
            # Simulação de upload (Upload real para Mongo precisa de GridFS ou S3, aqui salvamos o nome)
            if st.session_state.indice_edicao is not None and val_msg:
                 st.caption(f"Atual: {val_msg}")
            
            audio_file = st.file_uploader("Arquivo de Áudio", type=['mp3', 'ogg', 'wav'])
            if audio_file:
                final_content = f"[Audio] {audio_file.name}"
            elif st.session_state.indice_edicao is not None:
                final_content = val_msg
        else:
            final_content = st.text_area("MENSAGEM", value=val_msg, height=150)

        # BOTÃO SALVAR (AGORA SALVA NO MONGO TAMBÉM)
        if st.button(texto_botao, type="primary", use_container_width=True):
            if block_id and final_content:
                novo_bloco = {"id": block_id, "tipo": resp_type, "msg": final_content}
                
                # Atualiza na Memória
                if st.session_state.indice_edicao is not None:
                    st.session_state.fluxo[st.session_state.indice_edicao] = novo_bloco
                    st.session_state.indice_edicao = None
                else:
                    st.session_state.fluxo.append(novo_bloco)
                
                # SALVA NO MONGODB
                if client:
                    salvou = salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                    if salvou:
                        st.toast(f"Salvo na nuvem no projeto '{projeto_id}'!", icon="☁️")
                    else:
                        st.error("Erro ao salvar no banco.")
                else:
                    st.warning("Salvo apenas na memória (Sem conexão DB).")
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Preencha todos os campos.")

# --- VISUALIZAÇÃO ---
with col_view:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.subheader(f"☍ Fluxo de {projeto_id}")
        
        if c2.button("Limpar"):
            st.session_state.fluxo = []
            st.session_state.indice_edicao = None
            # Opcional: Limpar também no banco
            # salvar_fluxo_db(projeto_id, [])
            st.rerun()

        if not st.session_state.fluxo:
            st.info("Nenhum bloco neste projeto.")
        else:
            for i, bloco in enumerate(st.session_state.fluxo):
                eh_editado = (i == st.session_state.indice_edicao)
                titulo = f"{'✏️' if eh_editado else '📍'} {bloco['id']} ({bloco['tipo']})"
                
                with st.expander(titulo, expanded=True):
                    st.write(bloco['msg'])
                    col_e, col_d = st.columns(2)
                    if col_e.button("Editar", key=f"ed_{i}", use_container_width=True):
                        st.session_state.indice_edicao = i
                        st.rerun()
                    if col_d.button("Excluir", key=f"del_{i}", use_container_width=True):
                        st.session_state.fluxo.pop(i)
                        # Atualiza o banco após excluir
                        salvar_fluxo_db(projeto_id, st.session_state.fluxo)
                        st.rerun()
