"""Barra segredos e dados pessoais antes de irem para o repositorio publico.

Uso:
  python scripts/check_secrets.py            # todos os arquivos versionados
  python scripts/check_secrets.py --staged   # so o que esta no proximo commit (pre-commit)
  python scripts/check_secrets.py a.md b.py  # arquivos especificos
Saida 1 se achar algo. Nunca imprime o trecho encontrado, so arquivo, linha e tipo.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWED_IPS = {"127.0.0.1", "0.0.0.0"}

# (nome, regex). Cada regex e escrita para nao casar com a propria linha do codigo.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("chave Google/Gemini", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("segredo de webhook", re.compile(r"\bwhsec_[0-9A-Za-z]+")),
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("telefone BR", re.compile(r"(?<!\d)\(?\d{2}\)?\s?9\d{4}-?\d{4}(?!\d)")),
    ("caminho de servidor", re.compile(r"(?<![\w.])/opt/[\w.-]+")),
    # Os colchetes impedem a regra de casar com o proprio texto dela.
    (
        "referencia ao repositorio privado",
        re.compile(r"saas-plan[s]|SaasLandin[g]|server/li[b]/|SirBarber-Mult[i]"),
    ),
    ("chave SSH", re.compile(r"\bid_(?:ed25519|rsa|ecdsa)\w*")),
    # Qualquer valor real atribuido a variavel de segredo (pega formatos de chave desconhecidos).
    (
        "valor em variavel de segredo",
        re.compile(
            r"(?i)\b\w*(?:API_KEY|SECRET|TOKEN|PASSWORD|SSH_KEY)\s*[=:]\s*['\"]?"
            r"(?!cole-sua-chave-aqui|<|\$\{|\s*$)[^\s'\"#]{8,}"
        ),
    ),
    ("e-mail pessoal", re.compile(r"[\w.+-]+@(?:gmail|hotmail|outlook|yahoo)\.com(?:\.br)?")),
]
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
# Arquivos que nunca podem ser versionados, qualquer que seja o conteudo.
FORBIDDEN_NAMES = re.compile(
    r"(^|/)(\.env(\.(?!example$)[^/]+)?|[^/]+\.(pem|key|p12|pfx)|id_[a-z0-9_]+)$"
)
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".npz", ".lock"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str


def scan_text(text: str, path: str = "<texto>") -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(Finding(path, number, kind))
        for match in IPV4.finditer(line):
            if match.group(0) not in ALLOWED_IPS:
                findings.append(Finding(path, number, "endereco IP"))
    return findings


def scan_file(path: Path) -> list[Finding]:
    if FORBIDDEN_NAMES.search(path.as_posix()):
        return [Finding(path.as_posix(), 0, "arquivo de segredo")]
    if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return scan_text(text, path.as_posix())


def _git_paths(args: list[str]) -> list[Path]:
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout
    return [Path(p) for p in out.splitlines() if p]


def main(argv: list[str]) -> int:
    if argv == ["--staged"]:
        paths = _git_paths(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    elif argv:
        paths = [Path(a) for a in argv]
    else:
        paths = _git_paths(["ls-files"])
    findings = [f for p in paths for f in scan_file(p)]
    for f in findings:
        print(f"{f.path}:{f.line}: possivel {f.kind}")
    if findings:
        print(f"\n{len(findings)} achado(s). Remova antes de commitar (repo publico).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
