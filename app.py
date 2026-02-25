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
        if not uri and "MONGO_URI" in st.secrets: 
            uri = st.secrets["MONGO_URI"]
        if uri:
            return pymongo.MongoClient(uri)
        return None
    except:
        return None

client = init_connection()

# --- SISTEMA DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["vencimento_teste"] = None
    st.session_state["plano_ativo"] = False
    st.session_state["projeto_ativo"] = "Padrao"

# --- TELA DE LOGIN ---
if not st.session_state["logado"]:
    col_vazia1, col_centro, col_vazia2 = st.columns([1, 2, 1])
    with col_centro:
        # Logo
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
            
            if st.button("Acessar Painel", type="primary", use_container_width=True):
                user_db = db["usuarios"].find_one({"_id": user_login, "senha": pass_login})
                if user_db:
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = user_login
                    st.session_state["vencimento_teste"] = user_db.get("vencimento_teste")
                    st.session_state["plano_ativo"] = user_db.get("plano_ativo", False)
                    st.rerun()
                else:
                    st.error("❌ Dados incorretos.")
                            
        with tab_registro:
            st.write("")
            user_reg = st.text_input("Novo Usuário", key="ureg").lower().strip()
            email_reg = st.text_input("Seu E-mail (Obrigatório)", key="ereg").lower().strip()
            pass_reg = st.text_input("Nova Senha", type="password", key="preg")
            
            if st.button("Criar Conta", type="primary", use_container_width=True):
                if user_reg and email_reg and pass_reg:
                    if not db["usuarios"].find_one({"_id": user_reg}):
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
                        st.success("✅ Conta criada com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Usuário já existe.")
                else:
                    st.warning("⚠️ Preencha todos os campos.")
                    
        with tab_senha:
            st.write("")
            u_t = st.text_input("Seu Usuário", key="utroca").lower().strip()
            p_a = st.text_input("Senha Atual", type="password", key="patual")
            p_n = st.text_input("Nova Senha", type="password", key="pnova")
            if st.button("Atualizar Senha", use_container_width=True):
                if db["usuarios"].find_one({"_id": u_t, "senha": p_a}):
                    db["usuarios"].update_one({"_id": u_t}, {"$set": {"senha": p_n}})
                    st.success("✅ Senha alterada!")
                else:
                    st.error("❌ Dados atuais incorretos.")
    st.stop()

# --- VARIÁVEIS DO SISTEMA ---
EVO_URL = "https://api-zap-motor.onrender.com"
EVO_KEY = "Mestra123"
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"
link_asaas = "https://www.asaas.com/c/kai0orwy6nsfr37s"
db = client["zapvoice_db"]

# --- FUNÇÕES DE BANCO DE DADOS ---
def listar_projetos():
    projetos = db["fluxos"].find({"dono": st.session_state["usuario"]})
    lista = [p["nome_projeto"] for p in projetos]
    if not lista:
        return ["Padrao"]
    return lista

def carregar_fluxo(nome_projeto):
    doc = db["fluxos"].find_one({
        "dono": st.session_state["usuario"], 
        "nome_projeto": nome_projeto
    })
    if doc:
        return doc.get("blocos", [])
    return []

def salvar_fluxo(lista_blocos, nome_projeto):
    db["fluxos"].update_one(
        {"_id": f"{st.session_state['usuario']}_{nome_projeto}"},
        {
            "$set": {
                "dono": st.session_state["usuario"], 
                "nome_projeto": nome_projeto, 
                "blocos": lista_blocos
            }
        },
        upsert=True
    )

# --- SIDEBAR (GERENCIADOR DE PROJETOS) ---
with st.sidebar:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        pass
    
    st.divider()
    st.subheader("📁 Minhas Pastas")
    
    lista_projetos = listar_projetos()
    
    # Se o projeto ativo atual não estiver na lista, volta pro primeiro
    if st.session_state["projeto_ativo"] not in lista_projetos:
        st.session_state["projeto_ativo"] = lista_projetos[0]
        
    proj_selecionado = st.selectbox(
        "Pasta Atual:", 
        options=lista_projetos, 
        index=lista_projetos.index(st.session_state["projeto_ativo"])
    )
    
    # Detecta se o usuário trocou de pasta
    if proj_selecionado != st.session_state["projeto_ativo"]:
        st.session_state["projeto_ativo"] = proj_selecionado
        st.session_state["fluxo"] = carregar_fluxo(proj_selecionado)
        st.session_state["indice_edicao"] = None
        st.rerun()

    with st.expander("➕ Criar Nova Pasta"):
        novo_nome = st.text_input("Nome da Pasta", key="novo_proj").strip()
        if st.button("Criar e Abrir"):
            if novo_nome:
                salvar_fluxo([], novo_nome)
                st.session_state["projeto_ativo"] = novo_nome
                st.rerun()

    st.divider()
    st.header(f"👤 {st.session_state['usuario']}")
    
    if not st.session_state["plano_ativo"]:
        st.markdown(
            f'<a href="{link_asaas}" target="_blank" style="text-decoration:none;"><button style="width:100%;background-color:#28a745;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;margin-bottom:10px;">💎 Assinar Plano Pro</button></a>', 
            unsafe_allow_html=True
        )
    
    if st.button("🔄 Sincronizar Tudo", use_container_width=True):
        st.session_state.fluxo = carregar_fluxo(st.session_state["projeto_ativo"])
        st.rerun()
        
    if st.button("🚪 Sair da Conta", use_container_width=True):
        st.session_state["logado"] = False
        st.rerun()

# --- IDENTIFICAÇÃO ÚNICA DA INSTÂNCIA ---
projeto_id_unico = f"{st.session_state['usuario']}_{st.session_state['projeto_ativo']}"
instancia_limpa = projeto_id_unico.replace(" ", "").replace("-", "").lower()

# --- TRAVA DE MONETIZAÇÃO (PAYWALL) ---
agora = datetime.datetime.now()
vencimento_teste = st.session_state["vencimento_teste"]

if isinstance(vencimento_teste, str): 
    vencimento_teste = datetime.datetime.fromisoformat(vencimento_teste.replace("Z", ""))

dias_restantes = (vencimento_teste - agora).days

if not st.session_state["plano_ativo"]:
    if dias_restantes < 0:
        col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
        with col_b2:
            st.error("⏳ Seu período de teste expirou!")
            st.markdown(
                f"""
                <div style="text-align: center; background-color: #1e1e1e; padding: 25px; border-radius: 15px; border: 1px solid #ff4b4b;">
                    <h2 style="color: white;">Opa! O robô parou.</h2>
                    <p style="color: #cccccc;">Para continuar automatizando seu WhatsApp com IA, assine o Plano Pro.</p>
                    <a href="{link_asaas}" target="_blank" style="text-decoration: none;">
                        <button style="width: 100%; background-color: #ff4b4b; color: white; border: none; padding: 15px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 18px;">
                            💳 ASSINAR AGORA (R$ 147,00/mês)
                        </button>
                    </a>
                </div>
                """, 
                unsafe_allow_html=True
            )
        st.stop()
    else:
        col_aviso, col_botao = st.columns([3, 1])
        with col_aviso:
            st.warning(f"💎 Teste Grátis: Restam {dias_restantes} dias para expirar.")
        with col_botao:
            st.markdown(
                f'<a href="{link_asaas}" target="_blank" style="text-decoration:none;"><button style="width:100%;background-color:#28a745;color:white;border:none;padding:8px;border-radius:5px;cursor:pointer;font-weight:bold;">🚀 ASSINAR JÁ</button></a>', 
                unsafe_allow_html=True
            )

# --- INICIALIZAÇÃO DE VARIÁVEIS LOCAIS ---
if 'fluxo' not in st.session_state: 
    st.session_state.fluxo = carregar_fluxo(st.session_state["projeto_ativo"])
if 'indice_edicao' not in st.session_state: 
    st.session_state.indice_edicao = None
if 'num_opcoes' not in st.session_state: 
    st.session_state.num_opcoes = 2

# --- CABEÇALHO PRINCIPAL ---
c1, c2, c3 = st.columns([2.5, 1, 1.5])
with c1: 
    st.title(f"ZapFluxo: {st.session_state['projeto_ativo']} ⚡")
with c2:
    if client:
        st.success("🟢 DB Ativo")
    else:
        st.error("🔴 DB Offline")
with c3:
    with st.popover("📲 Conectar Zap", use_container_width=True):
        st.info(f"Instância Interna: {instancia_limpa}")
        
        # OPÇÃO DE LIMPEZA
        if st.button("🧹 Limpar Conexão", use_container_width=True):
            requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
            st.success("Memória limpa! Pode conectar.")
            time.sleep(1.5)
            st.rerun()
            
        st.divider()
        
        # OPÇÃO QR CODE
        st.markdown("**Opção 1: Via QR Code**")
        if st.button("Gerar QR Code", use_container_width=True):
            # Deleta antes para evitar conflito com código de número
            requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
            time.sleep(1)
            requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": True}, headers={"apikey": EVO_KEY})
            res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}", headers={"apikey": EVO_KEY})
            if res.status_code == 200 and "base64" in res.json():
                st.image(base64.b64decode(res.json()["base64"].split(",")[1]))
            else:
                st.error("Erro. Clique em Gerar novamente.")
                
        st.divider()
        
        # OPÇÃO CÓDIGO NUMÉRICO
        st.markdown("**Opção 2: Via Código (Celular)**")
        numero_zap = st.text_input("Seu Celular (Ex: 5511999999999)", key="nzap", label_visibility="collapsed")
        if st.button("Gerar Código de 8 Dígitos", use_container_width=True):
            if numero_zap:
                # 🚨 Truque obrigatório: Criar instância sem qrcode antes de pedir pareamento
                requests.delete(f"{EVO_URL}/instance/delete/{instancia_limpa}", headers={"apikey": EVO_KEY})
                time.sleep(1)
                requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": False}, headers={"apikey": EVO_KEY})
                time.sleep(1)
                res = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={numero_zap}", headers={"apikey": EVO_KEY})
                
                codigo_pareamento = res.json().get("pairingCode")
                if codigo_pareamento:
                    st.success(f"Código: **{codigo_pareamento}**")
                else:
                    st.error("Erro. Verifique o número.")
            else:
                st.warning("Digite o número do WhatsApp.")
                
        st.divider()
        
        # ATIVADOR DE WEBHOOK
        if st.button("🚀 Ativar Robô Ouvinte", type="primary", use_container_width=True):
            payload = {
                "enabled": True, 
                "url": WEBHOOK_URL, 
                "webhookByEvents": False, 
                "events": ["MESSAGES_UPSERT"]
            }
            res = requests.post(f"{EVO_URL}/webhook/set/{instancia_limpa}", json=payload, headers={"apikey": EVO_KEY})
            if res.status_code in [200, 201]:
                st.success("Robô Ativado com Sucesso!")
            else:
                st.error("Falha ao ativar o robô.")

st.divider()

# --- ÁREA DE CONSTRUÇÃO (BUILDER) ---
col_edicao, col_visualizacao = st.columns([1, 1.5])
lista_tipos = ["Texto", "Menu", "Áudio", "Imagem", "Robô IA"]
val_id = ""
val_msg = ""
val_opc = ""
val_idx = 0

if st.session_state.indice_edicao is not None:
    bloco_atual = st.session_state.fluxo[st.session_state.indice_edicao]
    val_id = bloco_atual['id']
    val_msg = bloco_atual.get('msg', '')
    val_opc = bloco_atual.get('opcoes', '')
    if bloco_atual['tipo'] in lista_tipos:
        val_idx = lista_tipos.index(bloco_atual['tipo'])

with col_edicao:
    with st.container(border=True):
        st.subheader("📝 Configurar Bloco")
        input_id = st.text_input("ID do Bloco (Sem espaços)", value=val_id)
        input_tipo = st.selectbox("Tipo de Conteúdo", lista_tipos, index=val_idx)
        
        conteudo_final = ""
        rotas_final = ""
        arquivo_upload = None
        
        # COMPORTAMENTO POR TIPO
        if input_tipo == "Robô IA":
            conteudo_final = st.text_area("Treinamento da IA (Prompt)", value=val_msg, height=150)
            
            # Divide as opções (Gatilho | Destino)
            partes = val_opc.split("|") if "|" in val_opc else ["", ""]
            gatilho_atual = partes[0]
            destino_atual = partes[1] if len(partes) > 1 else ""
            
            c_gatilho, c_destino = st.columns(2)
            novo_gatilho = c_gatilho.text_input("Se o cliente falar sobre...", value=gatilho_atual, placeholder="pix")
            novo_destino = c_destino.text_input("Vá para o ID:", value=destino_atual, placeholder="bloco_pix")
            
            if novo_gatilho:
                rotas_final = f"{novo_gatilho}|{novo_destino}"
                
        elif input_tipo == "Menu":
            conteudo_final = st.text_area("Mensagem do Menu (Pergunta)", value=val_msg)
            
            # Restauração Completa da Lógica de Botões Dinâmicos
            linhas_menu = val_opc.split("\n") if val_opc else []
            botoes_texto = [linha.split(">")[0].strip() for linha in linhas_menu if ">" in linha]
            botoes_destino = [linha.split(">")[1].strip() for linha in linhas_menu if ">" in linha]
            
            if len(botoes_texto) > st.session_state.num_opcoes:
                st.session_state.num_opcoes = len(botoes_texto)
                
            if st.button("➕ Adicionar Opção ao Menu"):
                st.session_state.num_opcoes += 1
                
            while len(botoes_texto) < st.session_state.num_opcoes:
                botoes_texto.append("")
                botoes_destino.append("")
                
            opcoes_formatadas = []
            for i in range(st.session_state.num_opcoes):
                col_btn_texto, col_btn_id = st.columns(2)
                texto_btn = col_btn_texto.text_input(f"Texto do Botão {i+1}", value=botoes_texto[i], key=f"btxt_{i}")
                id_destino = col_btn_id.text_input(f"ID de Destino {i+1}", value=botoes_destino[i], key=f"bdst_{i}")
                
                if texto_btn and id_destino:
                    opcoes_formatadas.append(f"{texto_btn} > {id_destino}")
                    
            rotas_final = "\n".join(opcoes_formatadas)
            
        else:
            # Texto, Áudio e Imagem
            conteudo_final = st.text_area("Mensagem Principal", value=val_msg)
            rotas_final = st.text_input("ID do Próximo Bloco (Deixe em branco para encerrar)", value=val_opc)
            
            if input_tipo in ["Áudio", "Imagem"]:
                arquivo_upload = st.file_uploader("Fazer Upload do Arquivo", type=['mp3', 'ogg', 'png', 'jpg'])

        # SALVAMENTO
        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            if not input_id:
                st.warning("⚠️ O Bloco precisa de um ID.")
            else:
                novo_bloco = {
                    "id": input_id, 
                    "tipo": input_tipo, 
                    "msg": conteudo_final, 
                    "opcoes": rotas_final
                }
                
                # Tratamento de Arquivo Mídia
                if arquivo_upload:
                    novo_bloco["arquivo_b64"] = base64.b64encode(arquivo_upload.read()).decode('utf-8')
                elif st.session_state.indice_edicao is not None:
                    # Preserva o arquivo antigo se não subiu um novo
                    bloco_antigo = st.session_state.fluxo[st.session_state.indice_edicao]
                    novo_bloco["arquivo_b64"] = bloco_antigo.get("arquivo_b64", "")
                
                if st.session_state.indice_edicao is not None:
                    st.session_state.fluxo[st.session_state.indice_edicao] = novo_bloco
                else:
                    st.session_state.fluxo.append(novo_bloco)
                
                salvar_fluxo(st.session_state.fluxo, st.session_state["projeto_ativo"])
                
                # Limpa a edição
                st.session_state.indice_edicao = None
                st.session_state.num_opcoes = 2
                st.rerun()

# --- ÁREA DE VISUALIZAÇÃO ---
with col_visualizacao:
    aba_lista, aba_mapa, aba_crm = st.tabs(["📋 Lista de Blocos", "🕸️ Mapa de Fluxo", "👁️ Live Chat (CRM)"])
    
    with aba_lista:
        for i, bloco in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {bloco['id']} ({bloco['tipo']})"):
                st.write(f"**Conteúdo:** {bloco['msg'][:80]}...")
                if bloco.get('opcoes'):
                    st.write(f"**Rotas:** {bloco['opcoes']}")
                    
                col_btn_editar, col_btn_excluir = st.columns(2)
                if col_btn_editar.button("✏️ Editar Bloco", key=f"editar_{i}", use_container_width=True):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if col_btn_excluir.button("🗑️ Excluir", key=f"excluir_{i}", use_container_width=True):
                    st.session_state.fluxo.pop(i)
                    salvar_fluxo(st.session_state.fluxo, st.session_state["projeto_ativo"])
                    st.rerun()
                    
    with aba_mapa:
        if st.session_state.fluxo:
            grafo = graphviz.Digraph()
            # Cria os nós
            for b in st.session_state.fluxo:
                grafo.node(b['id'], f"{b['id']}\n({b['tipo']})")
                
            # Cria as linhas (arestas)
            for b in st.session_state.fluxo:
                if b.get('opcoes'):
                    if b['tipo'] == "Menu":
                        for linha in b['opcoes'].split('\n'):
                            if ">" in linha:
                                destino = linha.split(">")[1].strip()
                                grafo.edge(b['id'], destino)
                    elif b['tipo'] != "Robô IA":
                        # Texto, audio, imagem apenas vão para um lugar
                        grafo.edge(b['id'], b['opcoes'])
                        
            st.graphviz_chart(grafo)
            
    with aba_crm:
        if st.button("🔄 Atualizar Conversas", use_container_width=True):
            st.rerun()
            
        # Busca apenas as sessões da instância do projeto atual
        lista_sessoes = list(db["sessoes"].find({"instancia": instancia_limpa}))
        
        if not lista_sessoes:
            st.info("Nenhuma conversa ativa no momento para esta pasta.")
            
        for sessao in lista_sessoes:
            nome_exibicao = sessao.get('nome_personalizado', sessao.get('numero'))
            id_sessao_str = str(sessao["_id"])
            
            with st.expander(f"📱 {nome_exibicao} (Bloco Atual: {sessao.get('bloco_id')})"):
                
                # RESTAURAÇÃO COMPLETA: Botões de Renomear e Excluir Chat
                col_nome, col_salvar_nome, col_excluir_chat = st.columns([3, 1, 1])
                with col_nome:
                    novo_nome_cliente = st.text_input("Renomear Cliente", value=nome_exibicao, key=f"nome_{id_sessao_str}", label_visibility="collapsed")
                with col_salvar_nome:
                    if st.button("💾", key=f"salvarnome_{id_sessao_str}", help="Salvar Nome", use_container_width=True):
                        db["sessoes"].update_one({"_id": sessao["_id"]}, {"$set": {"nome_personalizado": novo_nome_cliente}})
                        st.success("Salvo!")
                        time.sleep(0.5)
                        st.rerun()
                with col_excluir_chat:
                    if st.button("🗑️", key=f"excluirchat_{id_sessao_str}", help="Apagar Conversa", type="primary", use_container_width=True):
                        db["sessoes"].delete_one({"_id": sessao["_id"]})
                        st.rerun()
                
                st.divider()
                
                # Exibição do Histórico
                for mensagem in sessao.get("historico", []):
                    if mensagem.startswith("Cliente:"):
                        st.markdown(f"**🟢 {mensagem}**")
                    else:
                        st.markdown(f"🤖 {mensagem}")
