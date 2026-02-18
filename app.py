import streamlit as st
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="ZapVoice Builder", layout="wide", page_icon="🤖")

# --- CSS / ESTILOS ---
st.markdown("""
<style>
    .status-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- ESTADO (SESSION STATE) ---
if 'fluxo' not in st.session_state:
    st.session_state.fluxo = []

if 'indice_edicao' not in st.session_state:
    st.session_state.indice_edicao = None

# --- LÓGICA DE PREENCHIMENTO (EDIÇÃO VS CRIAÇÃO) ---
# Valores padrão (Modo Criação)
val_id = ""
val_msg = ""
val_tipo_index = 0
titulo_form = "➕ Criar Novo Bloco"
texto_botao = "Salvar Bloco"
arquivo_existente = None

# Se estiver no Modo Edição, sobrescreve os valores
if st.session_state.indice_edicao is not None:
    idx = st.session_state.indice_edicao
    bloco_atual = st.session_state.fluxo[idx]
    
    val_id = bloco_atual['id']
    val_msg = bloco_atual['msg'] # No caso de áudio, aqui estará o nome do arquivo
    
    # Tenta achar o índice do tipo selecionado
    lista_tipos = ["Apenas Texto", "Menu (Botões)", "Áudio"]
    if bloco_atual['tipo'] in lista_tipos:
        val_tipo_index = lista_tipos.index(bloco_atual['tipo'])
        
    titulo_form = f"✏️ Editando: {val_id}"
    texto_botao = "Atualizar Bloco"

# --- CABEÇALHO ---
col_head_info, col_head_actions = st.columns([6, 1])
with col_head_info:
    st.title("ZapVoice Builder 🤖")
    st.caption("Crie e gerencie fluxos de conversa.")

with col_head_actions:
    st.markdown('<span class="status-badge">OFFLINE</span>', unsafe_allow_html=True)
    with st.popover("📲 Conectar", use_container_width=True):
        st.info("Abra o WhatsApp > Aparelhos Conectados")
        st.image("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=ZapVoiceDemo", use_column_width=True)

st.divider()

# --- CORPO PRINCIPAL ---
col_form, col_view = st.columns([1, 1.3])

# ==========================================
# LADO ESQUERDO: FORMULÁRIO INTELIGENTE
# ==========================================
with col_form:
    with st.container(border=True):
        st.subheader(titulo_form)
        
        # Botão cancelar edição
        if st.session_state.indice_edicao is not None:
            if st.button("❌ Cancelar", key="cancel_edit"):
                st.session_state.indice_edicao = None
                st.rerun()

        # 1. ID do Bloco
        block_id = st.text_input("NOME DO BLOCO (ID)", value=val_id, placeholder="Ex: inicio")
        
        # 2. Tipo de Resposta
        resp_type = st.selectbox("TIPO DE RESPOSTA", 
                                 ["Apenas Texto", "Menu (Botões)", "Áudio"], 
                                 index=val_tipo_index)
        
        # 3. Conteúdo (Muda dependendo do Tipo)
        final_content = None # Variável para guardar o que será salvo
        
        if resp_type == "Áudio":
            st.info("📂 Upload de Arquivo")
            
            # Se já existir um áudio salvo (edição), avisa qual é
            if st.session_state.indice_edicao is not None and val_msg:
                st.warning(f"Áudio atual: {val_msg}")
                st.caption("Faça upload apenas se quiser trocar o áudio.")

            audio_file = st.file_uploader("Selecione o arquivo (.mp3, .ogg)", type=['mp3', 'ogg', 'wav'])
            
            if audio_file:
                # Se o usuário subiu um novo, usamos o nome dele
                final_content = f"[Áudio] {audio_file.name}"
            elif st.session_state.indice_edicao is not None:
                # Se não subiu nada mas está editando, mantemos o antigo
                final_content = val_msg
                
        else:
            # Se for Texto ou Menu, mostra a caixa de texto normal
            msg_input = st.text_area("MENSAGEM / PERGUNTA", value=val_msg, height=150)
            final_content = msg_input

        # 4. Botão Salvar
        if st.button(texto_botao, type="primary", use_container_width=True):
            if block_id and final_content:
                
                # Cria o objeto do bloco
                dados_bloco = {
                    "id": block_id, 
                    "tipo": resp_type, 
                    "msg": final_content
                }
                
                if st.session_state.indice_edicao is not None:
                    # Atualiza existente
                    st.session_state.fluxo[st.session_state.indice_edicao] = dados_bloco
                    st.success("Atualizado!")
                    st.session_state.indice_edicao = None
                else:
                    # Cria novo
                    st.session_state.fluxo.append(dados_bloco)
                    st.success("Criado!")
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Preencha o ID e o Conteúdo (Texto ou Arquivo).")

# ==========================================
# LADO DIREITO: VISUALIZAÇÃO
# ==========================================
with col_view:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.subheader("☍ Seu Fluxo")
        
        if c2.button("Limpar Tudo"):
            st.session_state.fluxo = []
            st.session_state.indice_edicao = None
            st.rerun()

        if not st.session_state.fluxo:
            st.info("Nenhum bloco criado.")
        else:
            for i, bloco in enumerate(st.session_state.fluxo):
                # Destaca visualmente se estiver editando
                eh_o_editado = (i == st.session_state.indice_edicao)
                icon = "🔊" if bloco['tipo'] == "Áudio" else "💬"
                titulo = f"{'✏️' if eh_o_editado else '📍'} {bloco['id']} ({bloco['tipo']})"
                
                with st.expander(titulo, expanded=True):
                    # Mostra ícone diferente se for áudio
                    if bloco['tipo'] == "Áudio":
                        st.markdown(f"**{icon} Arquivo:** `{bloco['msg']}`")
                        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3") # Player demo
                    else:
                        st.write(bloco['msg'])
                    
                    # Botões de Ação
                    col_edit, col_del = st.columns([1, 1])
                    if col_edit.button("Editar", key=f"edit_{i}", use_container_width=True):
                        st.session_state.indice_edicao = i
                        st.rerun()
                    
                    if col_del.button("Excluir", key=f"del_{i}", use_container_width=True):
                        st.session_state.fluxo.pop(i)
                        if st.session_state.indice_edicao == i:
                            st.session_state.indice_edicao = None
                        st.rerun()