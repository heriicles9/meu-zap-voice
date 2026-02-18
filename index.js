require('dotenv').config();
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, delay } = require('@whiskeysockets/baileys');
const pino = require('pino');
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const QRCode = require('qrcode');
const multer = require('multer');
const mongoose = require('mongoose');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const PORT = process.env.PORT || 3000;

// --- 1. CONEXÃO MONGODB ---
// Substitua pela sua URL do MongoDB Atlas no arquivo .env ou direto aqui
const MONGO_URI = process.env.MONGO_URI || "SUA_URL_DO_MONGODB_AQUI";

mongoose.connect(MONGO_URI)
  .then(() => console.log('[DB] Conectado ao MongoDB com sucesso!'))
  .catch(err => console.error('[DB] Erro ao conectar ao MongoDB:', err));

// Schema do Fluxo (Como os blocos são salvos no banco)
const BlocoSchema = new mongoose.Schema({
    id: { type: String, required: true, unique: true },
    tipo: String,
    texto: String,
    midia: String,
    opcoes: Array,
    metrica_envios: { type: Number, default: 0 }
});
const Bloco = mongoose.model('Bloco', BlocoSchema);

// --- 2. CONFIGURAÇÃO DE UPLOAD ---
if (!fs.existsSync('uploads')) fs.mkdirSync('uploads');
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, 'uploads/'),
    filename: (req, file, cb) => {
        const uniqueName = Date.now() + '-' + file.originalname.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, '_');
        cb(null, uniqueName);
    }
});
const upload = multer({ storage: storage });

// --- 3. MIDDLEWARES E API ---
app.use(express.static('public'));
app.use('/uploads', express.static('uploads'));
app.use(express.json());

// API: Listar Fluxo do MongoDB
app.get('/api/fluxo', async (req, res) => {
    const fluxo = await Bloco.find();
    res.json(fluxo);
});

// API: Salvar Bloco no MongoDB
app.post('/api/salvar-bloco', upload.single('midia'), async (req, res) => {
    const { id, tipo, texto, opcoes } = req.body;
    const file = req.file;

    const dadosBloco = {
        id: id.trim(),
        tipo,
        texto,
        midia: file ? file.path : null,
        opcoes: opcoes ? JSON.parse(opcoes) : []
    };

    await Bloco.findOneAndUpdate({ id: dadosBloco.id }, dadosBloco, { upsert: true });
    res.json({ status: 'sucesso' });
});

// API: Resetar
app.post('/api/resetar', async (req, res) => {
    await Bloco.deleteMany({});
    res.json({ status: 'resetado' });
});

// --- 4. LÓGICA DO WHATSAPP ---
let sock = null;
const sessions = {}; 

async function connectToWhatsApp() {
    // No Render, a pasta 'sessions' deve ser persistente ou o QR voltará sempre
    const { state, saveCreds } = await useMultiFileAuthState('./sessions/main_session');

    sock = makeWASocket({
        logger: pino({ level: 'silent' }),
        auth: state,
        browser: ["ZapVoice Pro", "Chrome", "10.0"],
    });

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) io.emit('qr', await QRCode.toDataURL(qr));
        if (connection === 'open') {
            console.log('[WA] Bot Online!');
            io.emit('status', { online: true });
        }
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            if (shouldReconnect) connectToWhatsApp();
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async m => {
        const msg = m.messages[0];
        if (!msg.key.fromMe && m.type === 'notify') {
            const remoteJid = msg.key.remoteJid;

            // FILTRO ANTI-GRUPO
            if (remoteJid.endsWith('@g.us')) return; 

            const text = (msg.message?.conversation || msg.message?.extendedTextMessage?.text || '').trim();
            if (!text) return;

            console.log(`[MSG] ${remoteJid}: ${text}`);

            let etapaAtual = sessions[remoteJid] || 'inicio';
            
            // Comandos de Reinício
            if (["oi", "ola", "olá", "menu", "voltar"].includes(text.toLowerCase())) {
                etapaAtual = 'inicio';
            }

            let bloco = await Bloco.findOne({ id: etapaAtual });

            if (!bloco && etapaAtual === 'inicio') {
                console.log('[AVISO] Bloco "inicio" não encontrado no MongoDB.');
                return;
            }

            // Lógica de Navegação
            if (bloco && bloco.opcoes.length > 0) {
                const opcao = bloco.opcoes.find(op => op.gatilho.toLowerCase() === text.toLowerCase());
                if (opcao) {
                    const proximo = await Bloco.findOne({ id: opcao.proximo });
                    if (proximo) {
                        sessions[remoteJid] = proximo.id;
                        await processarBloco(remoteJid, proximo);
                        return;
                    }
                } else if (!["oi", "olá", "menu"].includes(text.toLowerCase())) {
                    await sock.sendMessage(remoteJid, { text: "Opção inválida. Escolha uma das opções do menu." });
                    return;
                }
            }
            
            // Se for início ou qualquer outra coisa sem opção válida
            if (bloco) await processarBloco(remoteJid, bloco);
        }
    });
}

async function processarBloco(jid, bloco) {
    try {
        await sock.sendPresenceUpdate(bloco.tipo === 'audio' ? 'recording' : 'composing', jid);
        await delay(2500); 

        if (bloco.tipo === 'texto' || bloco.tipo === 'menu') {
            await sock.sendMessage(jid, { text: bloco.texto });
        } 
        else if (bloco.tipo === 'audio' && bloco.midia) {
            await sock.sendMessage(jid, { 
                audio: { url: bloco.midia }, 
                ptt: true, 
                mimetype: 'audio/ogg; codecs=opus' 
            });
        }

        // Incrementa métrica no MongoDB
        await Bloco.updateOne({ id: bloco.id }, { $inc: { metrica_envios: 1 } });

    } catch (e) {
        console.error("Erro ao processar bloco:", e);
    }
}

server.listen(PORT, () => {
    console.log(`>> Dashboard Profissional em: http://localhost:${PORT}`);
    connectToWhatsApp();
});