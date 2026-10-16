"""Garantias sobre a imagem Docker, checadas sem precisar do Docker (rodam no CI)."""

import re
from fnmatch import fnmatch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
SERVICE = COMPOSE["services"]["assistente"]


def ignored(path: str) -> bool:
    """Aproximacao do .dockerignore: padrao sem barra so vale na raiz."""
    result = False
    for raw in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line.lstrip("!").rstrip("/")
        match = (
            fnmatch(path, pattern)
            or path.startswith(pattern + "/")
            or fnmatch(path, pattern.replace("**/", "*/"))
        )
        if match:
            result = not negated
    return result


def test_base_de_conhecimento_e_codigo_nao_sao_ignorados() -> None:
    for path in [
        "knowledge/platform/planos.md",
        "knowledge/platform/plans.json",
        "app/api/main.py",
    ]:
        assert not ignored(path), f"{path} ficaria fora da imagem"


def test_segredos_e_estado_local_ficam_fora_da_imagem() -> None:
    for path in [".env", ".env.local", ".index/embeddings.json", ".git/config", ".venv/x"]:
        assert ignored(path), f"{path} entraria na imagem"
    assert not ignored(".env.example")


def test_o_que_o_dockerfile_copia_existe() -> None:
    for source in re.findall(r"^COPY\s+(\S+)\s", DOCKERFILE, flags=re.M):
        assert (ROOT / source).exists(), source


def test_imagem_roda_sem_privilegios_e_sem_segredo_embutido() -> None:
    assert re.search(r"^USER app$", DOCKERFILE, flags=re.M)
    assert "--uid" in DOCKERFILE and "nologin" in DOCKERFILE
    assert "API_KEY" not in DOCKERFILE and "ARG GEMINI" not in DOCKERFILE
    assert "COPY . " not in DOCKERFILE  # nunca copiar o contexto inteiro


def test_dockerfile_tem_healthcheck_e_comando_de_producao() -> None:
    assert "HEALTHCHECK" in DOCKERFILE and "/health" in DOCKERFILE
    assert 'CMD ["python", "-m", "app.api.serve"]' in DOCKERFILE  # sobe com proxy_headers=False


def test_compose_endurece_o_container() -> None:
    assert SERVICE["read_only"] is True
    assert SERVICE["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in SERVICE["security_opt"]
    for limite in ["mem_limit", "cpus", "pids_limit"]:
        assert limite in SERVICE


def test_compose_so_publica_em_localhost() -> None:
    for port in SERVICE["ports"]:
        assert str(port).startswith("127.0.0.1:"), port


def test_compose_nao_carrega_segredo() -> None:
    assert SERVICE["env_file"] == ".env"
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert not re.search(r"GEMINI_API_KEY\s*[:=]", text)
