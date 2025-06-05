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


def clean_response_text(response_text: str) -> str:
    # Strip unnecessary markdown or whitespace that might have been included
    clean_text = response_text.strip("```json").strip("```").strip()
    return clean_text


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

        clean_result_text = clean_response_text(result_text)

        try:
            json_str = extract_first_json(clean_result_text)
            result = json.loads(json_str)
        except Exception as e:
            logging.error(f"JSON Decode Error (Provide Nutrition Advice): {str(e)}")
            logging.error(
                f"Cleaned Result Text (Provide Nutrition Advice) on JSON Decode Error: {clean_result_text}"
            )
            raise HTTPException(status_code=500, detail=f"JSON Decode Error: {str(e)}")

        # Convert the result dictionary to Pydantic models
        daily_calories_range = DailyCaloriesRange(**result["daily_calories_range"])
        macronutrients_range = {
            k: MacronutrientRange(**v)
            for k, v in result["macronutrients_range"].items()
        }

        def parse_meal_options(meal_data):
            return [MealOption(**meal) for meal in meal_data]

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
