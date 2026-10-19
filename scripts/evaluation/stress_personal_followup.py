"""Focused boundary probes added after broad stress discovery; no production edits."""

from datetime import timedelta

from scripts.evaluation.stress_personal_organizer import case, main, reply_text


@case("calendar_next_tuesday")
def next_weekday(p):
    due = p.today + timedelta(days=(1 - p.today.weekday()) % 7 or 7)
    t = p.turn(
        "I need to collect my repaired shoes next Tuesday. Put it on my list, please."
    )
    p.added(t, "task", due.isoformat(), ("shoes",))


@case("calendar_first_of_next_month")
def next_month(p):
    due = (p.today.replace(day=1) + timedelta(days=32)).replace(day=1)
    t = p.turn(
        "Please put auditing workshop stock on my list for the first day of next month."
    )
    p.added(t, "task", due.isoformat(), ("stock",))


@case("calendar_year_boundary")
def year_boundary(p):
    first = p.turn('Add "Review yearly budget" for December 31, 2026.')
    rows = p.added(first, "task", "2026-12-31", ("budget",))
    t = p.turn(
        "Move that task to the day after its current deadline. Keep the same task."
    )
    if rows:
        p.changed(t, {rows[0]["record_id"]: {"due_date": "2027-01-01"}})


@case("note_tail_reasoning")
def note_tail(p):
    body = (
        "The folder inventory is for the workshop cupboard. " * 5
        + "There are 7 red folders and 9 blue folders."
    )
    p.seed("Folder inventory", kind="note", body=body)
    t = p.turn(
        "According to my Folder inventory note, how many red and blue folders are there in total? Calculate the total."
    )
    p.unchanged(t)
    p.check("tail_information_used_to_calculate_total", "16" in reply_text(t))


@case("negative_tr_no_inspection")
def no_inspection(p):
    p.base()
    t = p.turn("Kitapları henüz iade etmedim, o görevi tamamlandı olarak işaretleme.")
    p.unchanged(t)
    p.check(
        "prohibition_does_not_read_private_records",
        not any(c["tool"] == "organizer_list" for c in t["calls"]),
        "privacy",
    )
    p.check(
        "prohibition_does_not_plan_a_mutation",
        not any(
            row.get("step") in {"add_personal_item", "update_personal_item"}
            for row in t["agent_trace"]
        ),
        "advisory",
    )


@case("completed_action_not_replayed_after_chat")
def no_replay(p):
    p.base()
    first = p.turn("Mark Return library books as done.")
    p.changed(first, {p.seeded[2]["record_id"]: {"status": "done"}})
    t = p.turn(
        "Thanks. I'm just chatting now: why do people enjoy visiting libraries? Don't change my tasks."
    )
    p.unchanged(t)


@case("calendar_with_explicit_today_control")
def explicit_today(p):
    due = (p.today.replace(day=1) + timedelta(days=32)).replace(day=1)
    t = p.turn(
        f"Today is {p.today.isoformat()}. Please put auditing workshop stock "
        "on my list for the first day of next month."
    )
    p.added(t, "task", due.isoformat(), ("stock",))


@case("note_short_content_reasoning_control")
def short_content(p):
    p.seed(
        "Folder inventory",
        kind="note",
        body="There are 7 red folders and 9 blue folders.",
    )
    t = p.turn(
        "According to my Folder inventory note, how many red and blue folders are "
        "there in total? Calculate the total."
    )
    p.unchanged(t)
    p.check("complete_information_used_to_calculate_total", "16" in reply_text(t))


if __name__ == "__main__":
    raise SystemExit(main())
