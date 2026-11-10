"""Publica el resultado: un hilo por ticket en Google Chat, un mensaje en Slack o la consola."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ICONS = {"incidente": "🔴", "consulta": "💬", "operativo": "🛠️", "requerimiento": "📝"}


def format_result(ticket, result, issue_urls):
    t, rel, d = result.triage, result.relation, result.diagnosis
    lines = [f"{ICONS.get(t.category, '•')} *{ticket.id} · {ticket.title}*",
             f"{t.category} · {t.module} · severidad {t.severity}", f"_{t.summary}_", ""]
    if rel.kind == "known_issue":
        ref = issue_urls.get(rel.ref) or rel.ref
        lines.append(f"🔗 Coincide con el issue {ref} (confianza {rel.confidence}). {rel.reason}")
    elif rel.kind == "closed_ticket":
        lines.append(f"♻️ Ya pasó en el ticket {rel.ref} (confianza {rel.confidence}). {rel.reason}")
    if d:
        lines += [f"🧭 *Hipótesis:* {d.hypothesis}"]
        lines += [f"   • {path}" for path in d.files]
        lines += ["*Para confirmar:*"] + [f"   {i}. {step}" for i, step in enumerate(d.verify, 1)]
        lines += [f"*Respuesta sugerida:* {d.reply}"]
    lines += ["", f"*Acción:* {result.action}"]
    return "\n".join(lines)


class ConsoleNotifier:
    def send(self, thread, text):
        print(f"\n── {thread} " + "─" * 40 + f"\n{text}")


class WebhookNotifier:
    def __init__(self, url, style):
        self.url, self.style = url, style

    def send(self, thread, text):
        url = self.url
        if self.style == "google-chat":
            # threadKey agrupa todos los mensajes del mismo ticket en un hilo.
            sep = "&" if "?" in url else "?"
            url += sep + urllib.parse.urlencode({"threadKey": thread,
                                                 "messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"})
        body = json.dumps({"text": text}).encode("utf-8")
        request = urllib.request.Request(url, body, {"Content-Type": "application/json; charset=utf-8"})
        try:
            urllib.request.urlopen(request, timeout=15).close()
        except urllib.error.HTTPError as e:
            # Un 4xx no se reintenta (mensaje inválido); el 429 y los 5xx sí, en el siguiente ciclo.
            if e.code == 429 or e.code >= 500:
                raise
            print(f"[chat] {e.code} al publicar {thread}; se descarta")


def build_notifier(config, dry_run):
    chat = config.get("chat", {})
    style = chat.get("style", "console")
    url = os.environ.get(chat.get("webhook_env", "CHAT_WEBHOOK_URL"), "")
    if dry_run or style == "console" or not url:
        return ConsoleNotifier()
    return WebhookNotifier(url, style)
