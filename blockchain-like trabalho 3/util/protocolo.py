# Protocolo e envelopamento

import json
from enum import Enum
from typing import Any, Dict, List

class MessageType(Enum):
    """Tipos de mensagens."""
    NEW_TRANSACTION = "NEW_TRANSACTION"
    NEW_BLOCK = "NEW_BLOCK"
    REQUEST_CHAIN = "REQUEST_CHAIN"
    RESPONSE_CHAIN = "RESPONSE_CHAIN"
    REQUEST_MEMPOOL = "REQUEST_MEMPOOL"
    RESPONSE_MEMPOOL = "RESPONSE_MEMPOOL"
    PING = "PING"
    PONG = "PONG"
    DISCOVER_PEERS = "DISCOVER_PEERS"
    PEERS_LIST = "PEERS_LIST"

# --- Funções de Serialização ---

def mensagem_para_bytes(mensagem: Dict[str, Any]) -> bytes:
    """
    Converte um dicionário de mensagem em bytes com cabeçalho de tamanho.
    Estrutura: [4 bytes de tamanho (Big Endian)] + [Corpo JSON em UTF-8]
    """
    # Garantir que o tipo seja a string do valor do Enum se necessário
    if isinstance(mensagem["type"], MessageType):
        mensagem["type"] = mensagem["type"].value
        
    corpo_json = json.dumps(mensagem).encode('utf-8')
    tamanho = len(corpo_json)
    return tamanho.to_bytes(4, 'big') + corpo_json

def bytes_para_mensagem(dados: bytes) -> Dict[str, Any]:
    """Converte bytes recebidos do socket de volta para um dicionário."""
    return json.loads(dados.decode('utf-8'))

# --- Factory Functions (Substituem a classe Protocol) ---

def criar_mensagem(tipo: MessageType, payload: Dict, sender: str = "") -> Dict[str, Any]:
    """Função genérica para montar o dicionário da mensagem."""
    return {
        "type": tipo.value,
        "payload": payload,
        "sender": sender
    }

def msg_nova_transacao(transacao: Dict) -> Dict:
    return criar_mensagem(MessageType.NEW_TRANSACTION, {"transaction": transacao})

def msg_novo_bloco(bloco: Dict) -> Dict:
    return criar_mensagem(MessageType.NEW_BLOCK, {"block": bloco})

def msg_solicitar_chain() -> Dict:
    return criar_mensagem(MessageType.REQUEST_CHAIN, {})

def msg_resposta_chain(blockchain_dict: Dict) -> Dict:
    return criar_mensagem(MessageType.RESPONSE_CHAIN, {"blockchain": blockchain_dict})

def msg_solicitar_mempool() -> Dict:
    return criar_mensagem(MessageType.REQUEST_MEMPOOL, {})

def msg_resposta_mempool(transacoes: List[Dict]) -> Dict:
    return criar_mensagem(MessageType.RESPONSE_MEMPOOL, {"transactions": transacoes})

def msg_ping() -> Dict:
    return criar_mensagem(MessageType.PING, {})

def msg_pong() -> Dict:
    return criar_mensagem(MessageType.PONG, {})