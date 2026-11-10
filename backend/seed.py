"""Reproducible fictional records for the first local launch."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random

from backend.data_generator import HOME_TYPES, LOCATIONS, MATERIALS
from backend.services.management_rules import timestamp

# Rooms with the photo that shows them, and how a summary describes each.
ROOMS = {"living room": ("living", "a living room that opens up for guests and quiet evenings"),
         "kitchen": ("kitchen", "a kitchen planned around how the family cooks and eats"),
         "bedroom": ("bedroom", "a bedroom kept calm, with storage built into the walls"),
         "dining area": ("dining", "a dining area sized for long dinners and homework alike"),
         "study": ("living", "a study corner with good light and space for two"),
         "entryway": ("living", "an entryway with room for shoes, bags and a bench")}
AREAS = {"HDB": (65, 120), "Condominium": (70, 160), "Landed": (150, 320)}
HOMES = {"HDB": "An HDB flat", "Condominium": "A condominium", "Landed": "A landed house"}


def _variant(base, rng, titles):
    """A different project by the same firm in the same style: its own room, place, size, budget and materials."""
    while True:
        room, location = rng.choice(list(ROOMS)), rng.choice(LOCATIONS)
        title = f"{base['style']} {room} in {location}"
        if title not in titles:
            titles.add(title)
            break
    home = rng.choice(HOME_TYPES)
    area = rng.randrange(*AREAS[home])
    materials = rng.sample(MATERIALS, 3)
    image, summary = ROOMS[room]
    return {"title": title, "type": home, "location": location, "area": f"{area} m²",
            "price": int(round(area * rng.uniform(380, 900), -3)), "image": image,
            "materials": ", ".join(m.capitalize() for m in materials),
            "summary": f"{HOMES[home]} in {location}: {summary}, "
                       f"finished in {materials[0]} and {materials[1]}."}


def seed_demo(store):
    originals = json.loads(Path(__file__).with_name("sample_projects.json").read_text(encoding="utf-8"))
    category_names = ["Japandi", "Contemporary", "Scandinavian", "Minimalist", "Retro", "Modern", "Modern Style", "Industrial"]
    descriptions = ["Japanese simplicity and Scandinavian warmth.", "Current forms and considered materials.",
                    "Light, natural and practical interiors.", "Simple lines and intentional spaces.",
                    "Vintage details and nostalgic character.", "Clean forms and functional spaces.",
                    "Modern interiors with practical details.", "Raw finishes and architectural details."]
    category_ids = {name: f"CAT-{index + 1:02d}" for index, name in enumerate(category_names)}
    now = datetime.now(timezone.utc)
    generator = random.Random(314)
    with store.transaction(write=True) as connection:
        if connection.execute("SELECT 1 FROM categories LIMIT 1").fetchone():
            return
        for name, description in zip(category_names, descriptions):
            connection.execute("""
                INSERT INTO categories(id, name, normalized_name, description, status, featured, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (category_ids[name], name, name.casefold(), description,
                  "Archived" if name == "Retro" else "Active", name in ("Japandi", "Scandinavian"), timestamp(now)))
        variants, titles = random.Random(2026), {p["title"] for p in originals}
        for project_id in range(1, 121):
            project = dict(originals[(project_id - 1) % len(originals)])
            project["id"] = project_id
            project["primary_category_id"] = category_ids[project["style"]]
            if project_id > len(originals):
                project.update(_variant(project, variants, titles))
            age_hours = (project_id * 17) % (90 * 24) + 1
            created = now - timedelta(hours=age_hours)
            connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                               (project_id, project["title"], project["firm"], json.dumps(project), timestamp(created)))
            names = {project["style"]}
            if project_id % 3 == 0:
                names.add("Modern")
            if project_id % 4 == 0:
                names.add("Modern Style")
            if project_id % 17 == 0:
                names.add("Retro")
            for name in names:
                connection.execute("INSERT INTO assignments VALUES (?, ?, ?)",
                                   (project_id, category_ids[name], timestamp(created)))
            for index in range(30):
                activity_type = generator.choices(["VIEW", "FAVOURITE_ADD", "ENQUIRY"], [7, 2, 1])[0]
                occurred = created + (now - created) * generator.random()
                connection.execute("INSERT INTO activities VALUES (?, ?, ?, ?, 'sample')",
                                   (f"sample-{project_id}-{index}", project_id, activity_type, timestamp(occurred)))
