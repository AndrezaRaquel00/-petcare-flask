# Importa as bibliotecas necessárias
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv
import sqlite3
# imports necessários 
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from flask import send_file, jsonify
from datetime import datetime, date

import qrcode
import io
from email.mime.text import MIMEText




def criar_tabelas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Tabela de agendamento
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT,
            nome_pet TEXT,
            tipo_servico TEXT,
            data TEXT,
            horario TEXT,
            observacoes TEXT
        )
    """)

    # Tabela itens atendimento
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_atendimento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_agendamento INTEGER,
            titulo TEXT,
            descricao TEXT,
            FOREIGN KEY (id_agendamento) REFERENCES agendamento (id)
        )
    """)

    # Tabela sugestões
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sugestoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_servico TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT
        )
    """)

    # Tabela notificações
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            lida INTEGER DEFAULT 0,
            data TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Tabelas criadas (ou já existiam).")



load_dotenv()

app = Flask(__name__)
app.secret_key = "petcare_secret"  # Necessário para usar flash messages
criar_tabelas()

# debug: liste as rotas no startup
print("Rotas disponíveis:")
for r in app.url_map.iter_rules():
    print(r)



# Configurações do e-mail vindas do .env
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

mail = Mail(app)

import logging
logging.basicConfig(level=logging.DEBUG)


def enviar_email(assunto, corpo):
    """Envia e-mail para a empresa confirmando o cadastro"""
    destinatario = os.getenv("MAIL_USERNAME")  # o e-mail da empresa recebe
    msg = Message(
        subject=assunto,
        sender=os.getenv("MAIL_USERNAME"),   # 👈 Define o remetente
        recipients=[destinatario]
    )
    msg.body = corpo
    mail.send(msg)


# -------------------------
# ROTAS DE CADASTRO
# -------------------------

# 🔹 Novo Cliente
@app.route("/clientes/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cliente (nome_cliente, nome_pet, telefone, email, endereco)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, telefone, email, endereco))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
📩 Novo Cliente Cadastrado!

Nome: {nome_cliente}
Pet: {nome_pet}
Telefone: {telefone}
E-mail: {email}
Endereço: {endereco}
"""
        enviar_email("Novo Cliente Cadastrado", corpo)

        flash("Cliente cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_clientes"))
    
    return render_template("novo_cliente.html")

# 🔹 Novo Pet
@app.route("/pets/novo", methods=["GET", "POST"])
def novo_pet():
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_cliente = request.form["nome_cliente"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form.get("peso")

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_cliente, raca, idade, peso))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
🐾 Novo Pet Cadastrado!

Nome do Pet: {nome_pet}
Tutor: {nome_cliente}
Raça: {raca}
Idade: {idade}
Peso: {peso} 
"""
        enviar_email("Novo Pet Cadastrado", corpo)
        
        cursor.execute("""
            INSERT INTO notificacoes (mensagem, lida, data)
            VALUES (?, 0, DATE('now'))
        """, (
            f"Novo Cliente: {nome_pet} {nome_cliente} {raca} {idade} {peso}",
        ))


        flash("Pet cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_pets"))

    return render_template("novo_pet.html")

# --- Função de recomendação simples (colocar antes da rota novo_agendamento) ---
def recomendar_servicos(tipo_servico):
    """
    Retorna uma lista de sugestões (serviços ou produtos) baseadas no tipo_servico.
    Mantém tudo em memória para não mexer no banco. Fácil de estender depois.
    """
    if not tipo_servico:
        return []

    t = tipo_servico.lower()

    # recomendações fixas por serviço (exemplo)
    sugestoes_por_servico = {
        'banho': [
            {"titulo": "Shampoo especial (500ml)", "descricao": "Hipoalergênico — complementar ao banho"},
            {"titulo": "Escovação extra", "descricao": "Remove pelos soltos — +15 min"},
            {"titulo": "Check-up rápido (gratuito)", "descricao": "Verificar pele e pulgas"}
        ],
        'tosa': [
            {"titulo": "Hidratação pós-tosa", "descricao": "Melhora o aspecto do pelo"},
            {"titulo": "Tosa higiênica adicional", "descricao": "Ajustes finos após a tosa"},
            {"titulo": "Corta-unhas", "descricao": "Serviço rápido"}
        ],
        'consulta': [
            {"titulo": "Vacinação (se necessário)", "descricao": "Verificar calendário vacinal"},
            {"titulo": "Exame rápido (olho/orelhas)", "descricao": "Rápido check-up complementar"},
            {"titulo": "Medicamentos (caso prescrito)", "descricao": "Entregar direto ao tutor"}
        ],
        'vacinação': [
            {"titulo": "Cartão de vacinação atualizado", "descricao": "Emitir recibo/caderneta"},
            {"titulo": "Vermífugo (opcional)", "descricao": "Complemento recomendado"},
            {"titulo": "Agendamento de retorno", "descricao": "Lembrete de dose posterior"}
        ]
    }

    # sugestões gerais (fallback)
    sugestoes_gerais = [
        {"titulo": "Pacote mensal (banho + tosa)", "descricao": "Economize com pacotes"},
        {"titulo": "Escova de dentes pet", "descricao": "Higiene bucal preventiva"},
        {"titulo": "Toalha microfibra", "descricao": "Produto à venda na recepção"}
    ]

    # tenta encontrar por correspondência exata; senão retorna gerais
    if t in sugestoes_por_servico:
        return sugestoes_por_servico[t] + sugestoes_gerais[:1]
    # tentar match parcial (ex: 'vacina' dentro de 'vacinação')
    for chave in sugestoes_por_servico.keys():
        if chave in t:
            return sugestoes_por_servico[chave] + sugestoes_gerais[:1]

    return sugestoes_gerais 

# 🔹 Novo Agendamento
@app.route("/agendamentos/novo", methods=["GET", "POST"])
def novo_agendamento():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes))

        conn.commit()
        conn.close()

        flash("Agendamento salvo com sucesso!", "success")
        return redirect(url_for("listar_agendamentos"))

    return render_template("novo_agendamento.html")



from flask import jsonify

@app.route("/agendamentos/<int:id_agendamento>/itens/adicionar", methods=["POST"])
def adicionar_item_atendimento(id_agendamento):
    data = request.get_json() or {}
    titulo = data.get("titulo")
    descricao = data.get("descricao", "")
    preco = float(data.get("preco", 0) or 0)

    if not titulo:
        return jsonify({"status": "error", "message": "Título obrigatório"}), 400

    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO itens_atendimento (id_agendamento, titulo, descricao, preco)
        VALUES (?, ?, ?, ?)
    """, (id_agendamento, titulo, descricao, preco))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Item adicionado ao atendimento", "titulo": titulo})

import sqlite3

def recomendar_servicos_por_historico(tipo_servico, limit=4):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.titulo, i.descricao, COUNT(*) as total
        FROM itens_atendimento i
        JOIN agendamento a ON i.id_agendamento = a.id
        WHERE LOWER(a.tipo_servico) = LOWER(?)
        GROUP BY i.titulo, i.descricao
        ORDER BY total DESC
        LIMIT ?
    """, (tipo_servico, limit))
    rows = cursor.fetchall()
    conn.close()

    sugestoes = []
    for r in rows:
        sugestoes.append({
            'titulo': r[0],
            'descricao': r[1] or "",
            'count': r[2]
        })
    return sugestoes

from sklearn.neighbors import NearestNeighbors
import numpy as np

def recomendar_por_similaridade():
    """
    Cria recomendações de serviços baseadas na similaridade entre agendamentos.
    Usa KNN com base no tipo de serviço (modelo simples de exemplo).
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, tipo_servico FROM agendamento")
    dados = cursor.fetchall()
    conn.close()

    if not dados:
        return []

    # Codificar tipos de serviço em números
    servicos_unicos = list(set([d[1] for d in dados]))
    mapa_servicos = {s: i for i, s in enumerate(servicos_unicos)}

    X = np.array([[mapa_servicos[d[1]]] for d in dados])

    # Treinar modelo
    knn = NearestNeighbors(n_neighbors=2, metric='euclidean')
    knn.fit(X)

    sugestoes = []
    for i, (cliente, servico) in enumerate(dados):
        distances, indices = knn.kneighbors([[mapa_servicos[servico]]])
        similares = [dados[j][1] for j in indices[0] if j != i]
        if similares:
            sugestoes.append((servico, similares[0]))

    # Remover duplicados
    sugestoes = list(set(sugestoes))
    return sugestoes



# 🔹 Exibir recomendações baseadas no tipo de serviço
@app.route("/agendamentos/<int:id_agendamento>/recomendacoes")
def recomendacoes(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamento WHERE id = ?", (id_agendamento,))
    agendamento = cursor.fetchone()
    conn.close()

    if not agendamento:
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    pet, servico = agendamento
    sugestoes = recomendar_servicos_por_historico(servico)

    # 👇 Aqui usamos o nome correto do seu template
    return render_template(
        "recomendacoes_funcionario.html",
        id_agendamento=id_agendamento,
        pet=pet,
        servico=servico,
        sugestoes=sugestoes
    )


# 🔹 Adicionar item ao atendimento
@app.route("/agendamentos/<int:id_agendamento>/adicionar_item", methods=["POST"])
def adicionar_item(id_agendamento):
    titulo = request.form.get("titulo")
    descricao = request.form.get("descricao")

    # Evita salvar valores nulos ou "None"
    if not titulo or titulo.lower() == "none":
        flash("Erro: título inválido para o item.")
        return redirect(url_for("ver_agendamento", id=id_agendamento))

    # Abre conexão
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Evita duplicar o mesmo item no mesmo agendamento
    cursor.execute("""
        SELECT COUNT(*) FROM itens_atendimento
        WHERE id_agendamento = ? AND titulo = ? AND descricao = ?
    """, (id_agendamento, titulo, descricao))
    ja_existe = cursor.fetchone()[0]

    if ja_existe == 0:
        cursor.execute("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, (id_agendamento, titulo, descricao))
        conn.commit()
        flash("Item adicionado ao atendimento com sucesso!")
    else:
        flash("Este item já foi adicionado a este atendimento.")

    conn.close()

    return redirect(url_for("ver_agendamento", id=id_agendamento))

from flask import render_template, request, redirect, url_for
import sqlite3
@app.route("/agendamentos/<int:id_agendamento>/sugestoes")
def sugestoes_agendamento(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Pega dados do agendamento
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamentos WHERE id = ?", (id_agendamento,))
    ag = cursor.fetchone()

    if not ag:
        conn.close()
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    nome_pet, tipo_servico = ag

    # Pega sugestões (fixas ou do banco)
    cursor.execute("""
        SELECT titulo, descricao 
        FROM sugestoes
        WHERE servico = ? OR servico = 'Geral'
    """, (tipo_servico,))

    rows = cursor.fetchall()
    sugestoes = [{"titulo": r[0], "descricao": r[1]} for r in rows]

    conn.close()

    return render_template(
        "sugestoes.html",
        nome_pet=nome_pet,
        tipo_servico=tipo_servico,
        sugestoes=sugestoes,
        id_agendamento=id_agendamento
    )


import unicodedata

# 🔹 Ver detalhes de um agendamento (corrigido com normalização de acentos)
@app.route("/agendamentos/<int:id>")
def ver_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome_cliente, nome_pet, tipo_servico, data, horario, observacoes
        FROM agendamentos
        WHERE id = ?
    """, (id,))
    agendamento = cursor.fetchone()

    # Itens do atendimento
    cursor.execute("""
        SELECT titulo, descricao
        FROM itens_atendimento
        WHERE id_agendamento = ?
    """, (id,))
    itens = cursor.fetchall()

    conn.close()

    return render_template(
        "ver_agendamento.html",
        agendamento=agendamento,
        itens=itens
    )

# -------------------------
# OUTRAS ROTAS
# -------------------------

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/agendamentos")
def listar_agendamentos():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agendamentos ORDER BY data, horario")
    agendamentos = cursor.fetchall()
    conn.close()
    return render_template("agendamentos.html", agendamentos=agendamentos)

@app.route("/clientes")
def listar_clientes():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()
    return render_template("clientes.html", clientes=clientes)

@app.route("/pets")
def listar_pets():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pet ORDER BY nome_pet")
    pets = cursor.fetchall()
    conn.close()
    return render_template("pets.html", pets=pets)

@app.route("/petbot")
def petbot():
    return render_template("chatbot.html")


# -------------------------
# CRUD de edição e exclusão
# -------------------------

@app.route("/agendamentos/editar/<int:id>", methods=["GET", "POST"])
def editar_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        cursor.execute("""
            UPDATE agendamento
            SET nome_cliente=?, nome_pet=?, tipo_servico=?, data=?, horario=?, observacoes=?
            WHERE id=?
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_agendamentos"))

    cursor.execute("SELECT * FROM agendamento WHERE id=?", (id,))
    agendamento = cursor.fetchone()
    conn.close()
    return render_template("editar_agendamento.html", agendamento=agendamento)

@app.route("/agendamentos/excluir/<int:id>")
def excluir_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agendamento WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_agendamentos"))

@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        cursor.execute("""
            UPDATE cliente
            SET nome_cliente=?, nome_pet=?, telefone=?, email=?, endereco=?
            WHERE id=?
        """, (nome_cliente, nome_pet, telefone, email, endereco, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_clientes"))

    cursor.execute("SELECT * FROM cliente WHERE id=?", (id,))
    cliente = cursor.fetchone()
    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

@app.route("/clientes/excluir/<int:id>")
def excluir_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cliente WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_clientes"))

@app.route("/pets/editar/<int:id>", methods=["GET", "POST"])
def editar_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_tutor = request.form["nome_tutor"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form["peso"]

        cursor.execute("""
            UPDATE pet
            SET nome_pet=?, nome_tutor=?, raca=?, idade=?, peso=?
            WHERE id=?
        """, (nome_pet, nome_tutor, raca, idade, peso, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_pets"))

    cursor.execute("SELECT * FROM pet WHERE id=?", (id,))
    pet = cursor.fetchone()
    conn.close()
    return render_template("editar_pet.html", pet=pet)

@app.route("/pets/excluir/<int:id>")
def excluir_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pet WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_pets"))

# -------------------------
# FINANÇAS
# -------------------------
@app.route('/financas')
def financas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cliente")
    total_clientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pet")
    total_pets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM agendamento")
    total_agendamentos = cursor.fetchone()[0]

    cursor.execute("SELECT tipo_servico, COUNT(*) FROM agendamento GROUP BY tipo_servico")
    dados = cursor.fetchall()
    tipos = [linha[0] for linha in dados]
    contagens = [linha[1] for linha in dados]

    precos = {
        'Banho': 40,
        'Tosa': 80,
        'Consulta': 100,
        'Vacinação': 70
    }

    cursor.execute("SELECT tipo_servico FROM agendamento")
    todos = cursor.fetchall()
    lucro_total = sum(precos.get(t[0], 0) for t in todos)

    from datetime import date
    hoje = date.today().isoformat()
    cursor.execute("SELECT tipo_servico FROM agendamento WHERE data > ?", (hoje,))
    futuros = cursor.fetchall()
    lucro_futuro = sum(precos.get(t[0], 0) for t in futuros)

    conn.close()

    return render_template("financas.html",
                           total_clientes=total_clientes,
                           total_pets=total_pets,
                           total_agendamentos=total_agendamentos,
                           tipos=tipos,
                           contagens=contagens,
                           lucro_total=lucro_total,
                           lucro_futuro=lucro_futuro)
    


# -------------------------
# BANCO DE DADOS
# -------------------------
def init_db():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            tipo_servico TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            observacoes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            endereco TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pet TEXT NOT NULL,
            nome_tutor TEXT NOT NULL,
            raca TEXT,
            idade INTEGER,
            peso REAL
        )
    ''')

    conn.commit()
    conn.close()
    
def seed_itens_iniciais():
    """Popula a tabela itens_atendimento com sugestões iniciais (somente se estiver vazia)."""
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM itens_atendimento")
    total = cursor.fetchone()[0]

    if total == 0:
        print("🌱 Inserindo sugestões iniciais na tabela itens_atendimento...")

        itens_iniciais = [
            # Banho
            (1, "Shampoo especial", "Hipoalergênico — complementar ao banho"),
            (1, "Escovação extra", "Remove pelos soltos — +15 min"),
            (1, "Check-up rápido", "Verificar pele e pulgas"),

            # Tosa
            (1, "Hidratação pós-tosa", "Melhora o aspecto do pelo"),
            (1, "Tosa higiênica adicional", "Ajustes finos após a tosa"),
            (1, "Corta-unhas", "Serviço rápido"),

            # Consulta
            (1, "Vacinação (se necessário)", "Verificar calendário vacinal"),
            (1, "Exame rápido (olho/orelhas)", "Rápido check-up complementar"),
            (1, "Medicamentos (caso prescrito)", "Entregar direto ao tutor"),

            # Vacinação
            (1, "Cartão de vacinação atualizado", "Emitir recibo/caderneta"),
            (1, "Vermífugo (opcional)", "Complemento recomendado"),
            (1, "Agendamento de retorno", "Lembrete de dose posterior"),
        ]

        cursor.executemany("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, itens_iniciais)

        conn.commit()
        print("✅ Sugestões iniciais inseridas com sucesso.")
    else:
        print(f"ℹ️ Tabela já possui {total} itens. Nenhuma inserção feita.")

    conn.close()


# -------------------------
# START
# -------------------------

import sqlite3

def listar_agendamentos_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome_pet, tipo_servico, data, horario
        FROM agendamento
        ORDER BY 
            substr(data, 7, 4),
            substr(data, 4, 2),
            substr(data, 1, 2),
            horario
    """)
    agds = cursor.fetchall()
    conn.close()

    if not agds:
        return "Nenhum agendamento encontrado. 📭"

    linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
    return "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)


def listar_clientes_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()

    if not clientes:
        return "Nenhum cliente cadastrado ainda. 📭"

    linhas = [f"👤 {c[0]} (Pet: {c[1]})" for c in clientes]
    return "Aqui estão os clientes cadastrados:\n" + "\n".join(linhas)


from flask import jsonify, request
import re

# memória de contexto simples
user_context = {}

from unidecode import unidecode

from unidecode import unidecode
from flask import request, jsonify

from unidecode import unidecode
from flask import request, jsonify

from flask import jsonify, request
import sqlite3
import re
from unidecode import unidecode

@app.route("/api/chat_simple", methods=["POST"])
def api_chat_simple():
    data = request.get_json()
    user_message = data.get("message", "").strip().lower()
    user_message = unidecode(user_message)  # remove acentos

    # ========= RESPOSTAS BÁSICAS =========
    if any(p in user_message for p in ["oi", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"response": "Olá! 😊 Como posso te ajudar hoje?"})

    if any(p in user_message for p in ["obrigado", "obrigada", "valeu", "agradecido", "vlw"]):
        return jsonify({"response": "De nada! 😄 Sempre à disposição."})

    # ========= LISTAR PETS =========
        # ========= LISTAR PETS =========
    # ========= LISTAR PETS =========
    if "listar pets" in user_message or "meus pets" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, nome_tutor, raca FROM pet")
        pets = cursor.fetchall()
        conn.close()

        if pets:
            lista = "\n".join([
                f"🐾 Pet: {p[0]}\n   👤 Tutor: {p[1]}\n   🐶 Raça: {p[2]}"
                for p in pets
            ])
            return jsonify({"response": f"Aqui estão os pets cadastrados:\n\n{lista}"})
        else:
            return jsonify({"response": "Nenhum pet cadastrado ainda. 🐾"})



    # ========= LISTAR CLIENTES =========
    if "listar clientes" in user_message or "clientes" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_cliente, nome_pet FROM cliente")
        clientes = cursor.fetchall()
        conn.close()

        if clientes:
            lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
            return jsonify({"response": f"Aqui estão os clientes cadastrados:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum cliente cadastrado ainda."})


    # ========= LISTAR AGENDAMENTOS =========
    if "listar agendamentos" in user_message or "agendamentos" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, tipo_servico, data, horario FROM agendamentos ORDER BY data, horario")
        ags = cursor.fetchall()
        conn.close()

        if ags:
            lista = "\n".join([f"📅 {a[0]} - {a[1]} em {a[2]} às {a[3]}" for a in ags])
            return jsonify({"response": f"Aqui estão os agendamentos:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum agendamento encontrado."})

    # ========= CASO PADRÃO =========
    return jsonify({"response": "Desculpe, não entendi 😅. Você pode pedir para listar pets, clientes ou agendamentos."})


from flask import jsonify
import re
import sqlite3
from datetime import datetime, timedelta

@app.route("/api/chat_acoes", methods=["POST"])
def api_chat_acoes():
    data = request.get_json()
    msg = data.get("message", "").lower().strip()

    # === INTERPRETA SAUDAÇÕES ===
    if any(p in msg for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"reply": "Olá! Eu sou o PetBot 🐾 Como posso te ajudar hoje?"})

    # === INTERPRETA PEDIDO DE AGENDAMENTO ===
    if any(k in msg for k in ["agendar", "agd", "marcar"]) and "listar" not in msg:
        servicos = ["banho", "tosa", "consulta", "vacinação", "vacina"]
        tipo_servico = next((s for s in servicos if s in msg), None)

        if "amanh" in msg:
            data_agendamento = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        elif "hoje" in msg:
            data_agendamento = datetime.now().strftime("%d/%m/%Y")
        else:
            m_data = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", msg)
            data_agendamento = m_data.group(1) if m_data else None

        m_hora = re.search(r"(\d{1,2}[:h]\d{0,2})", msg)
        horario = m_hora.group(1).replace("h", ":00") if m_hora else None

        m_pet = re.search(r"para\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        nome_pet = m_pet.group(1).capitalize() if m_pet else "Pet não informado"

        if not all([tipo_servico, data_agendamento, horario]):
            return jsonify({"reply": "Preciso de mais informações: serviço, data e horário. Pode me dizer tudo de uma vez? 😊"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Empresa", nome_pet, tipo_servico.capitalize(), data_agendamento, horario, "Agendado via PetBot"))

        conn.commit()
        conn.close()

        return jsonify({
            "reply": f"Agendamento de {tipo_servico} para {nome_pet} em {data_agendamento} às {horario} registrado com sucesso! ✅"
        })

    # === INTERPRETA CADASTRO DE PET ===
    if "cadastrar pet" in msg or "novo pet" in msg:
        nome = re.search(r"pet\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        tutor = re.search(r"tutor\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        raca = re.search(r"ra[çc]a\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        idade = re.search(r"idade\s+(\d+)", msg)
        peso = re.search(r"peso\s+(\d+[.,]?\d*)", msg)

        nome_pet = nome.group(1).capitalize() if nome else None
        nome_tutor = tutor.group(1).capitalize() if tutor else None
        raca_pet = raca.group(1).capitalize() if raca else None
        idade_pet = int(idade.group(1)) if idade else None
        peso_pet = float(peso.group(1).replace(",", ".")) if peso else None

        if not all([nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet]):
            return jsonify({"reply": "Faltam alguns dados! Diga tudo na mesma frase: ex: 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg' 🐶"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet))
        conn.commit()
        conn.close()

        return jsonify({"reply": f"Pet {nome_pet} cadastrado com sucesso! 🐾"})

    # === LISTAR PETS ===
    if "listar" in msg and "pet" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_pet, nome_tutor FROM pet ORDER BY nome_pet")
            pets = cursor.fetchall()
            conn.close()

            if pets:
                lista = "\n".join([f"🐶 {p[0]} (Tutor: {p[1]})" for p in pets])
                reply = f"Aqui estão os pets cadastrados:\n{lista}"
            else:
                reply = "Não há pets cadastrados ainda. 🐾"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR CLIENTES ===
    if "listar" in msg and "cliente" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
            clientes = cursor.fetchall()
            conn.close()

            if clientes:
                lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
                reply = f"Aqui estão os clientes cadastrados:\n{lista}"
            else:
                reply = "Nenhum cliente cadastrado ainda. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR AGENDAMENTOS ===
    if "listar" in msg and "agendamento" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT nome_pet, tipo_servico, data, horario
                FROM agendamento
                WHERE nome_pet IS NOT NULL
                ORDER BY 
                    substr(data, 7, 4),  -- ano
                    substr(data, 4, 2),  -- mês
                    substr(data, 1, 2),  -- dia
                    horario
            """)
            agds = cursor.fetchall()
            conn.close()

            if agds:
                linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
                reply = "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)
            else:
                reply = "Nenhum agendamento encontrado. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === OUTRAS INTERAÇÕES ===
    if any(p in msg for p in ["obrigado", "valeu"]):
        return jsonify({"reply": "De nada! 😺 Sempre que precisar, estarei por aqui!"})

    if any(p in msg for p in ["tchau", "até", "flw", "falou"]):
        return jsonify({"reply": "Tchau tchau! 👋 Espero te ver em breve!"})
    

    # === CASO NÃO ENTENDA ===
    return jsonify({
        "reply": "Desculpe, não entendi bem. Você pode tentar algo como: 'Agendar banho amanhã às 15h para Luna' ou 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg'."
    })
    
    def recomendar_servicos(servico_base):
        """Sugere serviços ou produtos relacionados ao agendamento atual"""
    recomendacoes = {
        "banho": ["tosa", "hidratação", "perfume pet"],
        "tosa": ["banho", "corte de unhas"],
        "consulta": ["vacinação", "vermifugação"],
        "vacinação": ["vermifugação", "check-up"],
    }

    return recomendacoes.get(servico_base.lower(), ["Sem recomendações no momento"])

# 🔹 Página de FAQs
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")

def servicos_mais_populares(limit=4):
    """
    Retorna os serviços mais agendados, para exibir na home.
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo_servico, COUNT(*) AS total
        FROM agendamento
        GROUP BY tipo_servico
        ORDER BY total DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/previsoes")
def previsoes():
    # renderiza o template com o mockup; você pode passar dados reais aqui ou carregá-los via AJAX
    return render_template("previsoes.html")

@app.route("/previsao_image")
def previsao_image():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    # pega datas (no formato que você tem no banco: pode ser 'dd/mm/YYYY' ou 'YYYY-mm-dd')
    cursor.execute("SELECT data FROM agendamento WHERE data IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    datas = [r[0] for r in rows]

    if not datas:
        # retorna imagem simples com texto ou um JSON
        return "Ainda não há dados suficientes para previsão.", 400

    # normaliza formatos: detecta se tem '/' -> dd/mm/YYYY else assume ISO yyyy-mm-dd
    normalized = []
    for d in datas:
        if "/" in d:
            # dd/mm/YYYY
            try:
                dt = pd.to_datetime(d, format="%d/%m/%Y", dayfirst=True)
            except Exception:
                dt = pd.to_datetime(d, dayfirst=True, errors='coerce')
        else:
            try:
                dt = pd.to_datetime(d, format="%Y-%m-%d")
            except Exception:
                dt = pd.to_datetime(d, dayfirst=False, errors='coerce')
        if pd.notnull(dt):
            normalized.append(dt)

    if not normalized:
        return "Não consegui interpretar as datas do banco.", 400

    df = pd.DataFrame({"data": normalized})
    df_count = df.groupby("data").size().reset_index(name="quantidade")

    # converte para ordinal (número)
    df_count['dia_ord'] = df_count['data'].map(lambda x: x.toordinal())

    X = df_count[['dia_ord']].values
    y = df_count['quantidade'].values

    # cuidado: se y tem poucos pontos, a regressão pode falhar; tratar
    if len(X) < 2:
        return "Dados insuficientes para treinar modelo.", 400

    model = LinearRegression()
    model.fit(X, y)

    # prever próximos 7 dias
    last = int(df_count['dia_ord'].max())
    futuros = np.array([last + i for i in range(1, 8)]).reshape(-1, 1)
    preds = model.predict(futuros)

    # montagem do gráfico com o estilo do site
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df_count['data'], df_count['quantidade'], label='Histórico', marker='o', color='#2F8F6D')
    futuras_dt = [pd.to_datetime(pd.Timestamp.fromordinal(int(v))) for v in futuros.flatten()]
    ax.plot(futuras_dt, preds, label='Previsão', linestyle='--', marker='o', color='#7ADCB3')
    ax.set_title('Previsão de Agendamentos (próximos 7 dias)')
    ax.set_ylabel('Número de agendamentos')
    ax.legend()
    ax.grid(alpha=0.12)

    # salva em buffer
    buf = io.BytesIO()
    plt.tight_layout()
    fig.patch.set_facecolor('white')
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return send_file(buf, mimetype='image/png')
# Importa as bibliotecas necessárias
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv
import sqlite3
# imports necessários 
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from flask import send_file, jsonify
from datetime import datetime, date

import qrcode
import io
from email.mime.text import MIMEText




def criar_tabelas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT,
            nome_pet TEXT,
            tipo_servico TEXT,
            data TEXT,
            horario TEXT,
            observacoes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_atendimento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_agendamento INTEGER,
            titulo TEXT,
            descricao TEXT,
            FOREIGN KEY (id_agendamento) REFERENCES agendamento (id)
        )
    """)
    
        # Cria a tabela de sugestões, se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sugestoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_servico TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT
        )
    """)
    conn.commit()
    print("✅ Tabela 'sugestoes' criada (ou já existia).")


    conn.commit()
    conn.close()
    print("✅ Tabelas criadas (ou já existiam).")


load_dotenv()

app = Flask(__name__)
app.secret_key = "petcare_secret"  # Necessário para usar flash messages
criar_tabelas()

# debug: liste as rotas no startup
print("Rotas disponíveis:")
for r in app.url_map.iter_rules():
    print(r)



# Configurações do e-mail vindas do .env
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

mail = Mail(app)

import logging
logging.basicConfig(level=logging.DEBUG)


def enviar_email(assunto, corpo):
    """Envia e-mail para o PetCare confirmando novos agendamentos"""
    
    destinatario = os.getenv("MAIL_USERNAME")  # e-mail da empresa (PetCare)

    msg = Message(
        subject=assunto,
        sender=destinatario,  # remetente é o próprio e-mail do PetCare
        recipients=[destinatario]  # PetCare recebe
    )

    msg.body = corpo
    mail.send(msg)


# -------------------------
# ROTAS DE CADASTRO
# -------------------------

# 🔹 Novo Cliente
@app.route("/clientes/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cliente (nome_cliente, nome_pet, telefone, email, endereco)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, telefone, email, endereco))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
📩 Novo Cliente Cadastrado!

Nome: {nome_cliente}
Pet: {nome_pet}
Telefone: {telefone}
E-mail: {email}
Endereço: {endereco}
"""
        enviar_email("Novo Cliente Cadastrado", corpo)

        # 🔔 Adiciona notificação no sistema
        adicionar_notificacao(
            titulo="Novo Cliente Cadastrado",
            mensagem=f"O cliente {nome_cliente} foi registrado com o pet {nome_pet}."
        )

        flash("Cliente cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_clientes"))

    return render_template("novo_cliente.html")


# 🔹 Novo Pet
@app.route("/pets/novo", methods=["GET", "POST"])
def novo_pet():
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_cliente = request.form["nome_cliente"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form.get("peso")

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_cliente, raca, idade, peso))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
🐾 Novo Pet Cadastrado!

Nome do Pet: {nome_pet}
Tutor: {nome_cliente}
Raça: {raca}
Idade: {idade}
Peso: {peso}
"""
        enviar_email("Novo Pet Cadastrado", corpo)

        # 🔔 Adiciona notificação no sistema
        adicionar_notificacao(
            titulo="Novo Pet Cadastrado",
            mensagem=f"O pet {nome_pet} do tutor {nome_cliente} foi registrado no sistema."
        )

        flash("Pet cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_pets"))

    return render_template("novo_pet.html")


# --- Função de recomendação simples (colocar antes da rota novo_agendamento) ---
def recomendar_servicos(tipo_servico):
    """
    Retorna uma lista de sugestões (serviços ou produtos) baseadas no tipo_servico.
    Mantém tudo em memória para não mexer no banco. Fácil de estender depois.
    """
    if not tipo_servico:
        return []

    t = tipo_servico.lower()

    # recomendações fixas por serviço (exemplo)
    sugestoes_por_servico = {
        'banho': [
            {"titulo": "Shampoo especial (500ml)", "descricao": "Hipoalergênico — complementar ao banho"},
            {"titulo": "Escovação extra", "descricao": "Remove pelos soltos — +15 min"},
            {"titulo": "Check-up rápido (gratuito)", "descricao": "Verificar pele e pulgas"}
        ],
        'tosa': [
            {"titulo": "Hidratação pós-tosa", "descricao": "Melhora o aspecto do pelo"},
            {"titulo": "Tosa higiênica adicional", "descricao": "Ajustes finos após a tosa"},
            {"titulo": "Corta-unhas", "descricao": "Serviço rápido"}
        ],
        'consulta': [
            {"titulo": "Vacinação (se necessário)", "descricao": "Verificar calendário vacinal"},
            {"titulo": "Exame rápido (olho/orelhas)", "descricao": "Rápido check-up complementar"},
            {"titulo": "Medicamentos (caso prescrito)", "descricao": "Entregar direto ao tutor"}
        ],
        'vacinação': [
            {"titulo": "Cartão de vacinação atualizado", "descricao": "Emitir recibo/caderneta"},
            {"titulo": "Vermífugo (opcional)", "descricao": "Complemento recomendado"},
            {"titulo": "Agendamento de retorno", "descricao": "Lembrete de dose posterior"}
        ]
    }

    # sugestões gerais (fallback)
    sugestoes_gerais = [
        {"titulo": "Pacote mensal (banho + tosa)", "descricao": "Economize com pacotes"},
        {"titulo": "Escova de dentes pet", "descricao": "Higiene bucal preventiva"},
        {"titulo": "Toalha microfibra", "descricao": "Produto à venda na recepção"}
    ]

    # tenta encontrar por correspondência exata; senão retorna gerais
    if t in sugestoes_por_servico:
        return sugestoes_por_servico[t] + sugestoes_gerais[:1]
    # tentar match parcial (ex: 'vacina' dentro de 'vacinação')
    for chave in sugestoes_por_servico.keys():
        if chave in t:
            return sugestoes_por_servico[chave] + sugestoes_gerais[:1]

    return sugestoes_gerais 

# 🔹 Novo Agendamento
@app.route("/agendamentos/novo", methods=["GET", "POST"])
def novo_agendamento():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()

        # 1 — Salva o agendamento
        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes))

        conn.commit()

        # 2 — ETAPA 6: cria notificação interna
        cursor.execute("""
            INSERT INTO notificacoes (mensagem, lida, data)
            VALUES (?, 0, DATE('now'))
        """, (
            f"Novo agendamento: {nome_pet} ({tipo_servico}) — {data} às {horario}",
        ))

        conn.commit()
        conn.close()

        flash("Agendamento salvo com sucesso!", "success")
        return redirect(url_for("listar_agendamentos"))

    return render_template("novo_agendamento.html")



from flask import jsonify

@app.route("/agendamentos/<int:id_agendamento>/itens/adicionar", methods=["POST"])
def adicionar_item_atendimento(id_agendamento):
    data = request.get_json() or {}
    titulo = data.get("titulo")
    descricao = data.get("descricao", "")
    preco = float(data.get("preco", 0) or 0)

    if not titulo:
        return jsonify({"status": "error", "message": "Título obrigatório"}), 400

    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO itens_atendimento (id_agendamento, titulo, descricao, preco)
        VALUES (?, ?, ?, ?)
    """, (id_agendamento, titulo, descricao, preco))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Item adicionado ao atendimento", "titulo": titulo})

import sqlite3

def recomendar_servicos_por_historico(tipo_servico, limit=4):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.titulo, i.descricao, COUNT(*) as total
        FROM itens_atendimento i
        JOIN agendamento a ON i.id_agendamento = a.id
        WHERE LOWER(a.tipo_servico) = LOWER(?)
        GROUP BY i.titulo, i.descricao
        ORDER BY total DESC
        LIMIT ?
    """, (tipo_servico, limit))
    rows = cursor.fetchall()
    conn.close()

    sugestoes = []
    for r in rows:
        sugestoes.append({
            'titulo': r[0],
            'descricao': r[1] or "",
            'count': r[2]
        })
    return sugestoes

from sklearn.neighbors import NearestNeighbors
import numpy as np

def recomendar_por_similaridade():
    """
    Cria recomendações de serviços baseadas na similaridade entre agendamentos.
    Usa KNN com base no tipo de serviço (modelo simples de exemplo).
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, tipo_servico FROM agendamento")
    dados = cursor.fetchall()
    conn.close()

    if not dados:
        return []

    # Codificar tipos de serviço em números
    servicos_unicos = list(set([d[1] for d in dados]))
    mapa_servicos = {s: i for i, s in enumerate(servicos_unicos)}

    X = np.array([[mapa_servicos[d[1]]] for d in dados])

    # Treinar modelo
    knn = NearestNeighbors(n_neighbors=2, metric='euclidean')
    knn.fit(X)

    sugestoes = []
    for i, (cliente, servico) in enumerate(dados):
        distances, indices = knn.kneighbors([[mapa_servicos[servico]]])
        similares = [dados[j][1] for j in indices[0] if j != i]
        if similares:
            sugestoes.append((servico, similares[0]))

    # Remover duplicados
    sugestoes = list(set(sugestoes))
    return sugestoes



# 🔹 Exibir recomendações baseadas no tipo de serviço
@app.route("/agendamentos/<int:id_agendamento>/recomendacoes")
def recomendacoes(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamento WHERE id = ?", (id_agendamento,))
    agendamento = cursor.fetchone()
    conn.close()

    if not agendamento:
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    pet, servico = agendamento
    sugestoes = recomendar_servicos_por_historico(servico)

    # 👇 Aqui usamos o nome correto do seu template
    return render_template(
        "recomendacoes_funcionario.html",
        id_agendamento=id_agendamento,
        pet=pet,
        servico=servico,
        sugestoes=sugestoes
    )


# 🔹 Adicionar item ao atendimento
@app.route("/agendamentos/<int:id_agendamento>/adicionar_item", methods=["POST"])
def adicionar_item(id_agendamento):
    titulo = request.form.get("titulo")
    descricao = request.form.get("descricao")

    # Evita salvar valores nulos ou "None"
    if not titulo or titulo.lower() == "none":
        flash("Erro: título inválido para o item.")
        return redirect(url_for("ver_agendamento", id=id_agendamento))

    # Abre conexão
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Evita duplicar o mesmo item no mesmo agendamento
    cursor.execute("""
        SELECT COUNT(*) FROM itens_atendimento
        WHERE id_agendamento = ? AND titulo = ? AND descricao = ?
    """, (id_agendamento, titulo, descricao))
    ja_existe = cursor.fetchone()[0]

    if ja_existe == 0:
        cursor.execute("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, (id_agendamento, titulo, descricao))
        conn.commit()
        flash("Item adicionado ao atendimento com sucesso!")
    else:
        flash("Este item já foi adicionado a este atendimento.")

    conn.close()

    return redirect(url_for("ver_agendamento", id=id_agendamento))

from flask import render_template, request, redirect, url_for
import sqlite3
@app.route("/agendamentos/<int:id_agendamento>/sugestoes")
def sugestoes_agendamento(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Pega dados do agendamento
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamentos WHERE id = ?", (id_agendamento,))
    ag = cursor.fetchone()

    if not ag:
        conn.close()
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    nome_pet, tipo_servico = ag

    # Pega sugestões (fixas ou do banco)
    cursor.execute("""
        SELECT titulo, descricao 
        FROM sugestoes
        WHERE servico = ? OR servico = 'Geral'
    """, (tipo_servico,))

    rows = cursor.fetchall()
    sugestoes = [{"titulo": r[0], "descricao": r[1]} for r in rows]

    conn.close()

    return render_template(
        "sugestoes.html",
        nome_pet=nome_pet,
        tipo_servico=tipo_servico,
        sugestoes=sugestoes,
        id_agendamento=id_agendamento
    )


import unicodedata

# 🔹 Ver detalhes de um agendamento (corrigido com normalização de acentos)
@app.route("/agendamentos/<int:id>")
def ver_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome_cliente, nome_pet, tipo_servico, data, horario, observacoes
        FROM agendamentos
        WHERE id = ?
    """, (id,))
    agendamento = cursor.fetchone()

    # Itens do atendimento
    cursor.execute("""
        SELECT titulo, descricao
        FROM itens_atendimento
        WHERE id_agendamento = ?
    """, (id,))
    itens = cursor.fetchall()

    conn.close()

    return render_template(
        "ver_agendamento.html",
        agendamento=agendamento,
        itens=itens
    )

# -------------------------
# OUTRAS ROTAS
# -------------------------

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/agendamentos")
def listar_agendamentos():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agendamentos ORDER BY data, horario")
    agendamentos = cursor.fetchall()
    conn.close()
    return render_template("agendamentos.html", agendamentos=agendamentos)

@app.route("/clientes")
def listar_clientes():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()
    return render_template("clientes.html", clientes=clientes)

@app.route("/pets")
def listar_pets():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pet ORDER BY nome_pet")
    pets = cursor.fetchall()
    conn.close()
    return render_template("pets.html", pets=pets)

@app.route("/petbot")
def petbot():
    return render_template("chatbot.html")


# -------------------------
# CRUD de edição e exclusão
# -------------------------

@app.route("/agendamentos/editar/<int:id>", methods=["GET", "POST"])
def editar_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        cursor.execute("""
            UPDATE agendamento
            SET nome_cliente=?, nome_pet=?, tipo_servico=?, data=?, horario=?, observacoes=?
            WHERE id=?
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_agendamentos"))

    cursor.execute("SELECT * FROM agendamento WHERE id=?", (id,))
    agendamento = cursor.fetchone()
    conn.close()
    return render_template("editar_agendamento.html", agendamento=agendamento)

@app.route("/agendamentos/excluir/<int:id>")
def excluir_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agendamento WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_agendamentos"))

@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        cursor.execute("""
            UPDATE cliente
            SET nome_cliente=?, nome_pet=?, telefone=?, email=?, endereco=?
            WHERE id=?
        """, (nome_cliente, nome_pet, telefone, email, endereco, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_clientes"))

    cursor.execute("SELECT * FROM cliente WHERE id=?", (id,))
    cliente = cursor.fetchone()
    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

@app.route("/clientes/excluir/<int:id>")
def excluir_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cliente WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_clientes"))

@app.route("/pets/editar/<int:id>", methods=["GET", "POST"])
def editar_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_tutor = request.form["nome_tutor"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form["peso"]

        cursor.execute("""
            UPDATE pet
            SET nome_pet=?, nome_tutor=?, raca=?, idade=?, peso=?
            WHERE id=?
        """, (nome_pet, nome_tutor, raca, idade, peso, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_pets"))

    cursor.execute("SELECT * FROM pet WHERE id=?", (id,))
    pet = cursor.fetchone()
    conn.close()
    return render_template("editar_pet.html", pet=pet)

@app.route("/pets/excluir/<int:id>")
def excluir_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pet WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_pets"))

# -------------------------
# FINANÇAS
# -------------------------
@app.route('/financas')
def financas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cliente")
    total_clientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pet")
    total_pets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM agendamento")
    total_agendamentos = cursor.fetchone()[0]

    cursor.execute("SELECT tipo_servico, COUNT(*) FROM agendamento GROUP BY tipo_servico")
    dados = cursor.fetchall()
    tipos = [linha[0] for linha in dados]
    contagens = [linha[1] for linha in dados]

    precos = {
        'Banho': 40,
        'Tosa': 80,
        'Consulta': 100,
        'Vacinação': 70
    }

    cursor.execute("SELECT tipo_servico FROM agendamento")
    todos = cursor.fetchall()
    lucro_total = sum(precos.get(t[0], 0) for t in todos)

    from datetime import date
    hoje = date.today().isoformat()
    cursor.execute("SELECT tipo_servico FROM agendamento WHERE data > ?", (hoje,))
    futuros = cursor.fetchall()
    lucro_futuro = sum(precos.get(t[0], 0) for t in futuros)

    conn.close()

    return render_template("financas.html",
                           total_clientes=total_clientes,
                           total_pets=total_pets,
                           total_agendamentos=total_agendamentos,
                           tipos=tipos,
                           contagens=contagens,
                           lucro_total=lucro_total,
                           lucro_futuro=lucro_futuro)
    


# -------------------------
# BANCO DE DADOS
# -------------------------
def init_db():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            tipo_servico TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            observacoes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            endereco TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pet TEXT NOT NULL,
            nome_tutor TEXT NOT NULL,
            raca TEXT,
            idade INTEGER,
            peso REAL
        )
    ''')

    conn.commit()
    conn.close()
    
def seed_itens_iniciais():
    """Popula a tabela itens_atendimento com sugestões iniciais (somente se estiver vazia)."""
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM itens_atendimento")
    total = cursor.fetchone()[0]

    if total == 0:
        print("🌱 Inserindo sugestões iniciais na tabela itens_atendimento...")

        itens_iniciais = [
            # Banho
            (1, "Shampoo especial", "Hipoalergênico — complementar ao banho"),
            (1, "Escovação extra", "Remove pelos soltos — +15 min"),
            (1, "Check-up rápido", "Verificar pele e pulgas"),

            # Tosa
            (1, "Hidratação pós-tosa", "Melhora o aspecto do pelo"),
            (1, "Tosa higiênica adicional", "Ajustes finos após a tosa"),
            (1, "Corta-unhas", "Serviço rápido"),

            # Consulta
            (1, "Vacinação (se necessário)", "Verificar calendário vacinal"),
            (1, "Exame rápido (olho/orelhas)", "Rápido check-up complementar"),
            (1, "Medicamentos (caso prescrito)", "Entregar direto ao tutor"),

            # Vacinação
            (1, "Cartão de vacinação atualizado", "Emitir recibo/caderneta"),
            (1, "Vermífugo (opcional)", "Complemento recomendado"),
            (1, "Agendamento de retorno", "Lembrete de dose posterior"),
        ]

        cursor.executemany("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, itens_iniciais)

        conn.commit()
        print("✅ Sugestões iniciais inseridas com sucesso.")
    else:
        print(f"ℹ️ Tabela já possui {total} itens. Nenhuma inserção feita.")

    conn.close()


# -------------------------
# START
# -------------------------

import sqlite3

def listar_agendamentos_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome_pet, tipo_servico, data, horario
        FROM agendamento
        ORDER BY 
            substr(data, 7, 4),
            substr(data, 4, 2),
            substr(data, 1, 2),
            horario
    """)
    agds = cursor.fetchall()
    conn.close()

    if not agds:
        return "Nenhum agendamento encontrado. 📭"

    linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
    return "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)


def listar_clientes_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()

    if not clientes:
        return "Nenhum cliente cadastrado ainda. 📭"

    linhas = [f"👤 {c[0]} (Pet: {c[1]})" for c in clientes]
    return "Aqui estão os clientes cadastrados:\n" + "\n".join(linhas)


from flask import jsonify, request
import re

# memória de contexto simples
user_context = {}

from unidecode import unidecode

from unidecode import unidecode
from flask import request, jsonify

from unidecode import unidecode
from flask import request, jsonify

from flask import jsonify, request
import sqlite3
import re
from unidecode import unidecode

@app.route("/api/chat_simple", methods=["POST"])
def api_chat_simple():
    data = request.get_json()
    user_message = data.get("message", "").strip().lower()
    user_message = unidecode(user_message)  # remove acentos

    # ========= RESPOSTAS BÁSICAS =========
    if any(p in user_message for p in ["oi", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"response": "Olá! 😊 Como posso te ajudar hoje?"})

    if any(p in user_message for p in ["obrigado", "obrigada", "valeu", "agradecido", "vlw"]):
        return jsonify({"response": "De nada! 😄 Sempre à disposição."})

    # ========= LISTAR PETS =========
        # ========= LISTAR PETS =========
    # ========= LISTAR PETS =========
    if "listar pets" in user_message or "meus pets" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, nome_tutor, raca FROM pet")
        pets = cursor.fetchall()
        conn.close()

        if pets:
            lista = "\n".join([
                f"🐾 Pet: {p[0]}\n   👤 Tutor: {p[1]}\n   🐶 Raça: {p[2]}"
                for p in pets
            ])
            return jsonify({"response": f"Aqui estão os pets cadastrados:\n\n{lista}"})
        else:
            return jsonify({"response": "Nenhum pet cadastrado ainda. 🐾"})



    # ========= LISTAR CLIENTES =========
    if "listar clientes" in user_message or "clientes" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_cliente, nome_pet FROM cliente")
        clientes = cursor.fetchall()
        conn.close()

        if clientes:
            lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
            return jsonify({"response": f"Aqui estão os clientes cadastrados:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum cliente cadastrado ainda."})


    # ========= LISTAR AGENDAMENTOS =========
    if "listar agendamentos" in user_message or "agendamentos" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, tipo_servico, data, horario FROM agendamentos ORDER BY data, horario")
        ags = cursor.fetchall()
        conn.close()

        if ags:
            lista = "\n".join([f"📅 {a[0]} - {a[1]} em {a[2]} às {a[3]}" for a in ags])
            return jsonify({"response": f"Aqui estão os agendamentos:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum agendamento encontrado."})

    # ========= CASO PADRÃO =========
    return jsonify({"response": "Desculpe, não entendi 😅. Você pode pedir para listar pets, clientes ou agendamentos."})


from flask import jsonify
import re
import sqlite3
from datetime import datetime, timedelta

@app.route("/api/chat_acoes", methods=["POST"])
def api_chat_acoes():
    data = request.get_json()
    msg = data.get("message", "").lower().strip()

    # === INTERPRETA SAUDAÇÕES ===
    if any(p in msg for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"reply": "Olá! Eu sou o PetBot 🐾 Como posso te ajudar hoje?"})

    # === INTERPRETA PEDIDO DE AGENDAMENTO ===
    if any(k in msg for k in ["agendar", "agd", "marcar"]) and "listar" not in msg:
        servicos = ["banho", "tosa", "consulta", "vacinação", "vacina"]
        tipo_servico = next((s for s in servicos if s in msg), None)

        if "amanh" in msg:
            data_agendamento = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        elif "hoje" in msg:
            data_agendamento = datetime.now().strftime("%d/%m/%Y")
        else:
            m_data = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", msg)
            data_agendamento = m_data.group(1) if m_data else None

        m_hora = re.search(r"(\d{1,2}[:h]\d{0,2})", msg)
        horario = m_hora.group(1).replace("h", ":00") if m_hora else None

        m_pet = re.search(r"para\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        nome_pet = m_pet.group(1).capitalize() if m_pet else "Pet não informado"

        if not all([tipo_servico, data_agendamento, horario]):
            return jsonify({"reply": "Preciso de mais informações: serviço, data e horário. Pode me dizer tudo de uma vez? 😊"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Empresa", nome_pet, tipo_servico.capitalize(), data_agendamento, horario, "Agendado via PetBot"))

        conn.commit()
        conn.close()

        return jsonify({
            "reply": f"Agendamento de {tipo_servico} para {nome_pet} em {data_agendamento} às {horario} registrado com sucesso! ✅"
        })

    # === INTERPRETA CADASTRO DE PET ===
    if "cadastrar pet" in msg or "novo pet" in msg:
        nome = re.search(r"pet\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        tutor = re.search(r"tutor\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        raca = re.search(r"ra[çc]a\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        idade = re.search(r"idade\s+(\d+)", msg)
        peso = re.search(r"peso\s+(\d+[.,]?\d*)", msg)

        nome_pet = nome.group(1).capitalize() if nome else None
        nome_tutor = tutor.group(1).capitalize() if tutor else None
        raca_pet = raca.group(1).capitalize() if raca else None
        idade_pet = int(idade.group(1)) if idade else None
        peso_pet = float(peso.group(1).replace(",", ".")) if peso else None

        if not all([nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet]):
            return jsonify({"reply": "Faltam alguns dados! Diga tudo na mesma frase: ex: 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg' 🐶"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet))
        conn.commit()
        conn.close()

        return jsonify({"reply": f"Pet {nome_pet} cadastrado com sucesso! 🐾"})

    # === LISTAR PETS ===
    if "listar" in msg and "pet" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_pet, nome_tutor FROM pet ORDER BY nome_pet")
            pets = cursor.fetchall()
            conn.close()

            if pets:
                lista = "\n".join([f"🐶 {p[0]} (Tutor: {p[1]})" for p in pets])
                reply = f"Aqui estão os pets cadastrados:\n{lista}"
            else:
                reply = "Não há pets cadastrados ainda. 🐾"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR CLIENTES ===
    if "listar" in msg and "cliente" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
            clientes = cursor.fetchall()
            conn.close()

            if clientes:
                lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
                reply = f"Aqui estão os clientes cadastrados:\n{lista}"
            else:
                reply = "Nenhum cliente cadastrado ainda. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR AGENDAMENTOS ===
    if "listar" in msg and "agendamento" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT nome_pet, tipo_servico, data, horario
                FROM agendamento
                WHERE nome_pet IS NOT NULL
                ORDER BY 
                    substr(data, 7, 4),  -- ano
                    substr(data, 4, 2),  -- mês
                    substr(data, 1, 2),  -- dia
                    horario
            """)
            agds = cursor.fetchall()
            conn.close()

            if agds:
                linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
                reply = "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)
            else:
                reply = "Nenhum agendamento encontrado. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === OUTRAS INTERAÇÕES ===
    if any(p in msg for p in ["obrigado", "valeu"]):
        return jsonify({"reply": "De nada! 😺 Sempre que precisar, estarei por aqui!"})

    if any(p in msg for p in ["tchau", "até", "flw", "falou"]):
        return jsonify({"reply": "Tchau tchau! 👋 Espero te ver em breve!"})
    

    # === CASO NÃO ENTENDA ===
    return jsonify({
        "reply": "Desculpe, não entendi bem. Você pode tentar algo como: 'Agendar banho amanhã às 15h para Luna' ou 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg'."
    })
    
    def recomendar_servicos(servico_base):
        """Sugere serviços ou produtos relacionados ao agendamento atual"""
    recomendacoes = {
        "banho": ["tosa", "hidratação", "perfume pet"],
        "tosa": ["banho", "corte de unhas"],
        "consulta": ["vacinação", "vermifugação"],
        "vacinação": ["vermifugação", "check-up"],
    }

    return recomendacoes.get(servico_base.lower(), ["Sem recomendações no momento"])

# 🔹 Página de FAQs
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")

def servicos_mais_populares(limit=4):
    """
    Retorna os serviços mais agendados, para exibir na home.
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo_servico, COUNT(*) AS total
        FROM agendamento
        GROUP BY tipo_servico
        ORDER BY total DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/previsoes")
def previsoes():
    # renderiza o template com o mockup; você pode passar dados reais aqui ou carregá-los via AJAX
    return render_template("previsoes.html")

@app.route("/previsao_image")
def previsao_image():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    # pega datas (no formato que você tem no banco: pode ser 'dd/mm/YYYY' ou 'YYYY-mm-dd')
    cursor.execute("SELECT data FROM agendamento WHERE data IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    datas = [r[0] for r in rows]

    if not datas:
        # retorna imagem simples com texto ou um JSON
        return "Ainda não há dados suficientes para previsão.", 400

    # normaliza formatos: detecta se tem '/' -> dd/mm/YYYY else assume ISO yyyy-mm-dd
    normalized = []
    for d in datas:
        if "/" in d:
            # dd/mm/YYYY
            try:
                dt = pd.to_datetime(d, format="%d/%m/%Y", dayfirst=True)
            except Exception:
                dt = pd.to_datetime(d, dayfirst=True, errors='coerce')
        else:
            try:
                dt = pd.to_datetime(d, format="%Y-%m-%d")
            except Exception:
                dt = pd.to_datetime(d, dayfirst=False, errors='coerce')
        if pd.notnull(dt):
            normalized.append(dt)

    if not normalized:
        return "Não consegui interpretar as datas do banco.", 400

    df = pd.DataFrame({"data": normalized})
    df_count = df.groupby("data").size().reset_index(name="quantidade")

    # converte para ordinal (número)
    df_count['dia_ord'] = df_count['data'].map(lambda x: x.toordinal())

    X = df_count[['dia_ord']].values
    y = df_count['quantidade'].values

    # cuidado: se y tem poucos pontos, a regressão pode falhar; tratar
    if len(X) < 2:
        return "Dados insuficientes para treinar modelo.", 400

    model = LinearRegression()
    model.fit(X, y)

    # prever próximos 7 dias
    last = int(df_count['dia_ord'].max())
    futuros = np.array([last + i for i in range(1, 8)]).reshape(-1, 1)
    preds = model.predict(futuros)

    # montagem do gráfico com o estilo do site
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df_count['data'], df_count['quantidade'], label='Histórico', marker='o', color='#2F8F6D')
    futuras_dt = [pd.to_datetime(pd.Timestamp.fromordinal(int(v))) for v in futuros.flatten()]
    ax.plot(futuras_dt, preds, label='Previsão', linestyle='--', marker='o', color='#7ADCB3')
    ax.set_title('Previsão de Agendamentos (próximos 7 dias)')
    ax.set_ylabel('Número de agendamentos')
    ax.legend()
    ax.grid(alpha=0.12)

    # salva em buffer
    buf = io.BytesIO()
    plt.tight_layout()
    fig.patch.set_facecolor('white')
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return send_file(buf, mimetype='image/png')

def enviar_lembrete_email(email_destino, nome_pet, nome_cliente, data, horario, id_agendamento):

    # URL do agendamento
    link = f"http://localhost:5000/agendamentos/{id_agendamento}"

    # Gera QR Code
    img = qrcode.make(link)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    qr_bytes = buffer.read()

    # Corpo do e-mail em HTML
    corpo = f"""
    <h2>🐾 Lembrete de Agendamento - PetCare</h2>
    <p>Olá <strong>{nome_cliente}</strong>! Aqui está o lembrete do agendamento do pet <strong>{nome_pet}</strong>.</p>

    <p><strong>📆 Data:</strong> {data}<br>
    <strong>⏰ Horário:</strong> {horario}</p>

    <p>Use o QR Code abaixo para ver os detalhes:</p>

    <img src="cid:qrcode" alt="QR Code">

    <p>Até breve!<br>Equipe PetCare 💚</p>
    """

    msg = Message("📌 Lembrete de Agendamento - PetCare", recipients=[email_destino])
    msg.html = corpo

    # Anexa o QR Code
    msg.attach("qrcode.png", "image/png", qr_bytes, disposition="inline", headers=[("Content-ID", "<qrcode>")])

    mail.send(msg)
    
import datetime as dt
# Importa as bibliotecas necessárias
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv
import sqlite3
# imports necessários 
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from flask import send_file, jsonify
from datetime import datetime, date

import qrcode
import io
from email.mime.text import MIMEText




def criar_tabelas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT,
            nome_pet TEXT,
            tipo_servico TEXT,
            data TEXT,
            horario TEXT,
            observacoes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_atendimento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_agendamento INTEGER,
            titulo TEXT,
            descricao TEXT,
            FOREIGN KEY (id_agendamento) REFERENCES agendamento (id)
        )
    """)
    
        # Cria a tabela de sugestões, se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sugestoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_servico TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT
        )
    """)
    conn.commit()
    print("✅ Tabela 'sugestoes' criada (ou já existia).")


    conn.commit()
    conn.close()
    print("✅ Tabelas criadas (ou já existiam).")


load_dotenv()

app = Flask(__name__)
app.secret_key = "petcare_secret"  # Necessário para usar flash messages
criar_tabelas()

# debug: liste as rotas no startup
print("Rotas disponíveis:")
for r in app.url_map.iter_rules():
    print(r)



# Configurações do e-mail vindas do .env
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

mail = Mail(app)

import logging
logging.basicConfig(level=logging.DEBUG)


def enviar_email(assunto, corpo):
    """Envia e-mail para o PetCare confirmando novos agendamentos"""
    
    destinatario = os.getenv("MAIL_USERNAME")  # e-mail da empresa (PetCare)

    msg = Message(
        subject=assunto,
        sender=destinatario,  # remetente é o próprio e-mail do PetCare
        recipients=[destinatario]  # PetCare recebe
    )

    msg.body = corpo
    mail.send(msg)


# -------------------------
# ROTAS DE CADASTRO
# -------------------------

# 🔹 Novo Cliente
@app.route("/clientes/novo", methods=["GET", "POST"])
def novo_cliente():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cliente (nome_cliente, nome_pet, telefone, email, endereco)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, telefone, email, endereco))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
📩 Novo Cliente Cadastrado!

Nome: {nome_cliente}
Pet: {nome_pet}
Telefone: {telefone}
E-mail: {email}
Endereço: {endereco}
"""
        enviar_email("Novo Cliente Cadastrado", corpo)

        flash("Cliente cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_clientes"))
    
    return render_template("novo_cliente.html")

# 🔹 Novo Pet
@app.route("/pets/novo", methods=["GET", "POST"])
def novo_pet():
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_cliente = request.form["nome_cliente"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form.get("peso")

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_cliente, raca, idade, peso))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
🐾 Novo Pet Cadastrado!

Nome do Pet: {nome_pet}
Tutor: {nome_cliente}
Raça: {raca}
Idade: {idade}
Peso: {peso} 
"""
        enviar_email("Novo Pet Cadastrado", corpo)

        flash("Pet cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_pets"))

    return render_template("novo_pet.html")

# --- Função de recomendação simples (colocar antes da rota novo_agendamento) ---
def recomendar_servicos(tipo_servico):
    """
    Retorna uma lista de sugestões (serviços ou produtos) baseadas no tipo_servico.
    Mantém tudo em memória para não mexer no banco. Fácil de estender depois.
    """
    if not tipo_servico:
        return []

    t = tipo_servico.lower()

    # recomendações fixas por serviço (exemplo)
    sugestoes_por_servico = {
        'banho': [
            {"titulo": "Shampoo especial (500ml)", "descricao": "Hipoalergênico — complementar ao banho"},
            {"titulo": "Escovação extra", "descricao": "Remove pelos soltos — +15 min"},
            {"titulo": "Check-up rápido (gratuito)", "descricao": "Verificar pele e pulgas"}
        ],
        'tosa': [
            {"titulo": "Hidratação pós-tosa", "descricao": "Melhora o aspecto do pelo"},
            {"titulo": "Tosa higiênica adicional", "descricao": "Ajustes finos após a tosa"},
            {"titulo": "Corta-unhas", "descricao": "Serviço rápido"}
        ],
        'consulta': [
            {"titulo": "Vacinação (se necessário)", "descricao": "Verificar calendário vacinal"},
            {"titulo": "Exame rápido (olho/orelhas)", "descricao": "Rápido check-up complementar"},
            {"titulo": "Medicamentos (caso prescrito)", "descricao": "Entregar direto ao tutor"}
        ],
        'vacinação': [
            {"titulo": "Cartão de vacinação atualizado", "descricao": "Emitir recibo/caderneta"},
            {"titulo": "Vermífugo (opcional)", "descricao": "Complemento recomendado"},
            {"titulo": "Agendamento de retorno", "descricao": "Lembrete de dose posterior"}
        ]
    }

    # sugestões gerais (fallback)
    sugestoes_gerais = [
        {"titulo": "Pacote mensal (banho + tosa)", "descricao": "Economize com pacotes"},
        {"titulo": "Escova de dentes pet", "descricao": "Higiene bucal preventiva"},
        {"titulo": "Toalha microfibra", "descricao": "Produto à venda na recepção"}
    ]

    # tenta encontrar por correspondência exata; senão retorna gerais
    if t in sugestoes_por_servico:
        return sugestoes_por_servico[t] + sugestoes_gerais[:1]
    # tentar match parcial (ex: 'vacina' dentro de 'vacinação')
    for chave in sugestoes_por_servico.keys():
        if chave in t:
            return sugestoes_por_servico[chave] + sugestoes_gerais[:1]

    return sugestoes_gerais 

# 🔹 Novo Agendamento
@app.route("/agendamentos/novo", methods=["GET", "POST"])
def novo_agendamento():
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes))

        conn.commit()
        conn.close()
        
        adicionar_notificacao(
          titulo="Novo Agendamento",
          mensagem=f"Agendamento criado para {nome_pet} ({tipo_servico}) em {data} às {horario}."
)


        flash("Agendamento salvo com sucesso!", "success")
        return redirect(url_for("listar_agendamentos"))

    return render_template("novo_agendamento.html")



from flask import jsonify

@app.route("/agendamentos/<int:id_agendamento>/itens/adicionar", methods=["POST"])
def adicionar_item_atendimento(id_agendamento):
    data = request.get_json() or {}
    titulo = data.get("titulo")
    descricao = data.get("descricao", "")
    preco = float(data.get("preco", 0) or 0)

    if not titulo:
        return jsonify({"status": "error", "message": "Título obrigatório"}), 400

    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO itens_atendimento (id_agendamento, titulo, descricao, preco)
        VALUES (?, ?, ?, ?)
    """, (id_agendamento, titulo, descricao, preco))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok", "message": "Item adicionado ao atendimento", "titulo": titulo})

import sqlite3

def recomendar_servicos_por_historico(tipo_servico, limit=4):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.titulo, i.descricao, COUNT(*) as total
        FROM itens_atendimento i
        JOIN agendamento a ON i.id_agendamento = a.id
        WHERE LOWER(a.tipo_servico) = LOWER(?)
        GROUP BY i.titulo, i.descricao
        ORDER BY total DESC
        LIMIT ?
    """, (tipo_servico, limit))
    rows = cursor.fetchall()
    conn.close()

    sugestoes = []
    for r in rows:
        sugestoes.append({
            'titulo': r[0],
            'descricao': r[1] or "",
            'count': r[2]
        })
    return sugestoes

from sklearn.neighbors import NearestNeighbors
import numpy as np

def recomendar_por_similaridade():
    """
    Cria recomendações de serviços baseadas na similaridade entre agendamentos.
    Usa KNN com base no tipo de serviço (modelo simples de exemplo).
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, tipo_servico FROM agendamento")
    dados = cursor.fetchall()
    conn.close()

    if not dados:
        return []

    # Codificar tipos de serviço em números
    servicos_unicos = list(set([d[1] for d in dados]))
    mapa_servicos = {s: i for i, s in enumerate(servicos_unicos)}

    X = np.array([[mapa_servicos[d[1]]] for d in dados])

    # Treinar modelo
    knn = NearestNeighbors(n_neighbors=2, metric='euclidean')
    knn.fit(X)

    sugestoes = []
    for i, (cliente, servico) in enumerate(dados):
        distances, indices = knn.kneighbors([[mapa_servicos[servico]]])
        similares = [dados[j][1] for j in indices[0] if j != i]
        if similares:
            sugestoes.append((servico, similares[0]))

    # Remover duplicados
    sugestoes = list(set(sugestoes))
    return sugestoes



# 🔹 Exibir recomendações baseadas no tipo de serviço
@app.route("/agendamentos/<int:id_agendamento>/recomendacoes")
def recomendacoes(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamento WHERE id = ?", (id_agendamento,))
    agendamento = cursor.fetchone()
    conn.close()

    if not agendamento:
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    pet, servico = agendamento
    sugestoes = recomendar_servicos_por_historico(servico)

    # 👇 Aqui usamos o nome correto do seu template
    return render_template(
        "recomendacoes_funcionario.html",
        id_agendamento=id_agendamento,
        pet=pet,
        servico=servico,
        sugestoes=sugestoes
    )


# 🔹 Adicionar item ao atendimento
@app.route("/agendamentos/<int:id_agendamento>/adicionar_item", methods=["POST"])
def adicionar_item(id_agendamento):
    titulo = request.form.get("titulo")
    descricao = request.form.get("descricao")

    # Evita salvar valores nulos ou "None"
    if not titulo or titulo.lower() == "none":
        flash("Erro: título inválido para o item.")
        return redirect(url_for("ver_agendamento", id=id_agendamento))

    # Abre conexão
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Evita duplicar o mesmo item no mesmo agendamento
    cursor.execute("""
        SELECT COUNT(*) FROM itens_atendimento
        WHERE id_agendamento = ? AND titulo = ? AND descricao = ?
    """, (id_agendamento, titulo, descricao))
    ja_existe = cursor.fetchone()[0]

    if ja_existe == 0:
        cursor.execute("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, (id_agendamento, titulo, descricao))
        conn.commit()
        flash("Item adicionado ao atendimento com sucesso!")
    else:
        flash("Este item já foi adicionado a este atendimento.")

    conn.close()

    return redirect(url_for("ver_agendamento", id=id_agendamento))

from flask import render_template, request, redirect, url_for
import sqlite3
@app.route("/agendamentos/<int:id_agendamento>/sugestoes")
def sugestoes_agendamento(id_agendamento):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Pega dados do agendamento
    cursor.execute("SELECT nome_pet, tipo_servico FROM agendamentos WHERE id = ?", (id_agendamento,))
    ag = cursor.fetchone()

    if not ag:
        conn.close()
        flash("Agendamento não encontrado.")
        return redirect(url_for("listar_agendamentos"))

    nome_pet, tipo_servico = ag

    # Pega sugestões (fixas ou do banco)
    cursor.execute("""
        SELECT titulo, descricao 
        FROM sugestoes
        WHERE servico = ? OR servico = 'Geral'
    """, (tipo_servico,))

    rows = cursor.fetchall()
    sugestoes = [{"titulo": r[0], "descricao": r[1]} for r in rows]

    conn.close()

    return render_template(
        "sugestoes.html",
        nome_pet=nome_pet,
        tipo_servico=tipo_servico,
        sugestoes=sugestoes,
        id_agendamento=id_agendamento
    )


import unicodedata

# 🔹 Ver detalhes de um agendamento (corrigido com normalização de acentos)
@app.route("/agendamentos/<int:id>")
def ver_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome_cliente, nome_pet, tipo_servico, data, horario, observacoes
        FROM agendamentos
        WHERE id = ?
    """, (id,))
    agendamento = cursor.fetchone()

    # Itens do atendimento
    cursor.execute("""
        SELECT titulo, descricao
        FROM itens_atendimento
        WHERE id_agendamento = ?
    """, (id,))
    itens = cursor.fetchall()

    conn.close()

    return render_template(
        "ver_agendamento.html",
        agendamento=agendamento,
        itens=itens
    )

# -------------------------
# OUTRAS ROTAS
# -------------------------

@app.route("/")
def home():
    return render_template("index.html")



@app.route("/agendamentos")
def listar_agendamentos():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agendamentos ORDER BY data, horario")
    agendamentos = cursor.fetchall()
    conn.close()
    return render_template("agendamentos.html", agendamentos=agendamentos)

@app.route("/clientes")
def listar_clientes():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()
    return render_template("clientes.html", clientes=clientes)

@app.route("/pets")
def listar_pets():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pet ORDER BY nome_pet")
    pets = cursor.fetchall()
    conn.close()
    return render_template("pets.html", pets=pets)

@app.route("/petbot")
def petbot():
    return render_template("chatbot.html")


# -------------------------
# CRUD de edição e exclusão
# -------------------------

@app.route("/agendamentos/editar/<int:id>", methods=["GET", "POST"])
def editar_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        tipo_servico = request.form["tipo_servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        observacoes = request.form["observacoes"]

        cursor.execute("""
            UPDATE agendamento
            SET nome_cliente=?, nome_pet=?, tipo_servico=?, data=?, horario=?, observacoes=?
            WHERE id=?
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_agendamentos"))

    cursor.execute("SELECT * FROM agendamento WHERE id=?", (id,))
    agendamento = cursor.fetchone()
    conn.close()
    return render_template("editar_agendamento.html", agendamento=agendamento)

@app.route("/agendamentos/excluir/<int:id>")
def excluir_agendamento(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agendamento WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_agendamentos"))

@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_cliente = request.form["nome_cliente"]
        nome_pet = request.form["nome_pet"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        endereco = request.form["endereco"]

        cursor.execute("""
            UPDATE cliente
            SET nome_cliente=?, nome_pet=?, telefone=?, email=?, endereco=?
            WHERE id=?
        """, (nome_cliente, nome_pet, telefone, email, endereco, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_clientes"))

    cursor.execute("SELECT * FROM cliente WHERE id=?", (id,))
    cliente = cursor.fetchone()
    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

@app.route("/clientes/excluir/<int:id>")
def excluir_cliente(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cliente WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_clientes"))

@app.route("/pets/editar/<int:id>", methods=["GET", "POST"])
def editar_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    if request.method == "POST":
        nome_pet = request.form["nome_pet"]
        nome_tutor = request.form["nome_tutor"]
        raca = request.form["raca"]
        idade = request.form["idade"]
        peso = request.form["peso"]

        cursor.execute("""
            UPDATE pet
            SET nome_pet=?, nome_tutor=?, raca=?, idade=?, peso=?
            WHERE id=?
        """, (nome_pet, nome_tutor, raca, idade, peso, id))
        conn.commit()
        conn.close()
        return redirect(url_for("listar_pets"))

    cursor.execute("SELECT * FROM pet WHERE id=?", (id,))
    pet = cursor.fetchone()
    conn.close()
    return render_template("editar_pet.html", pet=pet)

@app.route("/pets/excluir/<int:id>")
def excluir_pet(id):
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pet WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("listar_pets"))

# -------------------------
# FINANÇAS
# -------------------------
@app.route('/financas')
def financas():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cliente")
    total_clientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pet")
    total_pets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM agendamento")
    total_agendamentos = cursor.fetchone()[0]

    cursor.execute("SELECT tipo_servico, COUNT(*) FROM agendamento GROUP BY tipo_servico")
    dados = cursor.fetchall()
    tipos = [linha[0] for linha in dados]
    contagens = [linha[1] for linha in dados]

    precos = {
        'Banho': 40,
        'Tosa': 80,
        'Consulta': 100,
        'Vacinação': 70
    }

    cursor.execute("SELECT tipo_servico FROM agendamento")
    todos = cursor.fetchall()
    lucro_total = sum(precos.get(t[0], 0) for t in todos)

    from datetime import date
    hoje = date.today().isoformat()
    cursor.execute("SELECT tipo_servico FROM agendamento WHERE data > ?", (hoje,))
    futuros = cursor.fetchall()
    lucro_futuro = sum(precos.get(t[0], 0) for t in futuros)

    conn.close()

    return render_template("financas.html",
                           total_clientes=total_clientes,
                           total_pets=total_pets,
                           total_agendamentos=total_agendamentos,
                           tipos=tipos,
                           contagens=contagens,
                           lucro_total=lucro_total,
                           lucro_futuro=lucro_futuro)
    


# -------------------------
# BANCO DE DADOS
# -------------------------
def init_db():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            tipo_servico TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            observacoes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            nome_pet TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            endereco TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pet TEXT NOT NULL,
            nome_tutor TEXT NOT NULL,
            raca TEXT,
            idade INTEGER,
            peso REAL
        )
    ''')

    conn.commit()
    conn.close()
    
def seed_itens_iniciais():
    """Popula a tabela itens_atendimento com sugestões iniciais (somente se estiver vazia)."""
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM itens_atendimento")
    total = cursor.fetchone()[0]

    if total == 0:
        print("🌱 Inserindo sugestões iniciais na tabela itens_atendimento...")

        itens_iniciais = [
            # Banho
            (1, "Shampoo especial", "Hipoalergênico — complementar ao banho"),
            (1, "Escovação extra", "Remove pelos soltos — +15 min"),
            (1, "Check-up rápido", "Verificar pele e pulgas"),

            # Tosa
            (1, "Hidratação pós-tosa", "Melhora o aspecto do pelo"),
            (1, "Tosa higiênica adicional", "Ajustes finos após a tosa"),
            (1, "Corta-unhas", "Serviço rápido"),

            # Consulta
            (1, "Vacinação (se necessário)", "Verificar calendário vacinal"),
            (1, "Exame rápido (olho/orelhas)", "Rápido check-up complementar"),
            (1, "Medicamentos (caso prescrito)", "Entregar direto ao tutor"),

            # Vacinação
            (1, "Cartão de vacinação atualizado", "Emitir recibo/caderneta"),
            (1, "Vermífugo (opcional)", "Complemento recomendado"),
            (1, "Agendamento de retorno", "Lembrete de dose posterior"),
        ]

        cursor.executemany("""
            INSERT INTO itens_atendimento (id_agendamento, titulo, descricao)
            VALUES (?, ?, ?)
        """, itens_iniciais)

        conn.commit()
        print("✅ Sugestões iniciais inseridas com sucesso.")
    else:
        print(f"ℹ️ Tabela já possui {total} itens. Nenhuma inserção feita.")

    conn.close()


# -------------------------
# START
# -------------------------

import sqlite3

def listar_agendamentos_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome_pet, tipo_servico, data, horario
        FROM agendamento
        ORDER BY 
            substr(data, 7, 4),
            substr(data, 4, 2),
            substr(data, 1, 2),
            horario
    """)
    agds = cursor.fetchall()
    conn.close()

    if not agds:
        return "Nenhum agendamento encontrado. 📭"

    linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
    return "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)


def listar_clientes_chatbot():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
    clientes = cursor.fetchall()
    conn.close()

    if not clientes:
        return "Nenhum cliente cadastrado ainda. 📭"

    linhas = [f"👤 {c[0]} (Pet: {c[1]})" for c in clientes]
    return "Aqui estão os clientes cadastrados:\n" + "\n".join(linhas)


from flask import jsonify, request
import re

# memória de contexto simples
user_context = {}

from unidecode import unidecode

from unidecode import unidecode
from flask import request, jsonify

from unidecode import unidecode
from flask import request, jsonify

from flask import jsonify, request
import sqlite3
import re
from unidecode import unidecode

@app.route("/api/chat_simple", methods=["POST"])
def api_chat_simple():
    data = request.get_json()
    user_message = data.get("message", "").strip().lower()
    user_message = unidecode(user_message)  # remove acentos

    # ========= RESPOSTAS BÁSICAS =========
    if any(p in user_message for p in ["oi", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"response": "Olá! 😊 Como posso te ajudar hoje?"})

    if any(p in user_message for p in ["obrigado", "obrigada", "valeu", "agradecido", "vlw"]):
        return jsonify({"response": "De nada! 😄 Sempre à disposição."})

    # ========= LISTAR PETS =========
        # ========= LISTAR PETS =========
    # ========= LISTAR PETS =========
    if "listar pets" in user_message or "meus pets" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, nome_tutor, raca FROM pet")
        pets = cursor.fetchall()
        conn.close()

        if pets:
            lista = "\n".join([
                f"🐾 Pet: {p[0]}\n   👤 Tutor: {p[1]}\n   🐶 Raça: {p[2]}"
                for p in pets
            ])
            return jsonify({"response": f"Aqui estão os pets cadastrados:\n\n{lista}"})
        else:
            return jsonify({"response": "Nenhum pet cadastrado ainda. 🐾"})



    # ========= LISTAR CLIENTES =========
    if "listar clientes" in user_message or "clientes" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_cliente, nome_pet FROM cliente")
        clientes = cursor.fetchall()
        conn.close()

        if clientes:
            lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
            return jsonify({"response": f"Aqui estão os clientes cadastrados:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum cliente cadastrado ainda."})


    # ========= LISTAR AGENDAMENTOS =========
    if "listar agendamentos" in user_message or "agendamentos" in user_message:
        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome_pet, tipo_servico, data, horario FROM agendamentos ORDER BY data, horario")
        ags = cursor.fetchall()
        conn.close()

        if ags:
            lista = "\n".join([f"📅 {a[0]} - {a[1]} em {a[2]} às {a[3]}" for a in ags])
            return jsonify({"response": f"Aqui estão os agendamentos:\n{lista}"})
        else:
            return jsonify({"response": "Nenhum agendamento encontrado."})

    # ========= CASO PADRÃO =========
    return jsonify({"response": "Desculpe, não entendi 😅. Você pode pedir para listar pets, clientes ou agendamentos."})


from flask import jsonify
import re
import sqlite3
from datetime import datetime, timedelta

@app.route("/api/chat_acoes", methods=["POST"])
def api_chat_acoes():
    data = request.get_json()
    msg = data.get("message", "").lower().strip()

    # === INTERPRETA SAUDAÇÕES ===
    if any(p in msg for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return jsonify({"reply": "Olá! Eu sou o PetBot 🐾 Como posso te ajudar hoje?"})

    # === INTERPRETA PEDIDO DE AGENDAMENTO ===
    if any(k in msg for k in ["agendar", "agd", "marcar"]) and "listar" not in msg:
        servicos = ["banho", "tosa", "consulta", "vacinação", "vacina"]
        tipo_servico = next((s for s in servicos if s in msg), None)

        if "amanh" in msg:
            data_agendamento = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        elif "hoje" in msg:
            data_agendamento = datetime.now().strftime("%d/%m/%Y")
        else:
            m_data = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", msg)
            data_agendamento = m_data.group(1) if m_data else None

        m_hora = re.search(r"(\d{1,2}[:h]\d{0,2})", msg)
        horario = m_hora.group(1).replace("h", ":00") if m_hora else None

        m_pet = re.search(r"para\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        nome_pet = m_pet.group(1).capitalize() if m_pet else "Pet não informado"

        if not all([tipo_servico, data_agendamento, horario]):
            return jsonify({"reply": "Preciso de mais informações: serviço, data e horário. Pode me dizer tudo de uma vez? 😊"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agendamentos (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Empresa", nome_pet, tipo_servico.capitalize(), data_agendamento, horario, "Agendado via PetBot"))

        conn.commit()
        conn.close()

        return jsonify({
            "reply": f"Agendamento de {tipo_servico} para {nome_pet} em {data_agendamento} às {horario} registrado com sucesso! ✅"
        })

    # === INTERPRETA CADASTRO DE PET ===
    if "cadastrar pet" in msg or "novo pet" in msg:
        nome = re.search(r"pet\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        tutor = re.search(r"tutor\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        raca = re.search(r"ra[çc]a\s+([a-zA-ZÀ-ÿ0-9_]+)", msg)
        idade = re.search(r"idade\s+(\d+)", msg)
        peso = re.search(r"peso\s+(\d+[.,]?\d*)", msg)

        nome_pet = nome.group(1).capitalize() if nome else None
        nome_tutor = tutor.group(1).capitalize() if tutor else None
        raca_pet = raca.group(1).capitalize() if raca else None
        idade_pet = int(idade.group(1)) if idade else None
        peso_pet = float(peso.group(1).replace(",", ".")) if peso else None

        if not all([nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet]):
            return jsonify({"reply": "Faltam alguns dados! Diga tudo na mesma frase: ex: 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg' 🐶"})

        conn = sqlite3.connect("petcare.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pet (nome_pet, nome_tutor, raca, idade, peso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome_pet, nome_tutor, raca_pet, idade_pet, peso_pet))
        conn.commit()
        conn.close()

        return jsonify({"reply": f"Pet {nome_pet} cadastrado com sucesso! 🐾"})

    # === LISTAR PETS ===
    if "listar" in msg and "pet" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_pet, nome_tutor FROM pet ORDER BY nome_pet")
            pets = cursor.fetchall()
            conn.close()

            if pets:
                lista = "\n".join([f"🐶 {p[0]} (Tutor: {p[1]})" for p in pets])
                reply = f"Aqui estão os pets cadastrados:\n{lista}"
            else:
                reply = "Não há pets cadastrados ainda. 🐾"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR CLIENTES ===
    if "listar" in msg and "cliente" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome_cliente, nome_pet FROM cliente ORDER BY nome_cliente")
            clientes = cursor.fetchall()
            conn.close()

            if clientes:
                lista = "\n".join([f"👤 {c[0]} (Pet: {c[1]})" for c in clientes])
                reply = f"Aqui estão os clientes cadastrados:\n{lista}"
            else:
                reply = "Nenhum cliente cadastrado ainda. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === LISTAR AGENDAMENTOS ===
    if "listar" in msg and "agendamento" in msg:
        try:
            conn = sqlite3.connect("petcare.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT nome_pet, tipo_servico, data, horario
                FROM agendamento
                WHERE nome_pet IS NOT NULL
                ORDER BY 
                    substr(data, 7, 4),  -- ano
                    substr(data, 4, 2),  -- mês
                    substr(data, 1, 2),  -- dia
                    horario
            """)
            agds = cursor.fetchall()
            conn.close()

            if agds:
                linhas = [f"📅 {a[0]} ({a[1]}) - {a[2]} às {a[3]}" for a in agds]
                reply = "Aqui estão os agendamentos registrados:\n" + "\n".join(linhas)
            else:
                reply = "Nenhum agendamento encontrado. 📭"

        except Exception as e:
            reply = f"Ocorreu um erro ao acessar o banco: {e}"

        return jsonify({"reply": reply})

    # === OUTRAS INTERAÇÕES ===
    if any(p in msg for p in ["obrigado", "valeu"]):
        return jsonify({"reply": "De nada! 😺 Sempre que precisar, estarei por aqui!"})

    if any(p in msg for p in ["tchau", "até", "flw", "falou"]):
        return jsonify({"reply": "Tchau tchau! 👋 Espero te ver em breve!"})
    

    # === CASO NÃO ENTENDA ===
    return jsonify({
        "reply": "Desculpe, não entendi bem. Você pode tentar algo como: 'Agendar banho amanhã às 15h para Luna' ou 'Cadastrar pet Bolt, tutor André, raça Golden, idade 3, peso 20 kg'."
    })
    
    def recomendar_servicos(servico_base):
        """Sugere serviços ou produtos relacionados ao agendamento atual"""
    recomendacoes = {
        "banho": ["tosa", "hidratação", "perfume pet"],
        "tosa": ["banho", "corte de unhas"],
        "consulta": ["vacinação", "vermifugação"],
        "vacinação": ["vermifugação", "check-up"],
    }

    return recomendacoes.get(servico_base.lower(), ["Sem recomendações no momento"])

# 🔹 Página de FAQs
@app.route("/faqs")
def faqs():
    return render_template("faqs.html")

def servicos_mais_populares(limit=4):
    """
    Retorna os serviços mais agendados, para exibir na home.
    """
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo_servico, COUNT(*) AS total
        FROM agendamento
        GROUP BY tipo_servico
        ORDER BY total DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/previsoes")
def previsoes():
    # renderiza o template com o mockup; você pode passar dados reais aqui ou carregá-los via AJAX
    return render_template("previsoes.html")

@app.route("/previsao_image")
def previsao_image():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    # pega datas (no formato que você tem no banco: pode ser 'dd/mm/YYYY' ou 'YYYY-mm-dd')
    cursor.execute("SELECT data FROM agendamento WHERE data IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    datas = [r[0] for r in rows]

    if not datas:
        # retorna imagem simples com texto ou um JSON
        return "Ainda não há dados suficientes para previsão.", 400

    # normaliza formatos: detecta se tem '/' -> dd/mm/YYYY else assume ISO yyyy-mm-dd
    normalized = []
    for d in datas:
        if "/" in d:
            # dd/mm/YYYY
            try:
                dt = pd.to_datetime(d, format="%d/%m/%Y", dayfirst=True)
            except Exception:
                dt = pd.to_datetime(d, dayfirst=True, errors='coerce')
        else:
            try:
                dt = pd.to_datetime(d, format="%Y-%m-%d")
            except Exception:
                dt = pd.to_datetime(d, dayfirst=False, errors='coerce')
        if pd.notnull(dt):
            normalized.append(dt)

    if not normalized:
        return "Não consegui interpretar as datas do banco.", 400

    df = pd.DataFrame({"data": normalized})
    df_count = df.groupby("data").size().reset_index(name="quantidade")

    # converte para ordinal (número)
    df_count['dia_ord'] = df_count['data'].map(lambda x: x.toordinal())

    X = df_count[['dia_ord']].values
    y = df_count['quantidade'].values

    # cuidado: se y tem poucos pontos, a regressão pode falhar; tratar
    if len(X) < 2:
        return "Dados insuficientes para treinar modelo.", 400

    model = LinearRegression()
    model.fit(X, y)

    # prever próximos 7 dias
    last = int(df_count['dia_ord'].max())
    futuros = np.array([last + i for i in range(1, 8)]).reshape(-1, 1)
    preds = model.predict(futuros)

    # montagem do gráfico com o estilo do site
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df_count['data'], df_count['quantidade'], label='Histórico', marker='o', color='#2F8F6D')
    futuras_dt = [pd.to_datetime(pd.Timestamp.fromordinal(int(v))) for v in futuros.flatten()]
    ax.plot(futuras_dt, preds, label='Previsão', linestyle='--', marker='o', color='#7ADCB3')
    ax.set_title('Previsão de Agendamentos (próximos 7 dias)')
    ax.set_ylabel('Número de agendamentos')
    ax.legend()
    ax.grid(alpha=0.12)

    # salva em buffer
    buf = io.BytesIO()
    plt.tight_layout()
    fig.patch.set_facecolor('white')
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return send_file(buf, mimetype='image/png')

def enviar_lembrete_email(email_destino, nome_pet, nome_cliente, data, horario, id_agendamento):

    # URL do agendamento
    link = f"http://localhost:5000/agendamentos/{id_agendamento}"

    # Gera QR Code
    img = qrcode.make(link)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    qr_bytes = buffer.read()

    # Corpo do e-mail em HTML
    corpo = f"""
    <h2>🐾 Lembrete de Agendamento - PetCare</h2>
    <p>Olá <strong>{nome_cliente}</strong>! Aqui está o lembrete do agendamento do pet <strong>{nome_pet}</strong>.</p>

    <p><strong>📆 Data:</strong> {data}<br>
    <strong>⏰ Horário:</strong> {horario}</p>

    <p>Use o QR Code abaixo para ver os detalhes:</p>

    <img src="cid:qrcode" alt="QR Code">

    <p>Até breve!<br>Equipe PetCare 💚</p>
    """

    msg = Message("📌 Lembrete de Agendamento - PetCare", recipients=[email_destino])
    msg.html = corpo

    # Anexa o QR Code
    msg.attach("qrcode.png", "image/png", qr_bytes, disposition="inline", headers=[("Content-ID", "<qrcode>")])

    mail.send(msg)
    
import datetime as dt
@app.route("/enviar_lembretes")
def enviar_lembretes():

    import datetime
    hoje = datetime.date.today()

    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_cliente, nome_pet, data, horario, email FROM agendamento")
    ags = cursor.fetchall()
    conn.close()

    futuros = []

    for ag in ags:
        id_ag, cliente, pet, data_str, hora, email = ag

        # Se não tem email, pula
        if not email:
            continue

        # Tenta converter formato YYYY-MM-DD
        data_real = None
        try:
            data_real = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
        except:
            pass

        # Tenta converter formato DD/MM/YYYY
        if data_real is None:
            try:
                data_real = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            except:
                continue

        # Agora SIM podemos comparar
        if data_real >= hoje:
            futuros.append((id_ag, cliente, pet, data_real, hora, email))

    if not futuros:
        return "Nenhum agendamento futuro encontrado para enviar lembretes."

    # Envia os emails
    for ag in futuros:
        id_ag, cliente, pet, data_real, hora, email = ag

        enviar_lembrete_email(
            email_destino=email,
            nome_pet=pet,
            nome_cliente=cliente,
            data=data_real.strftime("%d/%m/%Y"),
            horario=hora,
            id_agendamento=id_ag
        )

    return f"{len(futuros)} lembretes enviados com sucesso!"


# Função para adicionar uma nova notificação ao banco de dados
def adicionar_notificacao(titulo, mensagem):
    import datetime
    # Pega a data e hora atual formatada
    data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # Conecta ao banco
    conn = sqlite3.connect("petcare.db")
    cur = conn.cursor()

    # Insere a notificação no banco
    cur.execute("""
        INSERT INTO notificacoes (titulo, mensagem, data)
        VALUES (?, ?, ?)
    """, (titulo, mensagem, data))

    # Salva as alterações
    conn.commit()
    conn.close()


# Função que busca todas as notificações
def buscar_notificacoes():
    # Conecta ao banco
    conn = sqlite3.connect("petcare.db")
    cur = conn.cursor()

    # Seleciona todas as notificações, mais recentes primeiro
    cur.execute("SELECT id, titulo, mensagem, data, lida FROM notificacoes ORDER BY id DESC")
    notificacoes = cur.fetchall()

    # Fecha o banco
    conn.close()
    return notificacoes


# Rota para marcar uma notificação como lida
@app.route("/notificacoes_ler/<int:id>", methods=["POST"])
def notificacoes_ler(id):
    # Conecta ao banco
    conn = sqlite3.connect("petcare.db")
    cur = conn.cursor()

    # Atualiza o campo 'lida' para 1 (verdadeiro)
    cur.execute("UPDATE notificacoes SET lida = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    # Retorno vazio com sucesso (204 = OK, sem conteúdo)
    return ("", 204)


# API que retorna as notificações em formato JSON (usada pelo JavaScript do sino)
@app.route("/api/notificacoes")
def api_notificacoes():
    # Conecta ao banco
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()

    # Busca as 20 notificações mais recentes
    cursor.execute("SELECT id, titulo, mensagem, lida, data FROM notificacoes ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()

    # Monta a lista de notificações em formato JSON
    notificacoes = []
    for r in rows:
        notificacoes.append({
            "id": r[0],        # ID da notificação
            "titulo": r[1],    # Título da notificação
            "mensagem": r[2],  # Texto da notificação
            "lida": r[3],      # Status (0 = não lida, 1 = lida)
            "data": r[4]       # Data formatada
        })

    # Retorna JSON para o frontend
    return jsonify(notificacoes)







if __name__ == '__main__':
    init_db()
    app.run(debug=True)
