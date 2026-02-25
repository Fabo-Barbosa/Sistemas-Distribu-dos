
# Funções utilitárias para lidar com blocos

import hashlib
import json
import time
from typing import Any, Dict, List

def calcular_hash_bloco(bloco: Dict[str, Any]) -> str:
    """
    Calcula o hash SHA-256 do bloco.
    O hash é baseado em todos os campos exceto o próprio campo 'hash'.
    """
    # Criamos uma cópia para não alterar o bloco original e removemos o hash
    dados_para_hash = bloco.copy()
    dados_para_hash.pop("hash", None) 
    
    # sort_keys=True é VITAL para que o JSON seja sempre igual, 
    # caso contrário, a ordem das chaves mudaria o hash.
    bloco_string = json.dumps(dados_para_hash, sort_keys=True)
    return hashlib.sha256(bloco_string.encode()).hexdigest()

def criar_bloco(index: int, previous_hash: str, transacoes: List[Dict], 
                nonce: int = 0, timestamp: float = None, hash_bloco: str = "") -> Dict[str, Any]:
    """
    Cria a estrutura de um bloco.
    Se não for passado um hash, ele calcula automaticamente.
    """
    bloco = {
        "index": index,
        "previous_hash": previous_hash,
        "transactions": transacoes,
        "nonce": nonce,
        "timestamp": timestamp if timestamp else time.time(),
        "hash": hash_bloco
    }
    
    if not bloco["hash"]:
        bloco["hash"] = calcular_hash_bloco(bloco)
        
    return bloco

def criar_bloco_genesis() -> Dict[str, Any]:
    """
    Gera o bloco inicial da rede (índice 0).
    Conforme o escopo: 'existir um bloco gênesis fixo'.
    """
    return criar_bloco(
        index=0,
        previous_hash="0" * 64,
        transacoes=[],
        nonce=0,
        timestamp=1234567890.0  # Um valor fixo garante que o hash do gênesis seja o mesmo para todos
    )

def validar_proof_of_work(bloco: Dict[str, Any], dificuldade: str = "000") -> bool:
    """
    Verifica se o hash do bloco começa com a quantidade de zeros exigida.
    """
    return bloco["hash"].startswith(dificuldade)