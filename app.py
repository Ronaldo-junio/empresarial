import os
from datetime import datetime, timezone, timedelta, date
from functools import wraps

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from dotenv import load_dotenv

from models import db, Company, User, Request, RequestHistory

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-troque-em-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///empresarial.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.role not in roles:
                flash("Você não tem permissão para acessar esta página.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def trial_check():
    if not current_user.is_authenticated:
        return None
    company = current_user.company
    if not company.active:
        flash("Sua conta foi desativada. Entre em contato com o suporte.", "danger")
        return redirect(url_for("login"))
    if company.plan == "trial" and not company.is_trial_active():
        return redirect(url_for("planos"))
    return None


def seed_demo_data(company, admin_user):
    approver = User(
        company_id=company.id,
        name="Ana Aprovadora",
        email=f"aprovador@{company.email.split('@')[1]}",
        role="approver",
        active=True,
    )
    approver.set_password("demo1234")
    db.session.add(approver)
    db.session.flush()

    demo_requests = [
        {
            "type": "material",
            "description": "Compra de 10 resmas de papel A4 para o setor administrativo.",
            "needed_date": date.today() + timedelta(days=5),
            "sector": "Administrativo",
            "status": "pendente",
        },
        {
            "type": "ferias",
            "description": "Solicitação de férias de 15 dias no período de 01/08 a 15/08.",
            "needed_date": date(2026, 8, 1),
            "sector": "RH",
            "status": "aprovado",
        },
        {
            "type": "manutencao",
            "description": "Conserto do ar-condicionado da sala de reuniões — parou de refrigerar.",
            "needed_date": date.today() + timedelta(days=2),
            "sector": "Infraestrutura",
            "status": "em_andamento",
        },
    ]

    for idx, data in enumerate(demo_requests):
        req = Request(
            company_id=company.id,
            type=data["type"],
            description=data["description"],
            needed_date=data["needed_date"],
            sector=data["sector"],
            status=data["status"],
            created_by=admin_user.id,
        )
        if data["status"] in ("aprovado", "em_andamento"):
            req.approved_by = approver.id
        db.session.add(req)
        db.session.flush()

        db.session.add(RequestHistory(
            request_id=req.id,
            user_id=admin_user.id,
            action="Solicitação criada",
            note=None,
        ))

        if data["status"] == "aprovado":
            db.session.add(RequestHistory(
                request_id=req.id,
                user_id=approver.id,
                action="Solicitação aprovada",
                note="Aprovado conforme orçamento disponível.",
            ))
        elif data["status"] == "em_andamento":
            db.session.add(RequestHistory(
                request_id=req.id,
                user_id=approver.id,
                action="Solicitação aprovada",
                note="Manutenção agendada.",
            ))
            db.session.add(RequestHistory(
                request_id=req.id,
                user_id=admin_user.id,
                action="Status alterado para Em Andamento",
                note=None,
            ))

    db.session.commit()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/planos")
def planos():
    return render_template("planos.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        user_name = request.form.get("user_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not company_name:
            errors.append("Nome da empresa é obrigatório.")
        if not user_name:
            errors.append("Seu nome é obrigatório.")
        if not email or "@" not in email:
            errors.append("E-mail inválido.")
        if len(password) < 6:
            errors.append("A senha deve ter pelo menos 6 caracteres.")
        if password != confirm:
            errors.append("As senhas não coincidem.")

        existing = Company.query.filter_by(email=email).first()
        if existing:
            errors.append("Este e-mail já está cadastrado.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/cadastro.html",
                                   company_name=company_name,
                                   user_name=user_name,
                                   email=email)

        trial_end = datetime.now(timezone.utc) + timedelta(days=7)
        company = Company(name=company_name, email=email, plan="trial", trial_end=trial_end)
        db.session.add(company)
        db.session.flush()

        admin = User(
            company_id=company.id,
            name=user_name,
            email=email,
            role="admin",
            active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        seed_demo_data(company, admin)

        login_user(admin)
        flash(f"Bem-vindo(a), {user_name}! Seu teste grátis de 7 dias começa agora.", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth/cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("E-mail ou senha incorretos.", "danger")
            return render_template("auth/login.html", email=email)

        if not user.active:
            flash("Sua conta está desativada. Contate o administrador.", "danger")
            return render_template("auth/login.html", email=email)

        if not user.company.active:
            flash("Conta da empresa desativada. Entre em contato com o suporte.", "danger")
            return render_template("auth/login.html", email=email)

        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard"))

    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu com sucesso.", "info")
    return redirect(url_for("login"))


@app.route("/app/dashboard")
@login_required
def dashboard():
    result = trial_check()
    if result:
        return result

    company = current_user.company
    days = company.days_remaining()
    show_trial_warning = (company.plan == "trial" and days is not None and days <= 2)

    base_query = Request.query.filter_by(company_id=company.id)

    stats = {
        "total": base_query.count(),
        "pendentes": base_query.filter_by(status="pendente").count(),
        "aprovados": base_query.filter_by(status="aprovado").count(),
        "concluidos": base_query.filter_by(status="concluido").count(),
    }

    if current_user.role == "admin":
        recent = base_query.order_by(Request.created_at.desc()).limit(10).all()
        pendentes_urgentes = base_query.filter_by(status="pendente").order_by(Request.created_at).all()
    elif current_user.role == "approver":
        recent = base_query.order_by(Request.created_at.desc()).limit(10).all()
        pendentes_urgentes = base_query.filter_by(status="pendente").order_by(Request.created_at).all()
    else:
        recent = base_query.filter_by(created_by=current_user.id).order_by(Request.created_at.desc()).limit(5).all()
        pendentes_urgentes = []

    return render_template(
        "app/dashboard.html",
        stats=stats,
        recent=recent,
        pendentes_urgentes=pendentes_urgentes,
        show_trial_warning=show_trial_warning,
        days=days,
    )


@app.route("/app/solicitacoes")
@login_required
def lista_solicitacoes():
    result = trial_check()
    if result:
        return result

    company = current_user.company
    status_filter = request.args.get("status", "")
    tipo_filter = request.args.get("tipo", "")
    setor_filter = request.args.get("setor", "").strip()

    query = Request.query.filter_by(company_id=company.id)

    if current_user.role == "employee":
        query = query.filter_by(created_by=current_user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if tipo_filter:
        query = query.filter_by(type=tipo_filter)
    if setor_filter:
        query = query.filter(Request.sector.ilike(f"%{setor_filter}%"))

    solicitacoes = query.order_by(Request.created_at.desc()).all()

    return render_template(
        "app/solicitacoes/lista.html",
        solicitacoes=solicitacoes,
        status_filter=status_filter,
        tipo_filter=tipo_filter,
        setor_filter=setor_filter,
    )


@app.route("/app/solicitacoes/nova", methods=["GET", "POST"])
@login_required
def nova_solicitacao():
    result = trial_check()
    if result:
        return result

    if request.method == "POST":
        tipo = request.form.get("tipo", "")
        descricao = request.form.get("descricao", "").strip()
        needed_date_str = request.form.get("needed_date", "")
        setor = request.form.get("setor", "").strip()

        errors = []
        if not tipo:
            errors.append("Tipo de solicitação é obrigatório.")
        if not descricao:
            errors.append("Descrição é obrigatória.")

        needed_date = None
        if needed_date_str:
            try:
                needed_date = datetime.strptime(needed_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Data inválida.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("app/solicitacoes/nova.html",
                                   tipo=tipo, descricao=descricao,
                                   needed_date=needed_date_str, setor=setor)

        req = Request(
            company_id=current_user.company_id,
            type=tipo,
            description=descricao,
            needed_date=needed_date,
            sector=setor,
            status="pendente",
            created_by=current_user.id,
        )
        db.session.add(req)
        db.session.flush()

        db.session.add(RequestHistory(
            request_id=req.id,
            user_id=current_user.id,
            action="Solicitação criada",
        ))
        db.session.commit()

        flash("Solicitação criada com sucesso!", "success")
        return redirect(url_for("detalhe_solicitacao", id=req.id))

    return render_template("app/solicitacoes/nova.html")


@app.route("/app/solicitacoes/<int:id>")
@login_required
def detalhe_solicitacao(id):
    result = trial_check()
    if result:
        return result

    req = Request.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()

    if current_user.role == "employee" and req.created_by != current_user.id:
        abort(403)

    return render_template("app/solicitacoes/detalhe.html", req=req)


@app.route("/app/solicitacoes/<int:id>/aprovar", methods=["POST"])
@login_required
@role_required("approver", "admin")
def aprovar_solicitacao(id):
    result = trial_check()
    if result:
        return result

    req = Request.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()

    if req.status != "pendente":
        flash("Esta solicitação não está mais pendente.", "warning")
        return redirect(url_for("detalhe_solicitacao", id=id))

    note = request.form.get("note", "").strip()
    req.status = "aprovado"
    req.approved_by = current_user.id
    req.updated_at = datetime.now(timezone.utc)

    db.session.add(RequestHistory(
        request_id=req.id,
        user_id=current_user.id,
        action="Solicitação aprovada",
        note=note or None,
    ))
    db.session.commit()

    flash("Solicitação aprovada com sucesso!", "success")
    return redirect(url_for("detalhe_solicitacao", id=id))


@app.route("/app/solicitacoes/<int:id>/rejeitar", methods=["POST"])
@login_required
@role_required("approver", "admin")
def rejeitar_solicitacao(id):
    result = trial_check()
    if result:
        return result

    req = Request.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()

    if req.status != "pendente":
        flash("Esta solicitação não está mais pendente.", "warning")
        return redirect(url_for("detalhe_solicitacao", id=id))

    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash("Informe o motivo da rejeição.", "danger")
        return redirect(url_for("detalhe_solicitacao", id=id))

    req.status = "rejeitado"
    req.rejection_reason = motivo
    req.updated_at = datetime.now(timezone.utc)

    db.session.add(RequestHistory(
        request_id=req.id,
        user_id=current_user.id,
        action="Solicitação rejeitada",
        note=motivo,
    ))
    db.session.commit()

    flash("Solicitação rejeitada.", "warning")
    return redirect(url_for("detalhe_solicitacao", id=id))


@app.route("/app/solicitacoes/<int:id>/status", methods=["POST"])
@login_required
@role_required("admin")
def alterar_status(id):
    result = trial_check()
    if result:
        return result

    req = Request.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()

    novo_status = request.form.get("novo_status", "")
    validos = ["em_andamento", "concluido"]

    if novo_status not in validos:
        flash("Status inválido.", "danger")
        return redirect(url_for("detalhe_solicitacao", id=id))

    if req.status not in ("aprovado", "em_andamento"):
        flash("Não é possível alterar o status desta solicitação.", "warning")
        return redirect(url_for("detalhe_solicitacao", id=id))

    label_map = {"em_andamento": "Em Andamento", "concluido": "Concluído"}
    req.status = novo_status
    req.updated_at = datetime.now(timezone.utc)

    db.session.add(RequestHistory(
        request_id=req.id,
        user_id=current_user.id,
        action=f"Status alterado para {label_map[novo_status]}",
    ))
    db.session.commit()

    flash(f"Status atualizado para {label_map[novo_status]}.", "success")
    return redirect(url_for("detalhe_solicitacao", id=id))


@app.route("/app/admin/usuarios", methods=["GET"])
@login_required
@role_required("admin")
def gerenciar_usuarios():
    result = trial_check()
    if result:
        return result

    usuarios = User.query.filter_by(company_id=current_user.company_id).order_by(User.created_at).all()
    return render_template("app/admin/usuarios.html", usuarios=usuarios)


@app.route("/app/admin/usuarios", methods=["POST"])
@login_required
@role_required("admin")
def criar_usuario():
    result = trial_check()
    if result:
        return result

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "employee")
    password = request.form.get("password", "")

    errors = []
    if not name:
        errors.append("Nome é obrigatório.")
    if not email or "@" not in email:
        errors.append("E-mail inválido.")
    if role not in ("employee", "approver", "admin"):
        errors.append("Perfil inválido.")
    if len(password) < 6:
        errors.append("A senha deve ter pelo menos 6 caracteres.")

    existing = User.query.filter_by(company_id=current_user.company_id, email=email).first()
    if existing:
        errors.append("E-mail já cadastrado nesta empresa.")

    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        user = User(
            company_id=current_user.company_id,
            name=name,
            email=email,
            role=role,
            active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"Usuário {name} criado com sucesso!", "success")

    return redirect(url_for("gerenciar_usuarios"))


@app.route("/app/admin/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def toggle_usuario(id):
    user = User.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()

    if user.id == current_user.id:
        flash("Você não pode desativar sua própria conta.", "danger")
        return redirect(url_for("gerenciar_usuarios"))

    user.active = not user.active
    db.session.commit()

    status_text = "ativado" if user.active else "desativado"
    flash(f"Usuário {user.name} {status_text}.", "info")
    return redirect(url_for("gerenciar_usuarios"))


@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") == "development")
