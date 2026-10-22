"""Consulta el estado público de un servidor de Minecraft Java."""

from mcstatus import JavaServer


def query_server(address: str) -> dict:
    """Devuelve el estado y la latencia en milisegundos sin bloquear la interfaz."""
    if not address.strip():
        return {"configured": False, "online": False, "players": None, "maximum": None, "latencyMs": None}
    try:
        response = JavaServer.lookup(address.strip(), timeout=3).status()
    except Exception:
        return {"configured": True, "online": False, "players": None, "maximum": None, "latencyMs": None}
    return {
        "configured": True,
        "online": True,
        "players": response.players.online,
        "maximum": response.players.max,
        "latencyMs": round(response.latency),
    }
