from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    plan = db.Column(db.String(20), default="trial")
    trial_end = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", backref="company", lazy=True)
    requests = db.relationship("Request", backref="company", lazy=True)

    def is_trial_active(self):
        if self.plan != "trial":
            return True
        if self.trial_end is None:
            return False
        now = datetime.now(timezone.utc)
        end = self.trial_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return end > now

    def days_remaining(self):
        if self.plan != "trial" or self.trial_end is None:
            return None
        now = datetime.now(timezone.utc)
        end = self.trial_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = end - now
        return max(0, delta.days)

    def __repr__(self):
        return f"<Company {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="employee")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("company_id", "email", name="uq_company_email"),)

    requests_created = db.relationship(
        "Request", foreign_keys="Request.created_by", backref="creator", lazy=True
    )
    requests_approved = db.relationship(
        "Request", foreign_keys="Request.approved_by", backref="approver", lazy=True
    )
    history_entries = db.relationship("RequestHistory", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def role_label(self):
        labels = {"employee": "Funcionário", "approver": "Aprovador", "admin": "Admin"}
        return labels.get(self.role, self.role)

    def __repr__(self):
        return f"<User {self.email}>"


class Request(db.Model):
    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=False)
    needed_date = db.Column(db.Date, nullable=True)
    sector = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(30), default="pendente")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    history = db.relationship(
        "RequestHistory", backref="request", lazy=True, order_by="RequestHistory.created_at"
    )

    TYPE_LABELS = {
        "material": "Material",
        "ferias": "Férias",
        "manutencao": "Manutenção",
        "outro": "Outro",
    }

    STATUS_LABELS = {
        "pendente": "Pendente",
        "aprovado": "Aprovado",
        "rejeitado": "Rejeitado",
        "em_andamento": "Em Andamento",
        "concluido": "Concluído",
    }

    STATUS_COLORS = {
        "pendente": "warning",
        "aprovado": "success",
        "rejeitado": "danger",
        "em_andamento": "primary",
        "concluido": "secondary",
    }

    TYPE_ICONS = {
        "material": "bi-box-seam",
        "ferias": "bi-calendar-check",
        "manutencao": "bi-tools",
        "outro": "bi-three-dots-vertical",
    }

    def type_label(self):
        return self.TYPE_LABELS.get(self.type, self.type)

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    def status_color(self):
        return self.STATUS_COLORS.get(self.status, "secondary")

    def type_icon(self):
        return self.TYPE_ICONS.get(self.type, "bi-question-circle")

    def progress_pct(self):
        mapping = {
            "pendente": 10,
            "aprovado": 40,
            "em_andamento": 70,
            "concluido": 100,
            "rejeitado": 0,
        }
        return mapping.get(self.status, 0)

    def __repr__(self):
        return f"<Request {self.id} {self.type}>"


class RequestHistory(db.Model):
    __tablename__ = "request_history"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<RequestHistory {self.id} {self.action}>"
