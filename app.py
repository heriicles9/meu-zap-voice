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
        if uri:
            return pymongo.MongoClient(uri)
        return None
    except:
        return None

client = init_connection()

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""

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
                if db["usuarios"].find_one({"_id": user_login, "senha": pass_login}):
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = user_login
                    st.rerun()
                else:
                    st.error("❌ Dados incorretos.")
                            
        with tab_registro:
            st.write("")
            user_reg = st.text_input("Novo Usuário", key="ureg").lower().strip()
            pass_reg = st.text_input("Nova Senha", type="password", key="preg")
            if st.button("Criar Conta", type="primary", use_container_width=True):
                if user_reg and pass_reg and not db["usuarios"].find_one({"_id": user_reg}):
                    db["usuarios"].insert_one({"_id": user_reg, "senha": pass_reg})
                    st.session_state["logado"] = True
                    st.session_state["usuario"] = user_reg
                    st.success("✅ Sucesso!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ Erro no cadastro.")
                    
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
WEBHOOK_URL = "https://meu-zap-webhook.onrender.com/webhook"
projeto_id = st.session_state["usuario"]
instancia_limpa = projeto_id.replace(" ", "").replace("-", "")

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
        
        # --- OPÇÃO 1: QR CODE ---
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
        
        # --- OPÇÃO 2: EMPARELHAMENTO ---
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
                        # Se não existir, cria a instância primeiro
                        requests.post(f"{EVO_URL}/instance/create", json={"instanceName": instancia_limpa, "qrcode": False}, headers=headers)
                        time.sleep(1)
                        res_conn2 = requests.get(f"{EVO_URL}/instance/connect/{instancia_limpa}?number={numero_zap}", headers=headers)
                        codigo2 = res_conn2.json().get("pairingCode")
                        if codigo2:
                            st.success(f"Código: **{codigo2}**")
                        else:
                            st.error("Erro ao gerar. Use o QR Code.")
                except:
                    st.error("Erro de conexão. Tente novamente.")
            else:
                st.warning("Digite o número com o 55 e DDD.")

        st.divider()
        
        if st.button("🚀 Ativar Robô", type="primary", use_container_width=True):
            if ativar_webhook():
                st.success("Robô Ativo e Ouvindo!")
            else:
                st.error("Erro ao ativar webhook")
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
        bid = st.text_input("ID do Bloco (Ex: inicio)", value=val_id)
        btype = st.selectbox("Tipo de Conteúdo", tipos, index=v_idx)
        content, routing, upl = "", "", None
        
        if btype == "Robô IA":
            content = st.text_area("Treinamento da IA (Use {nome})", value=val_msg, height=150)
            v_c = val_opc.split("|")[0] if "|" in val_opc else ""
            v_d = val_opc.split("|")[1] if "|" in val_opc else ""
            c_f1, c_f2 = st.columns(2)
            cond = c_f1.text_input("Se o cliente...", value=v_c, placeholder="pedir pix")
            dest = c_f2.text_input("Vá para o ID:", value=v_d, placeholder="id_do_bloco")
            routing = f"{cond}|{dest}" if cond else ""
        elif btype == "Menu":
            content = st.text_area("Mensagem do Menu", value=val_msg)
            linhas = val_opc.split("\n") if val_opc else []
            b_vals = [l.split(">")[0].strip() for l in linhas if ">" in l]
            d_vals = [l.split(">")[1].strip() for l in linhas if ">" in l]
            
            if len(b_vals) > st.session_state.num_opcoes:
                st.session_state.num_opcoes = len(b_vals)
                
            if st.button("➕ Adicionar Opção"):
                st.session_state.num_opcoes += 1
            
            while len(b_vals) < st.session_state.num_opcoes:
                b_vals.append("")
                d_vals.append("")
            
            opcoes_temp = []
            for i in range(st.session_state.num_opcoes):
                c_btn, c_dst = st.columns(2)
                v1 = c_btn.text_input(f"Opção {i+1}", value=b_vals[i], key=f"btn_{i}")
                v2 = c_dst.text_input(f"Destino {i+1}", value=d_vals[i], key=f"dst_{i}")
                if v1 and v2:
                    opcoes_temp.append(f"{v1} > {v2}")
            routing = "\n".join(opcoes_temp)
        else:
            content = st.text_area("Mensagem", value=val_msg)
            routing = st.text_input("ID do próximo bloco", value=val_opc)
            if btype in ["Áudio", "Imagem"]:
                upl = st.file_uploader("Upload do arquivo", type=['mp3','ogg','png','jpg'])

        if st.button("💾 Salvar Bloco", type="primary", use_container_width=True):
            novo_bloco = {"id": bid, "tipo": btype, "msg": content, "opcoes": routing}
            if upl:
                novo_bloco["arquivo_b64"] = base64.b64encode(upl.read()).decode('utf-8')
            elif st.session_state.indice_edicao is not None:
                novo_bloco["arquivo_b64"] = st.session_state.fluxo[st.session_state.indice_edicao].get("arquivo_b64", "")
            
            if st.session_state.indice_edicao is not None:
                st.session_state.fluxo[st.session_state.indice_edicao] = novo_bloco
            else:
                st.session_state.fluxo.append(novo_bloco)
            
            salvar_fluxo(st.session_state.fluxo)
            st.session_state.indice_edicao = None
            st.rerun()

with col_vis:
    tab_lista, tab_mapa, tab_chat = st.tabs(["📋 Lista", "🕸️ Mapa", "👁️ Live Chat"])
    with tab_lista:
        for i, b in enumerate(st.session_state.fluxo):
            with st.expander(f"📍 {b['id']} ({b['tipo']})"):
                st.write(f"Conteúdo: {b['msg'][:50]}...")
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("Editar", key=f"edit_btn_{i}"):
                    st.session_state.indice_edicao = i
                    st.rerun()
                if col_btn2.button("Excluir", key=f"del_btn_{i}"):
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
                        if ">" in linha:
                            dot.edge(b['id'], linha.split(">")[1].strip())
            st.graphviz_chart(dot)
    with tab_chat:
        if st.button("🔄 Atualizar Conversas", use_container_width=True):
            st.rerun()
        sessoes = list(client["zapvoice_db"]["sessoes"].find({"instancia": instancia_limpa}))
        
        if not sessoes:
            st.info("Nenhuma conversa ativa no momento.")
            
        for s in sessoes:
            nome_exibicao = s.get('nome_personalizado', s.get('numero'))
            id_sessao = str(s["_id"])
            
            with st.expander(f"📱 {nome_exibicao} (Bloco: {s.get('bloco_id')})"):
                col_n, col_s, col_e = st.columns([3, 1, 1])
                with col_n:
                    novo_nome = st.text_input("Renomear", value=nome_exibicao, key=f"nome_{id_sessao}", label_visibility="collapsed")
                with col_s:
                    if st.button("💾", key=f"salvar_{id_sessao}", help="Salvar Nome", use_container_width=True):
                        client["zapvoice_db"]["sessoes"].update_one({"_id": s["_id"]}, {"$set": {"nome_personalizado": novo_nome}})
                        st.rerun()
                with col_e:
                    if st.button("🗑️", key=f"excluir_{id_sessao}", help="Excluir Chat", type="primary", use_container_width=True):
                        client["zapvoice_db"]["sessoes"].delete_one({"_id": s["_id"]})
                        st.rerun()
                
                st.divider()
                for m in s.get("historico", []):
                    if m.startswith("Cliente:"):
                        st.markdown(f"**🟢 {m}**")
                    else:
                        st.markdown(f"🤖 {m}")
