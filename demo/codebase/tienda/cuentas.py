"""Registro, inicio de sesión y recuperación de contraseña."""
import secrets


def solicitar_recuperacion(usuario, enviar_correo):
    token = secrets.token_urlsafe(24)
    usuario["token_recuperacion"] = token
    enviar_correo(usuario["correo"], "Recupera tu contraseña", f"https://tienda.ejemplo/recuperar/{token}")
    return token


def cambiar_correo(usuario, nuevo):
    usuario["correo"] = nuevo.strip().lower()
    usuario["verificado"] = False
    return usuario
