# Funções utilitárias para lidar com a comunicação de rede p2p

import socket
import threading
import logging
import json
from typing import Any, Dict, List, Optional

# Importamos as funções que já transformamos em procedural
from .blockchain import (
    iniciar_blockchain, adicionar_bloco, adicionar_transacao, 
    validar_cadeia_completa, obter_ultimo_bloco
)
from .block import criar_bloco
from .protocolo import criar_mensagem, MessageType # Assumindo adaptação similar

# Configurações
BUFFER_SIZE = 65536

def criar_estado_no(host: str = "localhost", port: int = 5000) -> Dict[str, Any]:
    """
    Inicializa o 'cérebro' do nó. Substitui o __init__ da classe Node.
    """
    #print(port)
    return {
        "host": host,
        "port": port,
        "address": f"{host}:{port}",
        "blockchain": iniciar_blockchain(),
        "peers": set(),
        "running": False,
        "lock": threading.Lock(), # Protege a blockchain de acessos simultâneos
        "logger": logging.getLogger(f"Node:{port}"),
        "server_socket": None
    }

def iniciar_no(no_estado: Dict[str, Any]):
    """Configura o socket e inicia a thread de escuta."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", no_estado["port"]))
    sock.listen(10)
    no_estado["server_socket"] = sock
    no_estado["running"] = True
    no_estado["logger"].info(f"Nó procedural ativo em {no_estado['address']}")

    # Thread para aceitar conexões
    thread = threading.Thread(target=_loop_aceitar_conexoes, args=(no_estado,))
    thread.daemon = True
    thread.start()

def _loop_aceitar_conexoes(no_estado: Dict[str, Any]):
    """Loop principal de rede."""
    while no_estado["running"]:
        try:
            client_sock, addr = no_estado["server_socket"].accept()
            print(f"Aceitando conexão de {addr}")
            thread = threading.Thread(target=_tratar_cliente, args=(no_estado, client_sock, addr))
            thread.daemon = True
            thread.start()
        except:
            break

def _tratar_cliente(no_estado: Dict[str, Any], sock: socket.socket, addr: tuple):
    """Lê e processa mensagens via socket com registro de peers."""
    try:
        # 1. Ler o tamanho da mensagem (4 bytes)
        length_data = sock.recv(4)
        if not length_data: 
            return
        
        length = int.from_bytes(length_data, 'big')
        
        # 2. Ler o corpo da mensagem (JSON)
        raw_data = sock.recv(length)
        if not raw_data:
            return

        mensagem = json.loads(raw_data.decode('utf-8'))
        
        # --- LÓGICA DE REGISTRO DE PEERS ---
        # Se a mensagem trouxer o endereço de quem enviou, registramos na lista
        sender_address = mensagem.get("sender")
        if sender_address:
            with no_estado["lock"]:
                if sender_address not in no_estado["peers"]:
                    no_estado["peers"].add(sender_address)
                    no_estado["logger"].info(f"Novo peer registrado: {sender_address}")
        # ----------------------------------

        # 3. Processar a lógica de negócio (Novo bloco, transação, etc)
        resposta = _processar_mensagem(no_estado, mensagem)
        
        # 4. Enviar resposta, se houver
        if resposta:
            # Garante que a resposta siga o protocolo de 4 bytes
            corpo_resp = json.dumps(resposta).encode('utf-8')
            header_resp = len(corpo_resp).to_bytes(4, 'big')
            sock.sendall(header_resp + corpo_resp)

    except Exception as e:
        no_estado["logger"].error(f"Erro ao tratar cliente {addr}: {e}")
    finally:
        sock.close()

def _processar_mensagem(no_estado: Dict[str, Any], msg: Dict[str, Any]) -> Optional[Dict]:
    """
    O 'Dispatcher'. Decide o que fazer com a mensagem recebida.
    Note o uso de no_estado['lock'] para segurança.
    """
    m_type = msg.get("type")
    sender = msg.get("sender")
    payload = msg.get("payload", {})
    print(payload)
    print(m_type)

    with no_estado["lock"]:
        if m_type == "NEW_TRANSACTION":
            tx = payload["transaction"]
            if adicionar_transacao(no_estado["blockchain"], tx):
                # Propaga para os outros (exceto quem enviou)
                propagar_mensagem(no_estado, msg, ignore_addr=sender)
                
        elif m_type == "NEW_BLOCK":
            bloco = payload["block"]
            if adicionar_bloco(no_estado["blockchain"], bloco):
                no_estado["logger"].info(f"Bloco #{bloco['index']} aceito!")
                propagar_mensagem(no_estado, msg, ignore_addr=sender)
            else:
                # Se o bloco for rejeitado, talvez precisemos sincronizar a chain
                return {"type": "REQUEST_CHAIN", "sender": no_estado["address"]}

        elif m_type == "REQUEST_CHAIN":
            return {
                "type": "RESPONSE_CHAIN",
                "sender": no_estado["address"],
                "payload": {"blockchain": no_estado["blockchain"]}
            }

    return None

def conectar_a_peer(no_estado: Dict[str, Any], peer_addr: str):
    """Handshake inicial com um novo nó."""
    if peer_addr == no_estado["address"]: return
    
    try:
        host, port = peer_addr.split(":")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((host, int(port)))
            
            # Pede a chain para se sincronizar
            msg = {"type": "REQUEST_CHAIN", "sender": no_estado["address"]}
            dados = json.dumps(msg).encode('utf-8')
            sock.sendall(len(dados).to_bytes(4, 'big') + dados)
            
            # Adiciona à lista de peers
            no_estado["peers"].add(peer_addr)
            no_estado["logger"].info(f"Conectado ao peer {peer_addr}")
    except Exception as e:
        no_estado["logger"].error(f"Falha ao conectar em {peer_addr}: {e}")

def propagar_mensagem(no_estado: Dict[str, Any], msg: Dict[str, Any], ignore_addr: str = None):
    """Envia uma mensagem para todos os conhecidos (Broadcast)."""
    msg["sender"] = no_estado["address"] # Atualiza quem está enviando agora
    print(f"Propagando bloco para {len(no_estado['peers'])} peers...")
    for peer in list(no_estado["peers"]):
        if peer == ignore_addr: continue
        
        def enviar():
            try:
                h, p = peer.split(":")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((h, int(p)))
                    corpo = json.dumps(msg).encode('utf-8')
                    s.sendall(len(corpo).to_bytes(4, 'big') + corpo)
            except:
                pass # Peer offline, ignorar ou remover da lista
        
        threading.Thread(target=enviar).start()