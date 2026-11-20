#!/usr/bin/env python3
"""Seed initial recipes into Firestore for chef-concierge."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-005c40b02edd"

RECIPES = [
    {
        "id": "garlic-butter-salmon",
        "title": "Garlic Butter Pan-Seared Salmon",
        "description": "Crispy skin salmon fillets basted in a rich garlic herb lemon butter sauce.",
        "cuisine": "Mediterranean",
        "difficulty": "Easy",
        "prep_time_minutes": 10,
        "cook_time_minutes": 12,
        "servings": 2,
        "ingredients": [
            "2 salmon fillets (6 oz each)",
            "3 cloves garlic, minced",
            "2 tbsp butter",
            "1 tbsp olive oil",
            "1 tbsp fresh lemon juice",
            "1 tbsp chopped fresh parsley",
            "Salt and black pepper to taste"
        ],
        "instructions": [
            "Pat salmon fillets dry and season generously with salt and pepper.",
            "Heat olive oil in a skillet over medium-high heat. Place salmon skin-side down and cook for 4-5 minutes until crispy.",
            "Flip fillets, reduce heat to medium, add butter and garlic to the pan.",
            "Baste salmon with melting garlic butter for 3-4 minutes until cooked through.",
            "Drizzle with lemon juice, garnish with fresh parsley, and serve immediately."
        ],
        "dietary_tags": ["keto", "low-carb", "gluten-free", "pescatarian"],
        "nutrition": {
            "calories": 460,
            "protein_g": 38,
            "carbs_g": 2,
            "fat_g": 32
        }
    },
    {
        "id": "keto-chicken-avocado-bowl",
        "title": "Grilled Chicken Avocado Salad Bowl",
        "description": "Juicy grilled chicken breast slices on mixed greens with ripe avocado, cherry tomatoes, and lime vinaigrette.",
        "cuisine": "American / Healthy",
        "difficulty": "Easy",
        "prep_time_minutes": 15,
        "cook_time_minutes": 10,
        "servings": 2,
        "ingredients": [
            "2 boneless chicken breasts",
            "1 ripe avocado, sliced",
            "4 cups mixed greens",
            "1/2 cup cherry tomatoes, halved",
            "2 tbsp extra virgin olive oil",
            "1 tbsp lime juice",
            "1/4 cup feta cheese crumbles",
            "Salt, pepper, and garlic powder"
        ],
        "instructions": [
            "Season chicken breasts with olive oil, salt, pepper, and garlic powder.",
            "Grill or pan-sear for 5-6 minutes per side until internal temperature reaches 165°F (74°C). Let rest, then slice.",
            "In large bowls, arrange mixed greens, halved tomatoes, sliced avocado, and grilled chicken.",
            "Whisk olive oil and lime juice; drizzle over salad and top with feta."
        ],
        "dietary_tags": ["keto", "low-carb", "gluten-free", "high-protein"],
        "nutrition": {
            "calories": 520,
            "protein_g": 48,
            "carbs_g": 8,
            "fat_g": 32
        }
    },
    {
        "id": "crispy-airfryer-tofu",
        "title": "Crispy Air Fryer Sesame Ginger Tofu",
        "description": "Extra-crispy golden tofu cubes tossed in a sweet-savory sesame ginger tamari glaze.",
        "cuisine": "Asian / Vegan",
        "difficulty": "Easy",
        "prep_time_minutes": 15,
        "cook_time_minutes": 15,
        "servings": 3,
        "ingredients": [
            "1 block (14 oz) extra firm tofu, pressed and cubed",
            "1.5 tbsp cornstarch",
            "1 tbsp sesame oil",
            "2 tbsp low-sodium tamari or soy sauce",
            "1 tbsp maple syrup",
            "1 tsp grated fresh ginger",
            "1 clove garlic, minced",
            "1 tbsp toasted sesame seeds",
            "2 green onions, thinly sliced"
        ],
        "instructions": [
            "Press tofu for 15 minutes, then cut into 3/4-inch cubes.",
            "Toss tofu cubes gently with 1 tsp sesame oil and cornstarch until evenly coated.",
            "Air fry at 400°F (200°C) for 15 minutes, shaking the basket halfway, until crispy and golden.",
            "Whisk tamari, maple syrup, ginger, garlic, and remaining sesame oil in a small saucepan over low heat for 2 minutes.",
            "Toss crispy tofu in the glaze, sprinkle with sesame seeds and green onions."
        ],
        "dietary_tags": ["vegan", "vegetarian", "dairy-free", "gluten-free"],
        "nutrition": {
            "calories": 280,
            "protein_g": 18,
            "carbs_g": 16,
            "fat_g": 16
        }
    },
    {
        "id": "truffle-mushroom-risotto",
        "title": "Creamy Truffle Wild Mushroom Risotto",
        "description": "Classic Italian Arborio rice slowly simmered with wild forest mushrooms, white wine, Parmesan, and a touch of black truffle oil.",
        "cuisine": "Italian",
        "difficulty": "Medium",
        "prep_time_minutes": 15,
        "cook_time_minutes": 30,
        "servings": 4,
        "ingredients": [
            "1.5 cups Arborio rice",
            "8 oz mixed wild mushrooms (cremini, shiitake, oyster), sliced",
            "4 cups warm vegetable or chicken broth",
            "1/2 cup dry white wine",
            "1 shallot, finely diced",
            "2 cloves garlic, minced",
            "2 tbsp butter",
            "1/2 cup freshly grated Parmigiano-Reggiano",
            "1 tsp black truffle oil",
            "Fresh thyme leaves"
        ],
        "instructions": [
            "Sauté sliced mushrooms in 1 tbsp butter over medium-high heat until caramelized; set aside.",
            "In the same pot, melt remaining butter and sauté shallot and garlic until translucent.",
            "Add Arborio rice and toast for 2 minutes until edges become pearly.",
            "Pour in white wine and stir until completely absorbed.",
            "Add warm broth one ladle at a time, stirring constantly and allowing each ladle to absorb before adding more (about 20 minutes).",
            "Fold in sautéed mushrooms and grated Parmesan. Remove from heat, drizzle with truffle oil, and garnish with fresh thyme."
        ],
        "dietary_tags": ["vegetarian", "comfort-food"],
        "nutrition": {
            "calories": 420,
            "protein_g": 11,
            "carbs_g": 62,
            "fat_g": 13
        }
    }
]


def seed_database():
    print(f"Connecting to Firestore in project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("recipes")

    for recipe in RECIPES:
        doc_id = recipe["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(recipe)
        print(f"✓ Seeded recipe: {recipe['title']} (ID: {doc_id})")

    print(f"\nSuccessfully seeded {len(RECIPES)} recipes into Firestore!")


if __name__ == "__main__":
    seed_database()
