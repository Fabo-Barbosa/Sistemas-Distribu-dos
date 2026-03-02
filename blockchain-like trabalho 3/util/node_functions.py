# Funções utilitárias para lidar com a comunicação de rede p2p

import socket
import threading
import logging
import json
from typing import Any, Dict, List, Optional

# Importamos as funções que já transformamos em procedural
from .blockchain import (
    iniciar_blockchain, adicionar_bloco, adicionar_transacao, 
    validar_cadeia_completa, obter_ultimo_bloco, substituir_pela_corrente_mais_longa
)
from .block import criar_bloco
from .protocolo import (
    criar_mensagem, MessageType, msg_solicitar_chain, msg_pong,
    msg_ping, mensagem_para_bytes, bytes_para_mensagem
    )

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
        #  Ler o tamanho da mensagem (4 bytes)
        length_data = sock.recv(4)
        if not length_data: 
            return
        
        length = int.from_bytes(length_data, 'big')
        
        # 2. Ler o corpo da mensagem (JSON)
        raw_data = sock.recv(length)
        if not raw_data:
            return

        mensagem = bytes_para_mensagem(raw_data)

        # 3. Processar a lógica de negócio (Novo bloco, transação, etc)
        resposta = _processar_mensagem(no_estado, mensagem)
        # 4. Enviar resposta, se houver
        if resposta:
            try:
                host, port = mensagem["sender"].split(":")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(5)
                    sock.connect((host, int(port)))
                    msgBytes = mensagem_para_bytes(resposta)
                    sock.sendall(msgBytes)

                    no_estado["logger"].info(f"Resposta {resposta["type"]} encaminhada {mensagem["sender"]}")
            except Exception as e:
                no_estado["logger"].error(f"Falha ao conectar em {peer_addr}: {e}")

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
        if m_type == MessageType.PING.value:
            print(1)
            if sender not in no_estado.get("peers"):
                print(2)
                no_estado["peers"].add(sender)
            pong_msg = msg_pong()
            pong_msg["sender"] = no_estado["address"]
            return pong_msg

        elif m_type == MessageType.PONG.value:
            if sender not in no_estado.get("peers"):
                no_estado["peers"].add(sender)
            return None
        
        elif m_type == MessageType.DISCOVER_PEERS.value:
            return criar_mensagem(MessageType.PEERS_LIST.value, {"peers": no_estado.get("peers")}, no_estado.get("address"))
        
        elif m_type == MessageType.PEERS_LIST.value:
            novos_peers = payload["peers"] - no_estado["peers"] - no_estado["address"]
            for peer in novos_peers:
                no_estado["peers"].add(peer)
            return None

        elif m_type == MessageType.NEW_TRANSACTION.value:
            tx = payload["transaction"]
            if adicionar_transacao(no_estado["blockchain"], tx):
                # Propaga para os outros (exceto quem enviou)
                propagar_mensagem(no_estado, msg, ignore_addr=sender)
                
        elif m_type == MessageType.NEW_BLOCK.value:
            bloco = payload["block"]
            blockchain_local = no_estado["blockchain"]
            proximo_index_esperado = len(blockchain_local["chain"])

            if bloco["index"] == proximo_index_esperado:
                # Caso ideal: bloco sequencial
                if adicionar_bloco(blockchain_local, bloco):
                    no_estado["logger"].info(f"Novo bloco #{bloco['index']} adicionado via rede.")
                    return None
        
            elif bloco["index"] > proximo_index_esperado:
                # Estamos atrasados! Pedimos a chain completa
                no_estado["logger"].info("Recebido bloco muito avançado. Solicitando sincronização completa...")
                from src.protocolo import msg_solicitar_chain
                return msg_solicitar_chain() 

        elif m_type == MessageType.RESPONSE_CHAIN.value:
            chain_recebida = payload["blockchain"]["chain"]
            if substituir_pela_corrente_mais_longa(no_estado, chain_recebida):
                no_estado["logger"].info("Blockchain sincronizada com a versão mais longa dos peers.")

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
        conectado = False
        resposta = None
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((host, int(port)))
            conectado = True
            # Pede a chain para se sincronizar
            msg = msg_solicitar_chain()
            msg["sender"] = no_estado["address"]
            msgBytes = mensagem_para_bytes(msg)
            sock.sendall(msgBytes)

            try:
                #  Ler o tamanho da mensagem (4 bytes)
                length_data = sock.recv(4)
                if not length_data: 
                    return

                length = int.from_bytes(length_data, 'big')
        
                # 2. Ler o corpo da mensagem (JSON)
                raw_data = sock.recv(length)
                if not raw_data:
                    return

                resposta = bytes_para_mensagem(raw_data)
            except:
                pass
            
        if (conectado == False):
            no_estado["logger"].error(f"Falha ao conectar em {peer_addr}")
            return

        if resposta and resposta["type"] == MessageType.RESPONSE_CHAIN.value:
            block_dict_list = resposta["payload"]["blockchain"]["chain"]
            substituir_pela_corrente_mais_longa(no_estado, block_dict_list)
        else:
            no_estado["logger"].info(f"Aguardando conexão de {peer_addr} via endereço de escuta principal.")

        try:
            conectado = False
            resposta = None
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((host, int(port)))
                conectado = True
                msg = criar_mensagem(MessageType.DISCOVER_PEERS, {}, no_estado.get("address"))
                sock.sendall(mensagem_para_bytes(msg))
                try:
                    #  Ler o tamanho da mensagem (4 bytes)
                    length_data = sock.recv(4)
                    if not length_data: 
                        return

                    length = int.from_bytes(length_data, 'big')
        
                    # 2. Ler o corpo da mensagem (JSON)
                    raw_data = sock.recv(length)
                    if not raw_data:
                        return

                    resposta = bytes_para_mensagem(raw_data)
                    # propagar ping para a lista recebida
                except Exception as e:
                    no_estado["logger"].error(f":Falha ao extrair dados, é possível que o nó mande para o endereço main' {e}")

                if (conectado == False):
                    no_estado["logger"].error(f"Falha ao conectar em {peer_addr}")
                    return
                
                if resposta and resposta["type"] == MessageType.PEERS_LIST.value:
                    novos_peers = set(resposta["payload"]["peers"]) - {no_estado["address"]}
                    adc = novos_peers - no_estado["peers"]
                    if (adc):
                        for p in adc:
                            no_estado["peers"].add(p)
                        propagar_mensagem(no_estado=no_estado, msg=criar_mensagem(MessageType.PING, {}), peers_propag=adc)
                    else:
                        no_estado["logger"].info(f"Não há peers desconhecidos na lista")
                else:
                    no_estado["logger"].info(f"Mensagem recebida no endereço principal.")
        except Exception as e:
            no_estado["logger"].error(f"Falha ao descobrir novos peers: {e}")

        no_estado["logger"].info(f"Conectado ao peer {peer_addr}")
    except Exception as e:
        no_estado["logger"].error(f"Falha ao conectar em {peer_addr}: {e}")

def propagar_mensagem(no_estado: Dict[str, Any], msg: Dict[str, Any], peers_propag: set() = None):
    """Envia uma mensagem para todos os conhecidos (Broadcast)."""
    msg["sender"] = no_estado["address"] # Atualiza quem está enviando agora
    no_estado["logger"].info(f"Mensagem {msg["type"]} propagada para {len(peers_propag)} peers.")
    for peer in list(peers_propag):
        
        def enviar():
            try:
                h, p = peer.split(":")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((h, int(p)))
                    s.sendall(mensagem_para_bytes(msg))
            except:
                pass # Peer offline, ignorar ou remover da lista
        
        threading.Thread(target=enviar).start()