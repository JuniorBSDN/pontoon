import os
from flask import Flask, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

# =================================================================
# CONFIGURAÇÃO DO SUPABASE E VARIÁVEIS DE AMBIENTE
# =================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL:
    db_ponto = os.environ.get("DB_PONTO_ON", "")
    SUPABASE_URL = db_ponto if db_ponto.startswith("http") else None

# PROTEÇÃO CONTRA CRASH FATAL: Impede que erro de URL derrube a Vercel
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        supabase = None
except Exception as e:
    print(f"Erro ao conectar com Supabase: {e}")
    supabase = None


# =================================================================
# 1. ROTA: LOGIN MASTER (Valida a variável SENHA_MASTER_PONTO)
# =================================================================
@app.route('/api/login-master', methods=['POST'])
def login_master():
    data = request.json or {}
    senha_digitada = data.get('senha', '')

    # Lê a senha master configurada no ambiente da Vercel
    senha_master_env = os.environ.get("SENHA_MASTER_PONTO", "pontoON2026master*")

    if senha_digitada == senha_master_env:
        return jsonify({
            "status": "success",
            "message": "Master autenticado com sucesso!",
            "token": "master_secure_token_123"
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Senha master incorreta."
        }), 401


# =================================================================
# 2. ROTA: LOGIN ADMIN / EMPRESA (Valida CNPJ e Senha no Supabase)
# =================================================================
@app.route('/api/login-admin', methods=['POST'])
def login_admin():
    data = request.json or {}
    cnpj_digitado = data.get('cnpj', '').strip()
    senha_digitada = data.get('senha', '').strip()

    if not supabase:
        return jsonify(
            {"status": "error", "message": "Banco de dados Supabase não configurado nas variáveis de ambiente."}), 500

    try:
        response = supabase.table('empresas').select('*').eq('cnpj', cnpj_digitado).execute()
        empresas = response.data

        if not empresas or len(empresas) == 0:
            return jsonify({"status": "error", "message": "CNPJ não cadastrado pelo Master no sistema."}), 404

        empresa = empresas[0]

        if empresa.get('senha') == senha_digitada:
            if empresa.get('status') == 'pendente':
                return jsonify({"status": "error", "message": "Empresa pendente de ativação pelo Master."}), 403

            return jsonify({
                "status": "success",
                "message": "Login efetuado com sucesso!",
                "nome_fantasia": empresa.get('nome_fantasia', 'Empresa'),
                "token": f"admin_token_{cnpj_digitado}"
            }), 200
        else:
            return jsonify({"status": "error", "message": "Senha incorreta para este CNPJ."}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro interno ao consultar banco: {str(e)}"}), 500


# =================================================================
# 3. ROTA: LOGIN DO COLABORADOR / PRESTADOR (Valida CPF e Senha)
# =================================================================
@app.route('/api/login-colaborador', methods=['POST'])
def login_colaborador():
    data = request.json or {}
    cpf_digitado = data.get('cpf', '').strip()
    senha_digitada = data.get('senha', '').strip()

    if not supabase:
        return jsonify({"status": "error", "message": "Supabase não configurado."}), 500

    try:
        response = supabase.table('funcionarios').select('*').eq('cpf', cpf_digitado).execute()
        funcionarios = response.data

        if not funcionarios or len(funcionarios) == 0:
            return jsonify({"status": "error", "message": "CPF não encontrado no sistema."}), 404

        func = funcionarios[0]

        if func.get('senha') == senha_digitada:
            if func.get('status') == 'bloqueado':
                return jsonify({"status": "error", "message": "Colaborador bloqueado pelo RH."}), 403

            return jsonify({
                "status": "success",
                "message": "Login realizado com sucesso!",
                "nome": func.get('nome_completo', 'Colaborador'),
                "empresa": func.get('empresa', 'Unidade Matriz'),
                "token": f"colab_token_{cpf_digitado}"
            }), 200
        else:
            return jsonify({"status": "error", "message": "Senha incorreta."}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro interno: {str(e)}"}), 500


# =================================================================
# 4. ROTA: CADASTRAR NOVA EMPRESA (Executada pelo Master)
# =================================================================
@app.route('/api/cadastrar-empresa', methods=['POST'])
def cadastrar_empresa():
    data = request.json or {}

    if not supabase:
        return jsonify({"status": "error", "message": "Supabase offline."}), 500

    try:
        novo_registro = {
            "razao_social": data.get('razao_social'),
            "nome_fantasia": data.get('nome_fantasia'),
            "cnpj": data.get('cnpj'),
            "responsavel": data.get('responsavel'),
            "contato": data.get('contato'),
            "email": data.get('email'),
            "endereco": data.get('endereco'),
            "plano": data.get('plano'),
            "vencimento": data.get('vencimento'),
            "senha": data.get('senha', '123456'),
            "status": data.get('status', 'ativo')
        }

        supabase.table('empresas').insert(novo_registro).execute()
        return jsonify({"status": "success", "message": "Empresa cadastrada com sucesso no banco de dados!"}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": f"Erro ao cadastrar: {str(e)}"}), 500


# =================================================================
# 5. ROTA DE VERIFICAÇÃO (HEALTHCHECK)
# =================================================================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "supabase_connected": supabase is not None,
        "routes": [
            "/api/login-master",
            "/api/login-admin",
            "/api/login-colaborador",
            "/api/cadastrar-empresa"
        ]
    }), 200


if __name__ == '__main__':
    app.run(debug=True)