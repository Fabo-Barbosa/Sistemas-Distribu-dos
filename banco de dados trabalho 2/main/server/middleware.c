#include <mysql/mysql.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define MID_PORT 5000
#define DB_USER "devmaster"
#define DB_PASS "@DevMaster123"
#define DB_NAME "projeto_distribuido"

// Função para formatar os resultados de um SELECT em uma string
void buscar_e_anexar_dados(MYSQL *conn, char *query, char *buffer_destino, char *prefixo) {
    if (mysql_query(conn, query)) return;

    MYSQL_RES *res = mysql_store_result(conn);
    if (res == NULL) return;

    MYSQL_ROW row;
    int num_fields = mysql_num_fields(res);
    char linha[256];

    while ((row = mysql_fetch_row(res))) {
        strcat(buffer_destino, prefixo);
        strcat(buffer_destino, " | ");
        for (int i = 0; i < num_fields; i++) {
            sprintf(linha, "%s%s", row[i] ? row[i] : "NULL", i == num_fields - 1 ? "" : " | ");
            strcat(buffer_destino, linha);
        }
        strcat(buffer_destino, "\n");
    }
    mysql_free_result(res);
}

MYSQL* conectar_banco(int porta) {
    MYSQL *conn = mysql_init(NULL);
    enum mysql_protocol_type protocolo = MYSQL_PROTOCOL_TCP;
    mysql_options(conn, MYSQL_OPT_PROTOCOL, &protocolo);
    if (mysql_real_connect(conn, "127.0.0.1", DB_USER, DB_PASS, DB_NAME, porta, NULL, 0) == NULL) return NULL;
    return conn;
}

int main() {
    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);
    char query_cliente[1024];

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(MID_PORT);
    bind(server_fd, (struct sockaddr *)&address, sizeof(address));
    listen(server_fd, 3);

    printf("--- Middleware Agregador Online (Porta %d) ---\n", MID_PORT);

    while(1) {
        new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen);
        memset(query_cliente, 0, 1024);
        read(new_socket, query_cliente, 1024);

        MYSQL *connA = conectar_banco(3306);
        MYSQL *connB = conectar_banco(3307);
        char resposta[8192] = ""; // Buffer grande para os dados

        // Lógica de Decisão: É SELECT ou ALTERAÇÃO?
        if (strncasecmp(query_cliente, "SELECT", 6) == 0) {
            strcat(resposta, "FONTE | DADOS DOS BANCOS\n------------------------\n");
            if (connA) buscar_e_anexar_dados(connA, query_cliente, resposta, "NÓ A");
            if (connB) buscar_e_anexar_dados(connB, query_cliente, resposta, "NÓ B");
        } else {
            // Lógica para INSERT, UPDATE, DELETE
            int resA = connA ? mysql_query(connA, query_cliente) : -1;
            int resB = connB ? mysql_query(connB, query_cliente) : -1;
            if (resA == 0 && resB == 0) sprintf(resposta, "OK: Sincronizado em ambos os nós.");
            else sprintf(resposta, "ERR: Erro na gravação distribuída.");
        }

        send(new_socket, resposta, strlen(resposta), 0);
        if(connA) mysql_close(connA);
        if(connB) mysql_close(connB);
        close(new_socket);
    }
    return 0;
}