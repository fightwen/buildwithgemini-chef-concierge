# My agent: chef-concierge
One-liner: A conversational agent that helps home cooks and food lovers plan meals, cook with available ingredients, and hit nutrition goals with a catalog of curated recipes and pantry items. (一個協助料理愛好者依現有食材與飲食偏好規劃菜單、查詢食譜並計算營養的個人主廚助理)

Tool coverage:
- Memory: User dietary restrictions (e.g. keto, vegan, gluten-free), allergies, disliked ingredients, available kitchen equipment (e.g. air fryer, oven), and pantry staples.
- Tools: Search recipe catalog, filter recipes by available ingredients/time, manage pantry/shopping list items, and record meal logs.
- Catalog/UI: Recipe cards (cooking time, difficulty, rating, ingredients list), weekly meal plan tables, and pantry inventory cards.
- Image gen: Photorealistic plated dish presentations and serving style visuals generated via Gemini image model.
- Sandbox: Dynamic ingredient portion scaling based on guest headcount and nutritional macro calculations (calories, protein, carbs, fat).

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Code sandbox for macro/portion calculation, Firestore for recipe & pantry persistence, Cloud Trace for observability.
