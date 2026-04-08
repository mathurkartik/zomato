from src.phase2.catalog_loader import load_catalog
from src.phase3.intent_parser import extract_budget
from src.phase3.query_parser import cuisine_for_dish, extract_dish, extract_locality


def main() -> None:
    catalog = load_catalog()
    known_localities = sorted(
        {
            str(x).strip().lower()
            for x in catalog["locality"].dropna().tolist()
            if str(x).strip()
        }
    )

    cases = [
        ("pizza", "pizza", "italian"),
        ("butter chicken", "butter chicken", "north indian"),
        ("cheesecake", "cheesecake", "desserts"),
        ("dosa", "dosa", "south indian"),
        ("idli", "idli", "south indian"),
        ("vada", "vada", "south indian"),
        ("sambar", "sambar", "south indian"),
        ("uttapam", "uttapam", "south indian"),
        ("noodles", "noodles", "chinese"),
        ("fried rice", "fried rice", "chinese"),
        ("manchurian", "manchurian", "chinese"),
        ("spring roll", "spring roll", "chinese"),
        ("pasta", "pasta", "italian"),
        ("lasagna", "lasagna", "italian"),
        ("spaghetti", "spaghetti", "italian"),
        ("risotto", "risotto", "italian"),
        ("burger", "burger", "fast food"),
        ("sandwich", "sandwich", "fast food"),
        ("fries", "fries", "fast food"),
        ("wrap", "wrap", "fast food"),
        ("coffee", "coffee", "cafe"),
        ("latte", "latte", "cafe"),
        ("cappuccino", "cappuccino", "cafe"),
        ("tea", "tea", "cafe"),
        ("shake", "shake", "cafe"),
        ("cake", "cake", "desserts"),
        ("ice cream", "ice cream", "desserts"),
        ("brownie", "brownie", "desserts"),
        ("pastry", "pastry", "desserts"),
        ("waffle", "waffle", "desserts"),
        ("donut", "donut", "desserts"),
        ("pani puri", "pani puri", "street food"),
        ("golgappa", "golgappa", "street food"),
        ("chaat", "chaat", "street food"),
        ("samosa", "samosa", "street food"),
        ("kachori", "kachori", "street food"),
        ("korma", "korma", "mughlai"),
        ("nihari", "nihari", "mughlai"),
        ("steak", "steak", "continental"),
        ("grill", "grill", "continental"),
        ("biryani", "biryani", "north indian"),
        ("thali", "thali", "north indian"),
        ("roll", "roll", "fast food"),
        ("combo", "combo", "fast food"),
        ("pizza under 800", "pizza", "italian"),
        ("butter chicken in koramangala", "butter chicken", "north indian"),
        ("dosa in indiranagar under 500", "dosa", "south indian"),
        ("coffee with friends in hsr", "coffee", "cafe"),
        ("cheap dosa in jp nagar", "dosa", "south indian"),
        ("need biryani in whitefield", "biryani", "north indian"),
        ("give me pasta near church street", "pasta", "italian"),
        ("looking for burger in btm", "burger", "fast food"),
        ("sushi in indiranagar", None, None),
        ("ramen in hsr", None, None),
        ("falafel near koramangala", None, None),
        ("quick lunch in domlur", None, None),
        ("family dinner in electronic city", None, None),
        ("romantic date in indiranagar", None, None),
        ("tea and samosa in jayanagar", "tea", "cafe"),
        ("spring roll and noodles in koramangala", "spring roll", "chinese"),
    ]

    passed = 0
    failures: list[tuple[int, str, str | None, str | None, str | None, str | None]] = []
    rows: list[tuple[int, str, str | None, str | None, str | None, int | None, bool]] = []

    for i, (q, exp_dish, exp_cuisine) in enumerate(cases, start=1):
        dish = extract_dish(q)
        cuisine = cuisine_for_dish(dish)
        loc = extract_locality(q, known_localities)
        budget = extract_budget(q)
        ok = dish == exp_dish and cuisine == exp_cuisine
        if ok:
            passed += 1
        else:
            failures.append((i, q, exp_dish, dish, exp_cuisine, cuisine))
        rows.append((i, q, dish, cuisine, loc, budget, ok))

    print(f"Total test cases: {len(cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
    print("--- SAMPLE OUTPUT (first 20) ---")
    for i, q, dish, cuisine, loc, budget, ok in rows[:20]:
        print(
            f"{i:02d}. q='{q}' | dish={dish} | cuisine={cuisine} | "
            f"locality={loc} | budget={budget} | pass={ok}"
        )
    if failures:
        print("--- FAILURES ---")
        for i, q, exp_d, got_d, exp_c, got_c in failures:
            print(
                f"{i:02d}. q='{q}' expected dish={exp_d} got={got_d} | "
                f"expected cuisine={exp_c} got={got_c}"
            )


if __name__ == "__main__":
    main()
