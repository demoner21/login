# seed_database.py
import asyncio
import asyncpg
from passlib.context import CryptContext

# Importa as configurações do seu conftest ou de um arquivo central de config
from tests.conftest import DB_CONFIG 

# Contexto para hash de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dados que devem corresponder ao seu locustfile.py e arquivos de teste
USERS_TO_CREATE = [
    {"email": "user1@exemplo.com", "password": "SenhaForte123", "nome": "Usuário de Teste 1"},
    {"email": "user2@exemplo.com", "password": "SenhaForte123", "nome": "Usuário de Teste 2"},
    {"email": "user3@exemplo.com", "password": "SenhaForte123", "nome": "Usuário de Teste 3"},
    {"email": "user4@exemplo.com", "password": "SenhaForte123", "nome": "Usuário de Teste 4"},
    {"email": "user5@exemplo.com", "password": "SenhaForte123", "nome": "Usuário de Teste 5"},
]

ROIS_TO_CREATE = [
    {
        "roi_id": 2898,
        "user_email": "user1@exemplo.com",
        "nome": "ROI 2898 para Análise",
        "tipo_roi": "TALHAO",
        "tipo_origem": "TEST_DATA",
        "metadata": '{"area_ha": 20.0}'
    }
]

async def seed_data():
    """Conecta ao DB e insere os dados de teste necessários."""
    conn = await asyncpg.connect(**DB_CONFIG)
    print("Conectado ao banco de dados para seeding...")

    try:
        # Limpa as tabelas para um estado inicial limpo (OPCIONAL)
        print("Limpando tabelas existentes...")
        await conn.execute("TRUNCATE TABLE usuario, regiao_de_interesse RESTART IDENTITY CASCADE;")

        # Cria os usuários
        print(f"Criando {len(USERS_TO_CREATE)} usuários...")
        for user in USERS_TO_CREATE:
            hashed_password = pwd_context.hash(user["password"])
            await conn.execute(
                "INSERT INTO usuario (nome, email, senha) VALUES ($1, $2, $3)",
                user["nome"], user["email"], hashed_password
            )
        print("Usuários criados com sucesso.")

        # Cria as ROIs
        print(f"Criando {len(ROIS_TO_CREATE)} ROIs de teste...")
        for roi in ROIS_TO_CREATE:
            # Pega o ID do usuário baseado no email
            user_id = await conn.fetchval("SELECT id FROM usuario WHERE email = $1", roi["user_email"])
            if user_id:
                await conn.execute(
                    """
                    INSERT INTO regiao_de_interesse (roi_id, user_id, nome, tipo_roi, tipo_origem, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    roi["roi_id"], user_id, roi["nome"], roi["tipo_roi"], roi["tipo_origem"], roi["metadata"]
                )
            else:
                print(f"AVISO: Usuário com email {roi['user_email']} não encontrado. ROI não criada.")
        print("ROIs criadas com sucesso.")

    finally:
        await conn.close()
        print("Conexão com o banco fechada.")

if __name__ == "__main__":
    asyncio.run(seed_data())