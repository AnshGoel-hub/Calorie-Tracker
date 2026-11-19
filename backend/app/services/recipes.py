"""Recipes: raw ingredient lines in, per-portion nutrition out. Totals are always computed here from the
raw lines divided by the number of portions, never from a cooked weight and never from client-sent totals."""
import json

from app.core.errors import ServiceError
from app.models import Recipe
from app.schemas import IngredientLine, RecipeIn, RecipeOut
from app.services.common import clip, norm_name

MAX_PORTION_KCAL = 5000


def per_portion(lines: list[IngredientLine], portions: float) -> dict:
    return {key: round(sum(getattr(i, key) for i in lines) / portions, 1)
            for key in ("kcal", "protein", "carbs", "fat")}


def values(b: RecipeIn) -> dict:
    """Column values for a recipe row, or a ServiceError if the recipe is unusable."""
    name = clip(b.name, 120).strip()
    if not name:
        raise ServiceError(422, "Give the recipe a name")
    pp = per_portion(b.ingredients, b.portions)
    if pp["kcal"] <= 0:
        raise ServiceError(422, "The ingredients add up to 0 kcal")
    if pp["kcal"] > MAX_PORTION_KCAL:
        raise ServiceError(422, f"One portion would be over {MAX_PORTION_KCAL} kcal. "
                                "Check the quantities or the number of portions")
    return {"name": name, "name_norm": norm_name(name), "portions": b.portions, **pp,
            "ingredients": json.dumps([i.model_dump() for i in b.ingredients])}


def to_out(r: Recipe) -> RecipeOut:
    return RecipeOut(id=r.id, name=r.name, portions=r.portions, kcal=r.kcal, protein=r.protein, carbs=r.carbs,
                     fat=r.fat, ingredients=json.loads(r.ingredients), version=r.version,
                     updated_at=r.updated_at)