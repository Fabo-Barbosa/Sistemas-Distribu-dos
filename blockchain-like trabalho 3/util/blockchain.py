# Funções utilitárias para lidar com a blockchain

from typing import Any, Dict, List
from .block import criar_bloco_genesis, calcular_hash_bloco, validar_proof_of_work
from .transaction import comparar_transacoes

# Configurações Globais
DIFICULDADE = "000"

def iniciar_blockchain() -> Dict[str, Any]:
    """
    Inicializa o estado da blockchain.
    Substitui o __init__ da classe.
    """
    return {
        "chain": [criar_bloco_genesis()],
        "pending_transactions": []
    }

def obter_ultimo_bloco(blockchain: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna o último bloco da lista 'chain'."""
    return blockchain["chain"][-1]

def calcular_saldo(blockchain: Dict[str, Any], endereco: str) -> float:
    """
    Calcula o saldo percorrendo toda a cadeia e transações pendentes.
    Regra do escopo: não permitir saldo negativo.
    """
    saldo = 0.0
    
    # 1. Saldo em blocos confirmados
    for bloco in blockchain["chain"]:
        for tx in bloco["transactions"]:
            if tx["destino"] == endereco:
                saldo += tx["valor"]
            if tx["origem"] == endereco:
                saldo -= tx["valor"]
                
    # 2. Subtrai transações que já saíram da conta mas estão na mempool
    for tx in blockchain["pending_transactions"]:
        if tx["origem"] == endereco:
            saldo -= tx["valor"]
            
    return saldo

def adicionar_transacao(blockchain: Dict[str, Any], transacao: Dict[str, Any], confiavel: bool = False) -> bool:
    """
    Tenta adicionar uma transação à lista de pendentes.
    """
    # Evita duplicatas na mempool
    if any(comparar_transacoes(tx, transacao) for tx in blockchain["pending_transactions"]):
        return False
        
    # Evita duplicatas em blocos já minerados
    for bloco in blockchain["chain"]:
        if any(comparar_transacoes(tx, transacao) for tx in bloco["transactions"]):
            return False
            
    # Validação de saldo (exceto para geração inicial de moedas)
    if not confiavel and transacao["origem"] not in ("genesis", "coinbase"):
        saldo_atual = calcular_saldo(blockchain, transacao["origem"])
        if saldo_atual < transacao["valor"]:
            return False
            
    blockchain["pending_transactions"].append(transacao)
    return True

def validar_bloco(blockchain: Dict[str, Any], bloco: Dict[str, Any]) -> bool:
    """Valida se o bloco pode ser inserido na cadeia atual."""
    ultimo = obter_ultimo_bloco(blockchain)
    
    # Verifica continuidade
    if bloco["index"] != len(blockchain["chain"]):
        return False
    if bloco["previous_hash"] != ultimo["hash"]:
        return False
        
    # Verifica integridade matemática e PoW
    if not validar_proof_of_work(bloco, DIFICULDADE):
        return False
    if bloco["hash"] != calcular_hash_bloco(bloco):
        return False
        
    return True

def adicionar_bloco(blockchain: Dict[str, Any], bloco: Dict[str, Any]) -> bool:
    """Valida e anexa o bloco, limpando a mempool."""
    if not validar_bloco(blockchain, bloco):
        return False
        
    # Remove da mempool as transações que agora estão confirmadas neste bloco
    ids_no_bloco = [tx["id"] for tx in bloco["transactions"]]
    blockchain["pending_transactions"] = [
        tx for tx in blockchain["pending_transactions"] 
        if tx["id"] not in ids_no_bloco
    ]
    
    blockchain["chain"].append(bloco)
    return True

def validar_cadeia_completa(chain: List[Dict]) -> bool:
    """
    Verifica se uma lista de blocos é uma blockchain válida.
    Útil para quando recebemos a cadeia de outro nó.
    """
    if not chain: return False
    
    # Valida Gênesis
    genesis_esperado = criar_bloco_genesis()
    if chain[0]["hash"] != genesis_esperado["hash"]:
        return False
        
    # Valida o encadeamento
    for i in range(1, len(chain)):
        bloco_atual = chain[i]
        bloco_anterior = chain[i-1]
        
        if bloco_atual["previous_hash"] != bloco_anterior["hash"]:
            return False
        if bloco_atual["hash"] != calcular_hash_bloco(bloco_atual):
            return False
        if not validar_proof_of_work(bloco_atual, DIFICULDADE):
            return False
            
    return True