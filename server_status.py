"""Consulta el estado público de un servidor de Minecraft Java."""

from mcstatus import JavaServer


def query_server(address: str) -> dict:
    """Devuelve el estado y la latencia en milisegundos sin bloquear la interfaz."""
    address = address.strip()
    if not address:
        return {"configured": False, "online": False, "address": "", "players": None, "maximum": None, "latencyMs": None}
    try:
        response = JavaServer.lookup(address, timeout=3).status()
    except Exception:
        return {"configured": True, "online": False, "address": address, "players": None, "maximum": None, "latencyMs": None}
    if response.players.max == 0:
        return {"configured": True, "online": False, "address": address, "players": None,
                "maximum": None, "latencyMs": None, "message": "Servidor apagado"}
    return {
        "configured": True,
        "online": True,
        "address": address,
        "players": response.players.online,
        "maximum": response.players.max,
        "latencyMs": round(response.latency),
    }
