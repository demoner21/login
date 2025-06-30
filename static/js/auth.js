        // Elementos DOM
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const loginErrorMessage = document.getElementById('loginErrorMessage');
        const registerErrorMessage = document.getElementById('registerErrorMessage');
        const registerSuccessMessage = document.getElementById('registerSuccessMessage');
        
        // Alternar entre formulários
        function toggleForm(formId) {
            document.querySelectorAll('.form-container').forEach(form => {
                form.classList.remove('active');
            });
            document.getElementById(formId).classList.add('active');
            clearMessages();
        }
        
        // Limpar mensagens de erro/sucesso
        function clearMessages() {
            loginErrorMessage.style.display = 'none';
            registerErrorMessage.style.display = 'none';
            registerSuccessMessage.style.display = 'none';
        }
        
        // Mostrar mensagem de erro no login
        function showLoginError(message) {
            loginErrorMessage.textContent = message;
            loginErrorMessage.style.display = 'block';
        }
        
        // Mostrar mensagem de erro no cadastro
        function showRegisterError(message) {
            registerErrorMessage.textContent = message;
            registerErrorMessage.style.display = 'block';
        }
        
        // Mostrar mensagem de sucesso no cadastro
        function showRegisterSuccess(message) {
            registerSuccessMessage.textContent = message;
            registerSuccessMessage.style.display = 'block';
        }
        
        // Validar força da senha
        function isPasswordStrong(password) {
            return password.length >= 8 &&
                   /[A-Z]/.test(password) &&
                   /[0-9]/.test(password);
        }
        
        // Login
        loginForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            clearMessages();
            
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('loginPassword').value.trim();
            const loginButton = document.getElementById('loginButton');
            
            if (!username || !password) {
                showLoginError("Por favor, preencha todos os campos.");
                return;
            }
            
            try {
                loginButton.disabled = true;
                loginButton.textContent = "Autenticando...";
                
                const response = await fetch('/api/v1/auth/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        username: username,
                        password: password,
                        grant_type: 'password'
                    })
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    showLoginError(errorData.detail || "Credenciais inválidas. Tente novamente.");
                    return;
                }
                
                const { access_token, refresh_token } = await response.json();
                
                // Armazenar tokens de forma segura
                localStorage.setItem('access_token', access_token);
                localStorage.setItem('refresh_token', refresh_token);
                
                // Redirecionar para a página principal
                window.location.href = '/static/login.html';
                
            } catch (error) {
                console.error('Erro no login:', error);
                showLoginError("Erro ao conectar ao servidor. Tente novamente.");
            } finally {
                loginButton.disabled = false;
                loginButton.textContent = "Login";
            }
        });
        
        // Cadastro
        registerForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            clearMessages();
            
            const name = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const confirmEmail = document.getElementById('confirmEmail').value.trim();
            const password = document.getElementById('registerPassword').value.trim();
            const confirmPassword = document.getElementById('confirmPassword').value.trim();
            const registerButton = document.getElementById('registerButton');
            
            // Validações
            if (!name || !email || !confirmEmail || !password || !confirmPassword) {
                showRegisterError("Preencha todos os campos.");
                return;
            }
            
            if (email !== confirmEmail) {
                showRegisterError("Os e-mails não coincidem.");
                return;
            }
            
            if (password !== confirmPassword) {
                showRegisterError("As senhas não coincidem.");
                return;
            }
            
            if (!isPasswordStrong(password)) {
                showRegisterError("A senha deve ter pelo menos 8 caracteres, incluindo uma letra maiúscula e um número.");
                return;
            }
            
            try {
                registerButton.disabled = true;
                registerButton.textContent = "Registrando...";
                
                const response = await fetch('/api/v1/auth/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        nome: name,
                        email: email,
                        confirmar_email: confirmEmail,
                        senha: password,
                        confirmar_senha: confirmPassword
                    })
                });
                
                if (response.ok) {
                    showRegisterSuccess("Cadastro realizado com sucesso! Faça login para continuar.");
                    registerForm.reset();
                    setTimeout(() => toggleForm('loginFormContainer'), 2000);
                } else {
                    const errorData = await response.json();
                    showRegisterError(errorData.detail || "Erro ao cadastrar. Tente novamente.");
                }
            } catch (error) {
                console.error('Erro no cadastro:', error);
                showRegisterError("Erro ao conectar ao servidor. Tente novamente.");
            } finally {
                registerButton.disabled = false;
                registerButton.textContent = "Cadastrar";
            }
        });