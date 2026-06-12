from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from kerykeion import AstrologicalSubject, SynastryAspects
import uvicorn

app = FastAPI(title="SintonÍA Astrology API", version="1.1.0")

# Planetas base (sin nodos: los nodos se agregan aparte porque cambiaron de nombre
# entre versiones de Kerykeion).
BASE_PLANETS = [
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
    "chiron",
]

# Nombres candidatos de los nodos, de la versión nueva a la vieja de Kerykeion.
# La versión nueva usa *_lunar_node; versiones viejas usaban true_node / mean_node.
NORTH_NODE_ATTRS = ["true_north_lunar_node", "mean_north_lunar_node", "true_node", "mean_node"]
SOUTH_NODE_ATTRS = ["true_south_lunar_node", "mean_south_lunar_node", "true_south_node", "mean_south_node"]

SIGNS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth",
            "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth"]


class NatalRequest(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    city: Optional[str] = "Buenos Aires"
    nation: Optional[str] = "AR"
    lat: Optional[float] = None
    lon: Optional[float] = None
    lng: Optional[float] = None
    tz: Optional[str] = None
    tz_str: Optional[str] = None


class SynastryRequest(BaseModel):
    person_a: NatalRequest
    person_b: NatalRequest


def _point_dict(obj) -> dict:
    return {
        "name": obj.name,
        "sign": obj.sign,
        "sign_num": obj.sign_num,
        "position": round(obj.position, 4),
        "abs_pos": round(obj.abs_pos, 4),
        "house": obj.house,
        "retrograde": obj.retrograde,
    }


def _first_attr(s, attrs):
    """Devuelve el primer atributo existente y no nulo de la lista."""
    for a in attrs:
        obj = getattr(s, a, None)
        if obj is not None:
            return obj
    return None


def _house_from_abs(abs_pos: float, houses: dict) -> Optional[str]:
    """Calcula en qué casa cae un grado absoluto, comparando contra las cúspides."""
    if not houses:
        return None
    cusps = []
    for i in range(1, 13):
        h = houses.get(f"house_{i}")
        if not h:
            return None
        cusps.append(h["abs_pos"])
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if start <= end:
            inside = start <= abs_pos < end
        else:  # la casa cruza 0°
            inside = abs_pos >= start or abs_pos < end
        if inside:
            return f"{ORDINALS[i]}_House"
    return None


def subject_to_dict(s: AstrologicalSubject) -> dict:
    planets = {}
    for planet in BASE_PLANETS:
        obj = getattr(s, planet, None)
        if obj:
            planets[planet] = _point_dict(obj)

    houses = {}
    house_attrs = [f"{ORDINALS[i].lower()}_house" for i in range(12)]
    for i, attr in enumerate(house_attrs, start=1):
        house = getattr(s, attr, None)
        if house:
            houses[f"house_{i}"] = {
                "sign": house.sign,
                "position": round(house.position, 4),
                "abs_pos": round(house.abs_pos, 4),
            }

    # --- Nodos lunares (eje nodal / dirección del alma) ---
    north = _first_attr(s, NORTH_NODE_ATTRS)
    if north is not None:
        planets["north_node"] = _point_dict(north)

    south = _first_attr(s, SOUTH_NODE_ATTRS)
    if south is not None:
        planets["south_node"] = _point_dict(south)
    elif north is not None:
        # Fallback: el Nodo Sur es el punto opuesto exacto al Nodo Norte.
        south_abs = (north.abs_pos + 180.0) % 360.0
        sign_idx = int(south_abs // 30)
        planets["south_node"] = {
            "name": "South_Node",
            "sign": SIGNS[sign_idx],
            "sign_num": sign_idx,
            "position": round(south_abs % 30, 4),
            "abs_pos": round(south_abs, 4),
            "house": _house_from_abs(south_abs, houses),
            "retrograde": getattr(north, "retrograde", True),
        }

    return {
        "name": s.name,
        "birth_data": {
            "year": s.year,
            "month": s.month,
            "day": s.day,
            "hour": s.hour,
            "minute": s.minute,
            "city": s.city,
            "nation": s.nation,
            "lat": s.lat,
            "lng": s.lng,
            "tz_str": s.tz_str,
        },
        "sun_sign": s.sun.sign,
        "moon_sign": s.moon.sign,
        "rising_sign": s.first_house.sign,
        "planets": planets,
        "houses": houses,
    }


def make_subject(data: NatalRequest) -> AstrologicalSubject:
    kwargs = {
        "name": data.name,
        "year": data.year,
        "month": data.month,
        "day": data.day,
        "hour": data.hour,
        "minute": data.minute,
        "city": data.city or "Buenos Aires",
        "nation": data.nation or "AR",
    }
    if data.lat is not None:
        kwargs["lat"] = data.lat
    # Acepta tanto lng como lon
    lng = data.lng if data.lng is not None else data.lon
    if lng is not None:
        kwargs["lng"] = lng
    # Acepta tanto tz_str como tz
    tz = data.tz_str if data.tz_str is not None else data.tz
    if tz is not None:
        kwargs["tz_str"] = tz
    return AstrologicalSubject(**kwargs)


@app.get("/health")
def health():
    return {"status": "ok", "service": "SintonÍA Astrology API"}


@app.get("/debug/points")
def debug_points():
    """Temporal: lista los atributos del subject relacionados con nodos y su valor.
    Sirve para confirmar los nombres reales en la versión de Kerykeion desplegada."""
    s = AstrologicalSubject("Debug", 1988, 3, 15, 14, 30,
                            lng=-58.3816, lat=-34.6037,
                            tz_str="America/Argentina/Buenos_Aires",
                            city="Buenos Aires", nation="AR")
    node_attrs = [a for a in dir(s) if "node" in a.lower() and not a.startswith("_")]
    out = {}
    for a in node_attrs:
        obj = getattr(s, a, None)
        if obj is not None and hasattr(obj, "sign"):
            out[a] = {"name": getattr(obj, "name", None), "sign": obj.sign,
                      "position": round(getattr(obj, "position", 0), 2),
                      "house": getattr(obj, "house", None)}
        else:
            out[a] = repr(obj)
    return {"node_like_attrs": node_attrs, "values": out}


@app.post("/natal")
def natal(request: NatalRequest):
    try:
        subject = make_subject(request)
        return {"success": True, "data": subject_to_dict(subject)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/synastry")
def synastry(request: SynastryRequest):
    try:
        person_a = make_subject(request.person_a)
        person_b = make_subject(request.person_b)

        synastry = SynastryAspects(person_a, person_b)
        aspects_list = []
        for aspect in synastry.relevant_aspects:
            aspects_list.append({
                "p1_name": aspect.get("p1_name"),
                "p1_abs_pos": aspect.get("p1_abs_pos"),
                "p2_name": aspect.get("p2_name"),
                "p2_abs_pos": aspect.get("p2_abs_pos"),
                "aspect": aspect.get("aspect"),
                "orbit": round(aspect.get("orbit", 0), 4),
                "aspect_degrees": aspect.get("aspect_degrees"),
                "diff": round(aspect.get("diff", 0), 4),
            })

        return {
            "success": True,
            "data": {
                "person_a": subject_to_dict(person_a),
                "person_b": subject_to_dict(person_b),
                "aspects": aspects_list,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
