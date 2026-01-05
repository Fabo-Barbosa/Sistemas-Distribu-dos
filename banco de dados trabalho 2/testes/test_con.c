#include <mysql/mysql.h>
#include <stdio.h>
#include <stdlib.h>

void testar_conexao(int porta) {
    MYSQL *conn = mysql_init(NULL);
    
    // Define explicitamente o protocolo TCP
    enum mysql_protocol_type protocolo = MYSQL_PROTOCOL_TCP;
    mysql_options(conn, MYSQL_OPT_PROTOCOL, &protocolo);

    // Tenta conectar
    if (mysql_real_connect(conn, "127.0.0.1", "devmaster", "@DevMaster123", NULL, porta, NULL, 0) == NULL) {
        fprintf(stderr, "Erro na porta %d: %s\n", porta, mysql_error(conn));
        mysql_close(conn);
        return;
    }

    printf("Sucesso! Conectado à instância na porta %d\n", porta);
    mysql_close(conn);
}
int main() {
    printf("Testando conexão com os servidores distribuídos...\n");
    testar_conexao(3306);
    testar_conexao(3307);
    return 0;
}
