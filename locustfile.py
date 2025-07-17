import os
import random
import shutil
import tempfile
from locust import HttpUser, task, between

# --- Dados de Teste ---
# Cada dicionário representa um conjunto de dados para um usuário virtual.
TEST_USERS = [
    {"email": "user1@exemplo.com", "password": "SenhaForte123", "data_dir": "user1"},
    {"email": "user2@exemplo.com", "password": "SenhaForte123", "data_dir": "user2"},
    {"email": "user3@exemplo.com", "password": "SenhaForte123", "data_dir": "user3"},
    {"email": "user4@exemplo.com", "password": "SenhaForte123", "data_dir": "user4"},
    {"email": "user5@exemplo.com", "password": "SenhaForte123", "data_dir": "user5"},
]

SHAPEFILE_DIR = "tests/test_data/"

class ApiUser(HttpUser):
    host = "http://localhost:8000"
    wait_time = between(1, 3)
    
    # ID numérico único para cada usuário virtual, fornecido pelo Locust.
    _user_id_counter = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # --- LÓGICA DE DISTRIBUIÇÃO SEGURA DE USUÁRIOS ---
        # Usa o operador de módulo para distribuir os usuários da lista de forma cíclica e segura.
        # Isso garante que cada usuário virtual tenha credenciais únicas, mesmo em modo distribuído.
        user_index = ApiUser._user_id_counter % len(TEST_USERS)
        self.user_credentials = TEST_USERS[user_index]
        ApiUser._user_id_counter += 1
        
        self.data_dir_name = self.user_credentials["data_dir"]
        self.temp_dir = tempfile.mkdtemp(prefix=f"{self.data_dir_name}_")
        self.access_token = None

    def on_start(self):
        # Copia os dados para um diretório temporário
        template_data_path = os.path.join(SHAPEFILE_DIR, self.data_dir_name)
        if not os.path.isdir(template_data_path):
            self.environment.runner.quit()
            return
        shutil.copytree(template_data_path, self.temp_dir, dirs_exist_ok=True)

        # Realiza o login e armazena o token manualmente
        with self.client.post(
            "/api/v1/auth/token",
            data={"username": self.user_credentials["email"], "password": self.user_credentials["password"]},
            name="/auth/token",
            catch_response=True
        ) as response:
            if response.status_code == 204 and "access_token" in response.cookies:
                self.access_token = response.cookies.get("access_token")
            else:
                response.failure(f"Falha na autenticação para {self.user_credentials['email']}.")
                self.environment.runner.quit()

    def on_stop(self):
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @task(1)
    def list_rois(self):
        if not self.access_token: return
        self.client.get(
            "/api/v1/roi/",
            name="/roi/ (list)",
            cookies={"access_token": self.access_token}
        )

    @task(2)
    def get_user_profile(self):
        if not self.access_token: return
        self.client.get(
            "/api/v1/users/me",
            name="/users/me",
            cookies={"access_token": self.access_token}
        )

    @task(3)
    def upload_shapefile(self):
        if not self.access_token: return

        shapefile_base_path = os.path.join(self.temp_dir, 'fazenda_teste')
        try:
            files_to_upload = {
                'shp': open(f'{shapefile_base_path}.shp', 'rb'),
                'shx': open(f'{shapefile_base_path}.shx', 'rb'),
                'dbf': open(f'{shapefile_base_path}.dbf', 'rb'),
            }
        except FileNotFoundError:
            return

        try:
            form_data = {'propriedade_col': 'Propriedad', 'talhao_col': 'Talhao'}
            self.client.post(
                "/api/v1/roi/upload-shapefile-splitter",
                data=form_data,
                files=files_to_upload,
                cookies={"access_token": self.access_token},
                name="/roi/upload-shapefile-splitter"
            )
        finally:
            for f in files_to_upload.values():
                f.close()