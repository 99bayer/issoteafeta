from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, send_from_directory,
                   Response, abort)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os, json, hmac, hashlib, secrets, zipfile, io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "issoteafeta-troque-em-producao")

# ── Banco de dados ──────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///issoteafeta.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

KIWIFY_SECRET = os.environ.get("KIWIFY_SECRET", "")
ADMIN_KEY     = os.environ.get("ADMIN_KEY", "")
GMAIL_USER    = os.environ.get("GMAIL_USER", "")
GMAIL_PASS    = os.environ.get("GMAIL_PASS", "")

# ── Models ──────────────────────────────────────────────────────────────────
class TokenEntrega(db.Model):
    """Token gerado após compra para acesso à página de entrega dos PDFs"""
    id        = db.Column(db.Integer, primary_key=True)
    token     = db.Column(db.String(64), unique=True, nullable=False)
    produto   = db.Column(db.String(20), nullable=False)  # mapa/desafio/combo
    email     = db.Column(db.String(150), nullable=True)
    nome      = db.Column(db.String(100), nullable=True)
    usado     = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    expira_em = db.Column(db.DateTime, nullable=False)

# ── E-mail de entrega ───────────────────────────────────────────────────────
def enviar_email_entrega(destinatario, nome, produto, link):
    if not GMAIL_USER or not GMAIL_PASS:
        print("Gmail não configurado — pulando envio")
        return False

    produtos_nome = {
        "mapa":    "Mapa Energético Pessoal",
        "desafio": "Desafio 21 Dias",
        "combo":   "Combo Completo — Mapa + Desafio 21 Dias",
    }
    produto_label = produtos_nome.get(produto, "seu material")
    nome_display  = nome.split()[0] if nome else "querida"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✨ Seu {produto_label} está pronto, {nome_display}!"
    msg["From"]    = f"Isso Te Afeta <{GMAIL_USER}>"
    msg["To"]      = destinatario

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#FFFDF5;font-family:'Helvetica Neue',Arial,sans-serif">
<div style="max-width:520px;margin:0 auto;padding:32px 20px">

  <div style="text-align:center;margin-bottom:28px">
    <div style="font-size:2rem;margin-bottom:6px">☯</div>
    <div style="font-size:1.5rem;font-style:italic;color:#1B9AAA">Isso Te Afeta</div>
    <div style="font-size:.7rem;font-weight:700;letter-spacing:.15em;
      text-transform:uppercase;color:#9AAA9A;margin-top:4px">
      @issoteafeta.oficial · Energia & Autoconhecimento
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:28px;
    box-shadow:0 2px 16px rgba(0,0,0,.06);margin-bottom:20px">
    <p style="font-size:1.1rem;font-weight:700;color:#1A2E1A;margin-bottom:8px">
      Olá, {nome_display}! 🎉
    </p>
    <p style="font-size:.92rem;color:#5A6A5A;line-height:1.6;margin-bottom:16px">
      Sua compra foi confirmada e seu
      <strong style="color:#1B9AAA">{produto_label}</strong>
      está pronto para ser acessado.
    </p>
    <p style="font-size:.88rem;color:#5A6A5A;line-height:1.6;margin-bottom:24px">
      Clique no botão abaixo, selecione o seu elemento
      e faça o download do material personalizado para você.
    </p>
    <div style="text-align:center;margin-bottom:20px">
      <a href="{link}"
        style="display:inline-block;
          background:linear-gradient(135deg,#1B9AAA,#4DBDCA);
          color:#fff;text-decoration:none;border-radius:50px;
          padding:15px 36px;font-size:.95rem;font-weight:800;
          box-shadow:0 5px 20px rgba(27,154,170,.3)">
        ✨ Acessar meu material
      </a>
    </div>
    <div style="background:#E0F7FA;border-left:3px solid #1B9AAA;
      border-radius:8px;padding:12px 14px;font-size:.8rem;color:#1A2E1A">
      <strong>⏰ Importante:</strong> Este link é válido por
      <strong>72 horas</strong>. Se precisar de acesso novamente,
      entre em contato pelo Instagram.
    </div>
  </div>

  <div style="background:#F0F2F5;border-radius:10px;padding:12px 14px;
    margin-bottom:20px;word-break:break-all">
    <div style="font-size:.72rem;font-weight:700;color:#9AAA9A;margin-bottom:4px;
      text-transform:uppercase;letter-spacing:.08em">Ou copie o link abaixo</div>
    <div style="font-size:.78rem;color:#1B9AAA">{link}</div>
  </div>

  <div style="text-align:center;font-size:.78rem;color:#9AAA9A;line-height:1.6">
    Dúvidas? Fale comigo no Instagram
    <a href="https://instagram.com/issoteafeta.oficial"
      style="color:#1B9AAA;font-weight:700;text-decoration:none">
      @issoteafeta.oficial
    </a><br>Com carinho ✨ — Isso Te Afeta
  </div>

</div>
</body>
</html>"""

    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.sendmail(GMAIL_USER, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# ── WEBHOOK KIWIFY ──────────────────────────────────────────────────────────
@app.route("/webhook/kiwify", methods=["POST"])
def webhook_kiwify():
    try:
        payload = request.get_json(force=True) or {}
        status  = payload.get("order_status", "")
        evento  = payload.get("type", payload.get("event", ""))
        validos = {"approved","paid","order_approved","order_paid",
                   "purchase.approved","purchase.paid"}
        if status not in validos and evento not in validos:
            return jsonify({"ok": True, "msg": "evento ignorado"}), 200

        customer = payload.get("customer", payload.get("Customer", {}))
        email    = (customer.get("email") or
                    payload.get("email") or
                    payload.get("customer_email", "")).strip().lower()
        nome     = (customer.get("name") or customer.get("full_name") or
                    payload.get("customer_name", "")).strip()
        plano    = (payload.get("product", {}).get("name") or
                    payload.get("plan_name") or
                    payload.get("offer_name", "Mapa Energético"))

        if not email:
            return jsonify({"erro": "e-mail não encontrado"}), 400

        # Identificar tipo de produto
        p = str(plano).lower()
        if "combo" in p or ("mapa" in p and "desafio" in p):
            prod_tipo = "combo"
        elif "desafio" in p or "21" in p:
            prod_tipo = "desafio"
        else:
            prod_tipo = "mapa"

        # Gerar token de entrega (72h)
        token     = secrets.token_urlsafe(32)
        expira    = datetime.utcnow() + timedelta(hours=72)
        tk        = TokenEntrega(token=token, produto=prod_tipo,
                                 email=email, nome=nome, expira_em=expira)
        db.session.add(tk)
        db.session.commit()

        # Enviar e-mail automático
        base_url = request.host_url.rstrip("/")
        link     = f"{base_url}/entrega/{token}"
        enviar_email_entrega(email, nome, prod_tipo, link)

        return jsonify({"ok": True, "email": email, "link": link}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ── PÁGINA DE ENTREGA ───────────────────────────────────────────────────────
@app.route("/entrega/<token>")
def entrega(token):
    tk = TokenEntrega.query.filter_by(token=token).first()
    if not tk:
        return render_template("entrega_erro.html",
            msg="Link inválido. Verifique o e-mail de compra.")
    if tk.expira_em < datetime.utcnow():
        return render_template("entrega_erro.html",
            msg="Este link expirou (72h). Entre em contato: @issoteafeta.oficial")
    return render_template("entrega.html",
        token=token, produto=tk.produto, usado=tk.usado)

# ── DOWNLOAD DO PDF ─────────────────────────────────────────────────────────
@app.route("/download/<token>/<elemento>")
def download_pdf(token, elemento):
    tk = TokenEntrega.query.filter_by(token=token).first()
    if not tk or tk.expira_em < datetime.utcnow():
        abort(403)

    el = elemento.strip().capitalize()
    if el == "Agua": el = "Água"
    validos = ["Madeira", "Fogo", "Terra", "Metal", "Água"]
    if el not in validos:
        abort(400)

    arquivos = []
    if tk.produto in ("mapa", "combo"):
        arquivos.append(f"Mapa_Energetico_ITA_{el}.pdf")
    if tk.produto in ("desafio", "combo"):
        arquivos.append(f"Desafio_21Dias_ITA_{el}.pdf")
    if not arquivos:
        abort(400)

    tk.usado = True
    db.session.commit()

    if len(arquivos) == 1:
        return send_from_directory("static/pdfs", arquivos[0],
            as_attachment=True, download_name=arquivos[0])

    # Combo → ZIP em memória
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in arquivos:
            caminho = os.path.join("static", "pdfs", arq)
            if os.path.exists(caminho):
                z.write(caminho, arq)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="application/zip",
        headers={"Content-Disposition":
                 f"attachment; filename=IssoteAfeta_Combo_{el}.zip"})

# ── ADMIN: gerar link manualmente ──────────────────────────────────────────
@app.route("/admin/gerar-entrega", methods=["POST"])
def admin_gerar_entrega():
    payload = request.get_json() or {}
    if payload.get("key") != ADMIN_KEY or not ADMIN_KEY:
        return jsonify({"erro": "chave incorreta"}), 403
    produto = payload.get("produto", "mapa")
    email   = payload.get("email", "")
    nome    = payload.get("nome", "")
    horas   = int(payload.get("horas", 72))
    token   = secrets.token_urlsafe(32)
    expira  = datetime.utcnow() + timedelta(hours=horas)
    db.session.add(TokenEntrega(token=token, produto=produto,
                                email=email, nome=nome, expira_em=expira))
    db.session.commit()
    link = request.host_url.rstrip("/") + "/entrega/" + token
    # Enviar e-mail se tiver e-mail
    if email:
        enviar_email_entrega(email, nome, produto, link)
    return jsonify({"ok": True, "link": link, "produto": produto})

# ── ADMIN: revogar token ───────────────────────────────────────────────────
@app.route("/admin/revogar-entrega", methods=["POST"])
def admin_revogar_entrega():
    payload = request.get_json() or {}
    if payload.get("key") != ADMIN_KEY or not ADMIN_KEY:
        return jsonify({"erro": "chave incorreta"}), 403
    token = payload.get("token", "")
    tk = TokenEntrega.query.filter_by(token=token).first()
    if tk:
        tk.expira_em = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "revogado": token})
    return jsonify({"erro": "token não encontrado"}), 404

# ── Página inicial ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect("https://www.instagram.com/issoteafeta.oficial")

# ── Init ───────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
