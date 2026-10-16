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


def test_dockerfile_comeca_por_uma_base_fixada_por_digest() -> None:
    primeira = next(
        line for line in DOCKERFILE.splitlines() if line.strip() and not line.startswith("#")
    )
    assert re.fullmatch(r"FROM python:\d+\.\d+-slim@sha256:[0-9a-f]{64}", primeira), primeira


def test_container_nao_toca_no_computador_alem_do_listado() -> None:
    """Regras de isolamento do host. Se alguem afrouxar uma, o CI avisa."""
    configured = yaml.safe_dump(SERVICE)  # ja sem comentarios: so o que de fato vale
    assert SERVICE.get("privileged") is False
    for proibido in ["network_mode", "pid", "ipc", "devices", "cap_add", "extra_hosts"]:
        assert proibido not in SERVICE, proibido
    assert "docker.sock" not in configured
    for volume in SERVICE["volumes"]:  # so volume NOMEADO; caminho do PC (./x, C:\x, /x) e proibido
        origem = str(volume).split(":")[0]
        assert re.fullmatch(r"[a-z][a-z0-9_-]*", origem), f"bind mount proibido: {volume}"
        assert origem in COMPOSE["volumes"]


def test_container_nao_volta_sozinho_e_nao_enche_o_disco() -> None:
    assert SERVICE["restart"] in ("no", False)  # o servidor liga isso por override, nunca o padrao
    options = SERVICE["logging"]["options"]
    assert options["max-size"] and options["max-file"]  # logs com teto
    assert SERVICE["memswap_limit"] == SERVICE["mem_limit"]  # sem swap
    assert "noexec" in SERVICE["tmpfs"][0] and "size=" in SERVICE["tmpfs"][0]


def test_compose_so_publica_em_localhost() -> None:
    for port in SERVICE["ports"]:
        assert str(port).startswith("127.0.0.1:"), port


def test_compose_nao_carrega_segredo() -> None:
    assert SERVICE["env_file"] == ".env"
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert not re.search(r"GEMINI_API_KEY\s*[:=]", text)
