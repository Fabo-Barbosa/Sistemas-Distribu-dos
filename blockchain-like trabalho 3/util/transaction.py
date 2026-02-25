# Funções utilitárias para lidar com as transações

import uuid
import time
from typing import Any, Dict

def criar_transacao(origem: str, destino: str, valor: float, 
                     id_transacao: str = None, timestamp: float = None) -> Dict[str, Any]:
    """
    Cria uma estrutura de dados (dicionário) para uma transação.
    Substitui o antigo construtor da classe Transaction.
    """
    
    # Se não for passado um ID ou timestamp (ex: nova transação), gera na hora
    transacao = {
        "id": id_transacao if id_transacao else str(uuid.uuid4()),
        "origem": origem,
        "destino": destino,
        "valor": valor,
        "timestamp": timestamp if timestamp else time.time()
    }
    
    # Validação imediata (Baseada no __post_init__)
    validar_estrutura_transacao(transacao)
    
    return transacao

def validar_estrutura_transacao(transacao: Dict[str, Any]) -> bool:
    """
    Valida se a transação possui os campos obrigatórios e valores permitidos.
    Assegura a regra do escopo: apenas valores positivos.
    """
    if transacao["valor"] <= 0:
        raise ValueError("Erro: O valor da transação deve ser positivo.")
    
    if not transacao["origem"] or not transacao["destino"]:
        raise ValueError("Erro: Origem e destino são obrigatórios.")
    
    return True

def comparar_transacoes(t1: Dict[str, Any], t2: Dict[str, Any]) -> bool:
    """Substitui o método __eq__."""
    return t1["id"] == t2["id"]

# Nota: to_dict e from_dict tornam-se obsoletos, pois a transação 
# JÁ É um dicionário pronto para ser serializado via json.dumps().