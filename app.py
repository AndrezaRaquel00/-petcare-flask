# Importa as bibliotecas necessárias
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv
import sqlite3

load_dotenv()

app = Flask(__name__)
app.secret_key = "petcare_secret"  # Necessário para usar flash messages

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

        flash("Pet cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_pets"))

    return render_template("novo_pet.html")

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
            INSERT INTO agendamento (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_cliente, nome_pet, tipo_servico, data, horario, observacoes))
        conn.commit()
        conn.close()

        # 📩 Envia e-mail para a empresa
        corpo = f"""
📅 Novo Agendamento!

Cliente: {nome_cliente}
Pet: {nome_pet}
Serviço: {tipo_servico}
Data: {data}
Horário: {horario}
Observações: {observacoes}
"""
        enviar_email("Novo Agendamento Cadastrado", corpo)

        flash("Agendamento cadastrado com sucesso e e-mail enviado!", "success")
        return redirect(url_for("listar_agendamentos"))
    
    return render_template("novo_agendamento.html")

# -------------------------
# OUTRAS ROTAS
# -------------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/agendamentos")
def listar_agendamentos():
    conn = sqlite3.connect("petcare.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agendamento ORDER BY data, horario")
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

# -------------------------
# START
# -------------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
