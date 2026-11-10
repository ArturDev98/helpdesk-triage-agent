"""Configuración en TOML; las rutas son relativas al archivo de configuración."""
import tomllib
from pathlib import Path


class Config(dict):
    def __init__(self, path):
        self.path = Path(path).resolve()
        super().__init__(tomllib.loads(self.path.read_text(encoding="utf-8")))

    def resolve(self, value):
        return (self.path.parent / value).resolve()

    @property
    def modules(self):
        return self.get("modules", {})

    @property
    def categories(self):
        return self.get("categories", {})
