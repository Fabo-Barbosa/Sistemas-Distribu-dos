# mineração com proof of work

import time
from typing import Any, Dict, List, Optional, Callable
from .transaction import criar_transacao
from .block import criar_bloco, calcular_hash_bloco, validar_proof_of_work

# Configuração da Recompensa
RECOMPENSA_MINERACAO = 50.0

def minerar_bloco(
    no_estado: Dict[str, Any], 
    endereco_minerador: str,
    dificuldade: str = "000",
    on_progress: Optional[Callable[[int], None]] = None
) -> Optional[Dict[str, Any]]:

    #Executa o algoritmo de Proof of Work.
    #
    #Retorna o bloco minerado ou None se a mineração for interrompida 
    #(ex: no_estado['mining_active'] alterado para False).

    blockchain = no_estado["blockchain"]
    
    # 1. Prepara as transações (Cópia das pendentes + Coinbase)
    with no_estado["lock"]:
        transacoes_candidatas = list(blockchain["pending_transactions"])
    
    timestamp_bloco = time.time()
    
    # Adiciona transação de recompensa (Coinbase) no início da lista
    coinbase_tx = criar_transacao(
        origem="coinbase",
        destino=endereco_minerador,
        valor=RECOMPENSA_MINERACAO,
        timestamp=timestamp_bloco
    )
    transacoes_candidatas.insert(0, coinbase_tx)

    # 2. Prepara o bloco candidato
    ultimo_bloco = blockchain["chain"][-1]
    bloco = criar_bloco(
        index=len(blockchain["chain"]),
        previous_hash=ultimo_bloco["hash"],
        transacoes=transacoes_candidatas,
        nonce=0,
        timestamp=timestamp_bloco
    )

    # 3. Loop de Proof of Work
    no_estado["mining_active"] = True
    no_estado["logger"].info(f"Minerando bloco #{bloco['index']}...")

    while no_estado["mining_active"]:
        # Calcula o hash atual com o nonce presente
        bloco["hash"] = calcular_hash_bloco(bloco)

        # Verifica se atingiu a dificuldade
        if validar_proof_of_work(bloco, dificuldade):
            no_estado["mining_active"] = False
            return bloco

        # Incrementa o nonce para a próxima tentativa
        bloco["nonce"] += 1

        # Reporta progresso opcionalmente (para logs ou interface)
        if on_progress and bloco["nonce"] % 10000 == 0:
            on_progress(bloco["nonce"])
            
    return None

def interromper_mineracao(no_estado: Dict[str, Any]):
    """Sinaliza para a função de mineração parar o loop atual."""
    no_estado["mining_active"] = False