# Pedidos Internos — Sistema SaaS de Controle de Solicitações

Sistema web para gerenciar solicitações internas de empresas: materiais, férias, manutenção e outros pedidos.

## Rodando localmente

### 1. Clone ou copie os arquivos

```bash
cd empresarial
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite .env e defina uma SECRET_KEY segura
```

### 5. Rode o servidor de desenvolvimento

```bash
python app.py
```

Acesse: <http://localhost:5000>

O banco SQLite é criado automaticamente em `empresarial.db`.

---

## Deploy no Render.com

### Passo a passo

1. Crie uma conta em [render.com](https://render.com)
2. Clique em **New > Web Service**
3. Conecte seu repositório Git
4. Configure:

   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

### Variáveis de ambiente no Render

No painel do serviço, vá em **Environment** e adicione:

| Variável | Valor |
| - | - |
| `SECRET_KEY` | Gere com: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | URL do PostgreSQL (veja abaixo) |
| `FLASK_ENV` | `production` |

### Banco de dados PostgreSQL no Render

1. Crie um **New > PostgreSQL** no Render
2. Copie a **Internal Database URL**
3. Cole em `DATABASE_URL` nas variáveis do Web Service

> O SQLAlchemy aceita URLs `postgres://` e `postgresql://`. Se o Render retornar `postgres://`, troque por `postgresql://` manualmente.

---

## Perfis de acesso

| Perfil | O que pode fazer |
| - | - |
| `employee` | Abrir pedidos, ver apenas os seus pedidos |
| `approver` | Aprovar/rejeitar pedidos, ver todos, abrir pedidos |
| `admin` | Tudo: usuários, status, aprovações, dashboard completo |

## Estrutura de arquivos

```
empresarial/
├── app.py               # Flask app principal
├── models.py            # Modelos SQLAlchemy
├── requirements.txt
├── .env.example
├── Procfile
├── runtime.txt
├── static/
│   ├── css/style.css
│   └── js/app.js
└── templates/
    ├── base.html
    ├── index.html
    ├── planos.html
    ├── auth/
    │   ├── login.html
    │   └── cadastro.html
    ├── app/
    │   ├── dashboard.html
    │   ├── solicitacoes/
    │   │   ├── lista.html
    │   │   ├── nova.html
    │   │   └── detalhe.html
    │   └── admin/
    │       └── usuarios.html
    └── errors/
        ├── 403.html
        └── 404.html
```

