from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from kerykeion import AstrologicalSubject, SynastryAspects
import uvicorn

app = FastAPI(title="SintonÍA Astrology API", version="1.0.0")


class NatalRequest(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    city: str
    nation: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    tz_str: Optional[str] = None


class SynastryRequest(BaseModel):
    person_a: NatalRequest
    person_b: NatalRequest


def subject_to_dict(s: AstrologicalSubject) -> dict:
    planets = {}
    for planet in [
        "sun", "moon", "mercury", "venus", "mars",
        "jupiter", "saturn", "uranus", "neptune", "pluto",
        "mean_node", "chiron"
    ]:
        obj = getattr(s, planet, None)
        if obj:
            planets[planet] = {
                "name": obj.name,
                "sign": obj.sign,
                "sign_num": obj.sign_num,
                "position": round(obj.position, 4),
                "abs_pos": round(obj.abs_pos, 4),
                "house": obj.house,
                "retrograde": obj.retrograde,
            }

    houses = {}
    for i in range(1, 13):
        house = getattr(s, f"first_house" if i == 1 else
                        f"second_house" if i == 2 else
                        f"third_house" if i == 3 else
                        f"fourth_house" if i == 4 else
                        f"fifth_house" if i == 5 else
                        f"sixth_house" if i == 6 else
                        f"seventh_house" if i == 7 else
                        f"eighth_house" if i == 8 else
                        f"ninth_house" if i == 9 else
                        f"tenth_house" if i == 10 else
                        f"eleventh_house" if i == 11 else
                        f"twelfth_house", None)
        if house:
            houses[f"house_{i}"] = {
                "sign": house.sign,
                "position": round(house.position, 4),
                "abs_pos": round(house.abs_pos, 4),
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
        "city": data.city,
        "nation": data.nation,
    }
    if data.lat is not None:
        kwargs["lat"] = data.lat
    if data.lng is not None:
        kwargs["lng"] = data.lng
    if data.tz_str is not None:
        kwargs["tz_str"] = data.tz_str
    return AstrologicalSubject(**kwargs)


@app.get("/health")
def health():
    return {"status": "ok", "service": "SintonÍA Astrology API"}


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
