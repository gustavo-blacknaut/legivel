from html import escape

from legivel.mail.sender import OutgoingMail

TEXTS = {
    "pt-BR": {
        "invite": (
            "Convite para o {instance}",
            "{inviter} convidou você para acessar o {instance} como {role}.",
            "Criar minha conta",
            "O link vale até {expires} e só pode ser usado uma vez.",
        ),
        "verify": (
            "Confirme seu e-mail no {instance}",
            "Confirme que este endereço é seu para concluir o cadastro no {instance}.",
            "Confirmar e-mail",
            "O link vale até {expires}.",
        ),
        "reset": (
            "Redefinição de senha no {instance}",
            "Recebemos um pedido para redefinir a senha da sua conta no {instance}."
            " Se não foi você, ignore este e-mail; sua senha continua a mesma.",
            "Definir nova senha",
            "O link vale até {expires} e só pode ser usado uma vez.",
        ),
        "roles": {"admin": "administrador", "reviewer": "revisor", "reader": "leitor"},
    },
    "en": {
        "invite": (
            "Invitation to {instance}",
            "{inviter} invited you to {instance} as {role}.",
            "Create my account",
            "The link is valid until {expires} and can be used once.",
        ),
        "verify": (
            "Confirm your e-mail on {instance}",
            "Confirm this address belongs to you to finish signing up on {instance}.",
            "Confirm e-mail",
            "The link is valid until {expires}.",
        ),
        "reset": (
            "Password reset on {instance}",
            "We received a request to reset your password on {instance}. If it wasn't you, ignore this e-mail.",
            "Set a new password",
            "The link is valid until {expires} and can be used once.",
        ),
        "roles": {"admin": "administrator", "reviewer": "reviewer", "reader": "reader"},
    },
}


def compose(kind: str, language: str, to: str, link: str, **values: str) -> OutgoingMail:
    texts = TEXTS.get(language, TEXTS["pt-BR"])
    if "role" in values:
        values["role"] = texts["roles"].get(values["role"], values["role"])
    subject, body, action, footer = (part.format(**values) for part in texts[kind])
    text = f"{body}\n\n{action}: {link}\n\n{footer}\n"
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#1d2420;max-width:520px">'
        f"<p>{escape(body)}</p>"
        f'<p><a href="{escape(link)}" style="display:inline-block;padding:10px 16px;background:#1f6f4a;color:#fff;'
        f'text-decoration:none;border-radius:6px">{escape(action)}</a></p>'
        f'<p style="color:#5b665f;font-size:13px">{escape(footer)}<br>{escape(link)}</p></div>'
    )
    return OutgoingMail(to=to, subject=subject, text=text, html=html)
