import sqlite3

# Conecta (ou cria) o banco de dados
conn = sqlite3.connect("petcare.db")
cursor = conn.cursor()

# Cria a tabela de itens de atendimento, se não existir
cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_atendimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_agendamento INTEGER,
    titulo TEXT,
    descricao TEXT,
    FOREIGN KEY (id_agendamento) REFERENCES agendamento(id)
)
""")

conn.commit()
conn.close()
print("Tabela 'itens_atendimento' criada com sucesso!")
