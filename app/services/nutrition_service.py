from app.models.gemini_model import GeminiModel
from app.schemas.nutrition import (
    ProfileData,
    NutritionPlan,
    MealOption,
    MealPlan,
    DailyCaloriesRange,
    MacronutrientRange,
)
from fastapi import HTTPException
import json
import logging
import re


def extract_first_json(text):
    """
    Extrage primul obiect JSON valid dintr-un text, chiar dacă există text suplimentar sau delimitatori markdown.
    """
    # Elimină delimitatorii de tip ```json sau ```
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
    # Găsește primul bloc JSON valid folosind o stivă pentru acolade
    stack = []
    start = None
    for i, c in enumerate(text):
        if c == '{':
            if not stack:
                start = i
            stack.append(c)
        elif c == '}':
            if stack:
                stack.pop()
                if not stack and start is not None:
                    candidate = text[start:i+1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        continue
    raise ValueError("No JSON object found in response.")


def generate_nutrition_plan(profile_data: ProfileData) -> NutritionPlan:
    try:
        result_text = GeminiModel.generate_nutrition_plan(profile_data.model_dump())

        if not result_text:
            raise HTTPException(status_code=500, detail="No response from Gemini API")

        try:
            json_str = extract_first_json(result_text)
            result = json.loads(json_str)
        except Exception as e:
            logging.error(f"JSON Decode Error (Provide Nutrition Advice): {str(e)}")
            logging.error(
                f"Raw Gemini Response (Provide Nutrition Advice) on JSON Decode Error: {result_text}"
            )
            raise HTTPException(status_code=500, detail=f"JSON Decode Error: {str(e)}")

        # Convert the result dictionary to Pydantic models
        daily_calories_range = DailyCaloriesRange(**result["daily_calories_range"])
        macronutrients_range = {
            k: MacronutrientRange(**v)
            for k, v in result["macronutrients_range"].items()
        }

        def parse_meal_options(meal_data):
            valid_meals = []
            for meal in meal_data:
                # Corectează ingredientele cu calorii non-int
                if "ingredients" in meal:
                    for ing in meal["ingredients"]:
                        try:
                            # Acceptă doar valori numerice, altfel pune 0
                            ing["calories"] = int(float(ing["calories"]))
                        except Exception:
                            ing["calories"] = 0
                # Corectează total_calories dacă nu e int
                if "total_calories" in meal:
                    try:
                        meal["total_calories"] = int(float(meal["total_calories"]))
                    except Exception:
                        meal["total_calories"] = 0
                try:
                    valid_meals.append(MealOption(**meal))
                except Exception as e:
                    logging.error(f"Validation error for MealOption: {meal} | Error: {e}")
                    continue
            return valid_meals

        meal_plan = MealPlan(
            breakfast=parse_meal_options(result["meal_plan"]["breakfast"]),
            lunch=parse_meal_options(result["meal_plan"]["lunch"]),
            dinner=parse_meal_options(result["meal_plan"]["dinner"]),
            snacks=parse_meal_options(result["meal_plan"]["snacks"]),
        )

        return NutritionPlan(
            daily_calories_range=daily_calories_range,
            macronutrients_range=macronutrients_range,
            meal_plan=meal_plan,
        )

    except Exception as e:
        logging.error(f"Exception (Provide Nutrition Advice): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
